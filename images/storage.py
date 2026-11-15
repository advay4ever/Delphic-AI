"""Private file and metadata storage for generated images."""

from __future__ import annotations

import os
import re
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from database import (
    get_generated_image_record,
    list_generated_image_filenames,
    list_generated_image_records,
    pop_generated_image_record,
    pop_generated_images_for_session,
    save_generated_image_record,
)

from .models import GeneratedImage, GenerationResult
from .validation import ImageValidationError, validate_generated_image, validate_image_review


IMAGE_STORAGE_DIRECTORY = "generated_images"
IMAGE_EXTENSION_BY_MIME = {"image/png": ".png"}
ORPHAN_GRACE_SECONDS = 60 * 60


class ImageStorageError(RuntimeError):
    """Raised when private image storage cannot complete safely."""


@dataclass(frozen=True)
class StoredImage:
    record: dict
    data: bytes


def get_image_storage_root(data_dir: Path) -> Path:
    return data_dir / IMAGE_STORAGE_DIRECTORY


def store_generated_image(
    result: GenerationResult,
    *,
    owner_id: str,
    session_id: str,
    storage_root: Path,
    message_id: int | None = None,
) -> dict:
    """Atomically save validated bytes, then save their private database record."""
    validate_image_review(result.review)
    if result.review.safety_problem:
        raise ImageStorageError("This image did not pass the student safety check.")
    owner_id = _canonical_uuid(owner_id, "image owner")
    _validate_session_id(session_id)
    if message_id is not None and (
        isinstance(message_id, bool) or not isinstance(message_id, int) or message_id < 1
    ):
        raise ImageStorageError("The image message ID is invalid.")
    validate_generated_image(result.image)

    root = Path(storage_root)
    owner_dir = root / owner_id
    _prepare_private_directory(root, 0o700)
    _prepare_private_directory(owner_dir, 0o700)
    remove_orphaned_image_files(
        owner_id=owner_id,
        storage_root=root,
    )

    image_uuid = uuid.uuid4()
    image_id = str(image_uuid)
    extension = IMAGE_EXTENSION_BY_MIME.get(result.image.mime_type)
    if extension is None:
        raise ImageStorageError("This generated image format cannot be stored.")
    local_filename = f"{image_uuid.hex}{extension}"
    target = owner_dir / local_filename
    temporary = owner_dir / f".{image_uuid.hex}.tmp"

    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(result.image.data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        _protect_file(target)
        save_generated_image_record(
            image_id=image_id,
            owner_id=owner_id,
            session_id=session_id,
            message_id=message_id,
            prompt=result.request.student_prompt,
            image_request=asdict(result.request),
            review=asdict(result.review),
            provider=result.image.provider,
            model=result.image.model,
            mime_type=result.image.mime_type,
            width=result.image.width,
            height=result.image.height,
            local_filename=local_filename,
        )
    except (OSError, sqlite3.Error, ImageValidationError, TypeError, ValueError) as error:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        raise ImageStorageError("Delphic could not save the generated image.") from error

    try:
        record = get_generated_image_record(image_id, owner_id)
    except sqlite3.Error as error:
        target.unlink(missing_ok=True)
        raise ImageStorageError("Delphic could not confirm the saved image.") from error
    if record is None:
        pop_generated_image_record(image_id, owner_id)
        target.unlink(missing_ok=True)
        raise ImageStorageError("Delphic could not confirm the saved image.")
    return record


def read_generated_image(
    image_id: str,
    *,
    owner_id: str,
    storage_root: Path,
) -> StoredImage | None:
    """Read and revalidate one image only for its owner."""
    canonical_image_id = _canonical_uuid(image_id, "image ID")
    canonical_owner_id = _canonical_uuid(owner_id, "image owner")
    try:
        record = get_generated_image_record(canonical_image_id, canonical_owner_id)
    except sqlite3.Error as error:
        raise ImageStorageError("Delphic could not read the saved image.") from error
    if record is None or not _has_safe_review(record):
        return None

    try:
        target = _record_path(record, canonical_owner_id, Path(storage_root))
        if target.is_symlink() or not target.is_file():
            return None
        data = target.read_bytes()
        validate_generated_image(_image_from_record(record, data))
    except (OSError, ValueError, TypeError, ImageValidationError, ImageStorageError):
        return None
    return StoredImage(record=record, data=data)


def list_session_images(owner_id: str, session_id: str) -> list[dict]:
    canonical_owner_id = _canonical_uuid(owner_id, "image owner")
    _validate_session_id(session_id)
    try:
        return [
            record for record in list_generated_image_records(canonical_owner_id, session_id)
            if _has_safe_review(record)
        ]
    except sqlite3.Error as error:
        raise ImageStorageError("Delphic could not list saved images.") from error


def delete_generated_image(
    image_id: str,
    *,
    owner_id: str,
    storage_root: Path,
) -> bool:
    canonical_image_id = _canonical_uuid(image_id, "image ID")
    canonical_owner_id = _canonical_uuid(owner_id, "image owner")
    try:
        record = pop_generated_image_record(canonical_image_id, canonical_owner_id)
    except sqlite3.Error as error:
        raise ImageStorageError("Delphic could not delete the saved image.") from error
    if record is None:
        return False
    _delete_record_file(record, canonical_owner_id, Path(storage_root))
    return True


def delete_session_images(
    *,
    owner_id: str,
    session_id: str,
    storage_root: Path,
) -> int:
    canonical_owner_id = _canonical_uuid(owner_id, "image owner")
    _validate_session_id(session_id)
    try:
        records = pop_generated_images_for_session(canonical_owner_id, session_id)
    except sqlite3.Error as error:
        raise ImageStorageError("Delphic could not delete the chat images.") from error
    for record in records:
        _delete_record_file(record, canonical_owner_id, Path(storage_root))
    return len(records)


def public_image_metadata(record: dict) -> dict:
    """Return browser-safe metadata without private paths or internal prompts."""
    if not _has_safe_review(record):
        raise ImageStorageError("This image did not pass the student safety check.")
    image_id = _canonical_uuid(str(record.get("id", "")), "image ID")
    request_data = record.get("image_request") if isinstance(record.get("image_request"), dict) else {}
    review = record.get("review") if isinstance(record.get("review"), dict) else {}
    return {
        "id": image_id,
        "message_id": record.get("message_id"),
        "prompt": str(record.get("prompt", ""))[:1_200],
        "mode": request_data.get("mode"),
        "width": record.get("width"),
        "height": record.get("height"),
        "mime_type": record.get("mime_type"),
        "review_passed": review.get("passed") is True,
        "safety_problem": review.get("safety_problem") is True,
        "created_at": record.get("created_at"),
        "url": f"/images/{image_id}",
        "download_url": f"/images/{image_id}?download=1",
    }


def _has_safe_review(record: dict) -> bool:
    review = record.get("review")
    return isinstance(review, dict) and review.get("safety_problem") is False


def safe_image_download_name(prompt: str, mime_type: str) -> str:
    words = re.sub(r"[^A-Za-z0-9]+", "-", prompt).strip("-").lower()
    stem = words[:55].rstrip("-") or "generated-image"
    extension = IMAGE_EXTENSION_BY_MIME.get(mime_type, ".png")
    return f"delphic-{stem}{extension}"


def remove_orphaned_image_files(
    *,
    owner_id: str,
    storage_root: Path,
    now: float | None = None,
) -> int:
    """Remove old untracked files left by an interrupted save."""
    canonical_owner_id = _canonical_uuid(owner_id, "image owner")
    owner_dir = Path(storage_root) / canonical_owner_id
    if not owner_dir.is_dir() or owner_dir.is_symlink():
        return 0

    try:
        expected = list_generated_image_filenames(canonical_owner_id)
    except sqlite3.Error as error:
        raise ImageStorageError("Delphic could not check private image storage.") from error
    cutoff = (time.time() if now is None else now) - ORPHAN_GRACE_SECONDS
    removed = 0
    try:
        candidates = list(owner_dir.iterdir())
    except OSError:
        return 0
    for candidate in candidates:
        if candidate.is_symlink() or not candidate.is_file() or candidate.name in expected:
            continue
        if not (candidate.suffix == ".png" or candidate.name.endswith(".tmp")):
            continue
        try:
            if candidate.stat().st_mtime > cutoff:
                continue
            candidate.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def _record_path(record: dict, owner_id: str, storage_root: Path) -> Path:
    owner_dir = storage_root / owner_id
    if storage_root.is_symlink() or owner_dir.is_symlink():
        raise ImageStorageError("The saved image path is invalid.")
    filename = str(record.get("local_filename", ""))
    image_id = uuid.UUID(str(record.get("id", "")))
    expected = f"{image_id.hex}{IMAGE_EXTENSION_BY_MIME.get(record.get('mime_type'), '')}"
    if not expected.endswith(tuple(IMAGE_EXTENSION_BY_MIME.values())) or filename != expected:
        raise ImageStorageError("The saved image path is invalid.")
    return owner_dir / filename


def _image_from_record(record: dict, data: bytes) -> GeneratedImage:
    return GeneratedImage(
        data=data,
        mime_type=record.get("mime_type"),
        width=record.get("width"),
        height=record.get("height"),
        provider=record.get("provider"),
        model=record.get("model"),
        request_id=None,
    )


def _delete_record_file(record: dict, owner_id: str, storage_root: Path) -> None:
    try:
        target = _record_path(record, owner_id, storage_root)
        if not target.is_symlink():
            target.unlink(missing_ok=True)
    except (OSError, ValueError, ImageStorageError):
        return


def _canonical_uuid(value: str, label: str) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise ImageStorageError(f"The {label} is invalid.") from error
    canonical = str(parsed)
    if str(value) != canonical:
        raise ImageStorageError(f"The {label} is invalid.")
    return canonical


def _validate_session_id(session_id: str) -> None:
    value = str(session_id)
    if value.startswith("science:"):
        raw_uuid = value.removeprefix("science:")
    elif ":" in value:
        raise ImageStorageError("The image chat ID is invalid.")
    else:
        raw_uuid = value
    try:
        if str(uuid.UUID(raw_uuid)) != raw_uuid:
            raise ValueError
    except ValueError as error:
        raise ImageStorageError("The image chat ID is invalid.") from error


def _prepare_private_directory(path: Path, mode: int) -> None:
    if path.exists() and (path.is_symlink() or not path.is_dir()):
        raise ImageStorageError("The private image folder is not safe to use.")
    try:
        path.mkdir(parents=True, exist_ok=True, mode=mode)
        if os.name != "nt":
            path.chmod(mode)
    except OSError as error:
        raise ImageStorageError("Delphic could not prepare private image storage.") from error


def _protect_file(path: Path) -> None:
    if os.name == "nt":
        return
    path.chmod(0o600)
