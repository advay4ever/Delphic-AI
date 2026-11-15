"""Strict validation for image requests and provider results."""

from __future__ import annotations

import re
import struct
import unicodedata
from collections.abc import Mapping
from dataclasses import replace
from io import BytesIO
from math import isfinite

from PIL import Image, UnidentifiedImageError

from .models import GeneratedImage, ImageRequest, ImageReview, RequiredObject


IMAGE_REQUEST_FIELDS = frozenset({
    "version",
    "mode",
    "subject",
    "main_subject",
    "required_objects",
    "relationships",
    "required_text",
    "style",
    "view",
    "colors",
    "avoid",
    "aspect_ratio",
    "student_prompt",
})
ALLOWED_MODES = frozenset({"educational_visual", "realistic_image", "creative_illustration"})
ALLOWED_SUBJECTS = frozenset({"math", "science"})
ALLOWED_ASPECT_RATIOS = frozenset({"1:1", "4:3", "3:4", "16:9", "9:16"})
ALLOWED_MIME_TYPES = frozenset({"image/png"})
MAX_PROMPT_CHARS = 1_200
MAX_FIELD_CHARS = 300
MAX_LIST_ITEMS = 12
MAX_REQUIRED_TEXT_ITEMS = 6
MAX_OBJECT_COUNT = 20
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_SIDE = 4_096
MAX_IMAGE_PIXELS = 16_000_000
MAX_REVIEW_ITEMS = 8
MAX_REVIEW_TEXT_CHARS = 500
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ImageValidationError(ValueError):
    """Raised when untrusted image request or result data is invalid."""


def build_image_request(payload: Mapping) -> ImageRequest:
    if not isinstance(payload, Mapping):
        raise ImageValidationError("The image request must be a JSON object.")

    unknown_fields = set(payload) - IMAGE_REQUEST_FIELDS
    if unknown_fields:
        unknown_label = min(repr(field) for field in unknown_fields)
        raise ImageValidationError(
            f"Unknown image request field: {unknown_label}."
        )

    version = payload.get("version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise ImageValidationError("Only image request version 1 is supported.")

    mode = _choice(payload.get("mode"), "mode", ALLOWED_MODES)
    subject = _choice(payload.get("subject"), "subject", ALLOWED_SUBJECTS)
    aspect_ratio = _choice(
        payload.get("aspect_ratio", "4:3"),
        "aspect ratio",
        ALLOWED_ASPECT_RATIOS,
    )
    student_prompt = _text(
        payload.get("student_prompt"),
        "student prompt",
        MAX_PROMPT_CHARS,
    )
    main_subject = _text(
        payload.get("main_subject", student_prompt),
        "main subject",
        MAX_FIELD_CHARS,
    )

    return ImageRequest(
        version=1,
        mode=mode,
        subject=subject,
        main_subject=main_subject,
        required_objects=_required_objects(payload.get("required_objects", [])),
        relationships=_text_list(payload.get("relationships", []), "relationships"),
        required_text=_text_list(
            payload.get("required_text", []),
            "required text",
            max_items=MAX_REQUIRED_TEXT_ITEMS,
        ),
        style=_text(payload.get("style", _default_style(mode)), "style", MAX_FIELD_CHARS),
        view=_text(payload.get("view", "clear view"), "view", MAX_FIELD_CHARS),
        colors=_text_list(payload.get("colors", []), "colors"),
        avoid=_text_list(payload.get("avoid", []), "avoid"),
        aspect_ratio=aspect_ratio,
        student_prompt=student_prompt,
    )


def validate_generated_image(image: GeneratedImage) -> None:
    sanitize_generated_image(image)


def sanitize_generated_image(image: GeneratedImage) -> GeneratedImage:
    """Fully decode and re-encode one provider PNG before it is trusted."""
    if not isinstance(image, GeneratedImage):
        raise ImageValidationError("The provider returned an invalid image result.")
    if image.mime_type not in ALLOWED_MIME_TYPES:
        raise ImageValidationError("This image format is not supported yet.")
    if not isinstance(image.data, bytes) or not image.data or len(image.data) > MAX_IMAGE_BYTES:
        raise ImageValidationError("The generated image has an invalid file size.")
    if (
        not isinstance(image.provider, str)
        or not isinstance(image.model, str)
        or not image.provider.strip()
        or not image.model.strip()
    ):
        raise ImageValidationError("The image provider metadata is incomplete.")
    _validate_optional_cost(image.cost_usd, "image generation")
    if (
        isinstance(image.width, bool)
        or isinstance(image.height, bool)
        or not isinstance(image.width, int)
        or not isinstance(image.height, int)
    ):
        raise ImageValidationError("The generated image dimensions are invalid.")

    actual_width, actual_height = png_dimensions(image.data)
    if (actual_width, actual_height) != (image.width, image.height):
        raise ImageValidationError("The image dimensions do not match the file.")
    if (
        image.width < 1
        or image.height < 1
        or image.width > MAX_IMAGE_SIDE
        or image.height > MAX_IMAGE_SIDE
        or image.width * image.height > MAX_IMAGE_PIXELS
    ):
        raise ImageValidationError("The generated image dimensions are too large.")

    try:
        with Image.open(BytesIO(image.data)) as decoded:
            if decoded.format != "PNG":
                raise ImageValidationError("The returned file is not a valid PNG image.")
            decoded.load()
            if decoded.size != (image.width, image.height):
                raise ImageValidationError("The image dimensions do not match the file.")
            safe_mode = "RGBA" if "A" in decoded.getbands() else "RGB"
            clean_image = decoded.convert(safe_mode)
            output = BytesIO()
            clean_image.save(output, format="PNG", optimize=True)
            clean_data = output.getvalue()
    except ImageValidationError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as error:
        raise ImageValidationError("The returned file is not a safe PNG image.") from error

    if len(clean_data) > MAX_IMAGE_BYTES:
        raise ImageValidationError("The generated image has an invalid file size.")
    return replace(image, data=clean_data, mime_type="image/png")


def validate_image_review(review: ImageReview) -> None:
    if not isinstance(review, ImageReview):
        raise ImageValidationError("The reviewer returned an invalid result.")
    if type(review.passed) is not bool or type(review.safety_problem) is not bool:
        raise ImageValidationError("The review safety decision is invalid.")
    for field_name in ("prompt_accuracy", "scientific_accuracy", "readability"):
        value = getattr(review, field_name)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ImageValidationError(f"The review {field_name.replace('_', ' ')} is invalid.")
    if review.passed and review.safety_problem:
        raise ImageValidationError("An unsafe image review cannot pass.")
    _validate_optional_cost(review.cost_usd, "image review")
    for label, items in (("missing", review.missing), ("incorrect", review.incorrect)):
        if not isinstance(items, tuple) or len(items) > MAX_REVIEW_ITEMS:
            raise ImageValidationError(f"The review {label} list is invalid.")
        for item in items:
            _text(item, f"review {label} item", MAX_REVIEW_TEXT_CHARS)
    if review.retry_instruction is not None:
        _text(review.retry_instruction, "review retry instruction", MAX_REVIEW_TEXT_CHARS)


def _choice(value: object, label: str, choices: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ImageValidationError(f"Choose a supported image {label}.")
    return value


def _text(value: object, label: str, max_chars: int) -> str:
    if not isinstance(value, str):
        raise ImageValidationError(f"The {label} must be text.")
    normalized = re.sub(r"[ \t]+", " ", value).strip()
    if not normalized:
        raise ImageValidationError(f"The {label} cannot be empty.")
    if len(normalized) > max_chars:
        raise ImageValidationError(f"The {label} is too long.")
    if any(_is_forbidden_control(character) for character in normalized):
        raise ImageValidationError(f"The {label} contains hidden control characters.")
    return normalized


def _text_list(
    value: object,
    label: str,
    *,
    max_items: int = MAX_LIST_ITEMS,
) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
        raise ImageValidationError(f"The {label} must be a list.")
    if len(value) > max_items:
        raise ImageValidationError(f"The {label} list has too many items.")
    return tuple(_text(item, label, MAX_FIELD_CHARS) for item in value)


def _required_objects(value: object) -> tuple[RequiredObject, ...]:
    if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
        raise ImageValidationError("Required objects must be a list.")
    if len(value) > MAX_LIST_ITEMS:
        raise ImageValidationError("The required objects list has too many items.")

    objects = []
    for item in value:
        if not isinstance(item, Mapping) or set(item) - {"name", "count"}:
            raise ImageValidationError("Each required object needs only a name and optional count.")
        name = _text(item.get("name"), "required object name", MAX_FIELD_CHARS)
        count = item.get("count")
        if count is not None and (
            isinstance(count, bool)
            or not isinstance(count, int)
            or not 1 <= count <= MAX_OBJECT_COUNT
        ):
            raise ImageValidationError(
                f"The count for {name} must be from 1 to {MAX_OBJECT_COUNT}."
            )
        objects.append(RequiredObject(name=name, count=count))
    return tuple(objects)


def png_dimensions(data: bytes) -> tuple[int, int]:
    if len(data) < 24 or not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        raise ImageValidationError("The returned file is not a valid PNG image.")
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _validate_optional_cost(value: object, label: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ImageValidationError(f"The {label} cost is invalid.")
    if not isfinite(float(value)) or float(value) < 0:
        raise ImageValidationError(f"The {label} cost is invalid.")


def _is_forbidden_control(character: str) -> bool:
    return unicodedata.category(character) in {"Cc", "Cf"} and character not in {"\n", "\t"}


def _default_style(mode: str) -> str:
    return {
        "educational_visual": "clear textbook illustration",
        "realistic_image": "realistic educational image",
        "creative_illustration": "colorful educational illustration",
    }[mode]
