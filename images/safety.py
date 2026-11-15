"""First-pass local safety rules for student image requests."""

from __future__ import annotations

import re
import unicodedata

from .models import ImageRequest


class ImageSafetyError(ValueError):
    """Raised when a request should not be sent to an image provider."""


MINOR_WORDS = re.compile(r"\b(child|children|kid|kids|minor|student|teen|teenager)\b", re.I)
SEXUAL_WORDS = re.compile(
    r"\b(nude|naked|nudity|porn\w*|p0rn\w*|sexualized|sexualised|sexually explicit|"
    r"explicit sex|erotic\w*|desnud\w*)\b|अश्लील|नग्न", re.I,
)
DANGEROUS_INSTRUCTION = re.compile(
    r"\b(?:how\s+to|steps?\s+to|instructions?\s+(?:for|to)|show|teach|explain)\b"
    r".{0,80}\b(?:build|make|create)\b.{0,30}"
    r"\b(?:bomb|explosive|weapon)\b",
    re.I | re.S,
)
FAKE_OR_FORGE = re.compile(r"\b(?:fake|fabricate|forge)\b", re.I)
EVIDENCE_OR_IMAGE = re.compile(r"\b(?:evidence|photo|picture|image)\b", re.I)
SCHOOL_PERSON = re.compile(r"\b(?:student|teacher|principal|classmate)\b", re.I)
FACE_SWAP = re.compile(r"\b(?:face[ -]?swap|swap .* face|deepfake)\b", re.I)
TARGETED_HATE = re.compile(
    r"\b(?:inferior race|hate propaganda|exterminate|dehumanize)\b",
    re.I,
)
BULLYING = re.compile(
    r"\b(bully\w*|humiliat\w*|mock(?:ing|ed)?|degrad\w*|ridicul\w*|humillar|burlar\w*)\b",
    re.I,
)
GRAPHIC_OR_SELF_HARM = re.compile(
    r"\b(gore|gory|dismember\w*|graphic.{0,50}(?:violence|injur\w*|wound\w*)|"
    r"severed (?:head|limb\w*)|self[ -]?harm|suicid\w*|autolesion\w*)\b|आत्महत्या",
    re.I,
)


def validate_image_safety(request: ImageRequest) -> None:
    combined = "\n".join((
        request.student_prompt,
        request.main_subject,
        *(item.name for item in request.required_objects),
        *request.relationships,
        *request.required_text,
        request.style,
        request.view,
        *request.colors,
        *request.avoid,
    ))
    validate_image_safety_text(combined)


def validate_image_safety_text(text: str) -> None:
    """Conservative first pass, not a replacement for provider/output moderation."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Cf")
    normalized = " ".join(normalized.split())
    combined = "".join(
        char for char in unicodedata.normalize("NFD", normalized)
        if unicodedata.category(char) != "Mn"
    )
    if SEXUAL_WORDS.search(combined) or SEXUAL_WORDS.search(normalized):
        if MINOR_WORDS.search(combined):
            raise ImageSafetyError("Delphic cannot create sexual images involving young people.")
        raise ImageSafetyError("Delphic cannot create sexual or nude imagery.")
    if BULLYING.search(combined):
        raise ImageSafetyError("Delphic cannot create bullying or humiliating images.")
    if GRAPHIC_OR_SELF_HARM.search(combined) or GRAPHIC_OR_SELF_HARM.search(normalized):
        raise ImageSafetyError("Delphic cannot create graphic violence or self-harm imagery.")
    if DANGEROUS_INSTRUCTION.search(combined):
        raise ImageSafetyError("Delphic cannot create instructions for making a weapon.")
    if (
        FAKE_OR_FORGE.search(combined)
        and EVIDENCE_OR_IMAGE.search(combined)
        and SCHOOL_PERSON.search(combined)
    ):
        raise ImageSafetyError("Delphic cannot create fake evidence about a real school person.")
    if FACE_SWAP.search(combined):
        raise ImageSafetyError("Face swapping is not supported.")
    if TARGETED_HATE.search(combined):
        raise ImageSafetyError("Delphic cannot create hateful propaganda.")
