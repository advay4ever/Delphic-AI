"""Read Delphic AI's version from its single version file."""

from __future__ import annotations

import re
import sys
from pathlib import Path


VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def bundled_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def load_app_version(version_file: Path | None = None) -> str:
    path = version_file or bundled_root() / "VERSION"
    try:
        version = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError(f"Delphic AI version file is missing: {path}") from exc
    if not VERSION_PATTERN.fullmatch(version):
        raise RuntimeError(f"Delphic AI has an invalid version: {version!r}")
    return version


APP_VERSION = load_app_version()
