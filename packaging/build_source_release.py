"""Build a curated Python-required download, never a whole-project archive."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "Delphic AI"
MANIFEST_PATH = "packaging/source-release-files.json"
SECRET_PATTERNS = (
    re.compile(rb"(?<![A-Za-z0-9_-])sk-(?:proj-|or-v1-|ant-)?[A-Za-z0-9_-]{24,}"),
    re.compile(rb"\bgsk_[A-Za-z0-9]{24,}"),
    re.compile(rb"\bAIza[A-Za-z0-9_-]{30,}"),
    re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
)
ALLOWED_ROOT_FILES = {
    ".env.example", "VERSION", "app.py", "database.py", "requirements.txt",
    "run_app.py", "run_mac.command", "run_windows.bat", "version.py",
}
RUNTIME_ROOTS = {"ai", "images", "science", "static", "templates"}
FORBIDDEN_PARTS = {"__pycache__", ".git", ".venv", "node_modules", "generated_images"}
ALLOWED_SUFFIXES = {".py", ".json", ".js", ".css", ".html", ".png", ".svg", ".woff", ".woff2", ".ttf", ".md"}


class ReleaseBuildError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected_file(root: Path, name: str, *, readme: bool = False) -> bytes:
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or ".." in path.parts or "\\" in name
            or str(path) != name or FORBIDDEN_PARTS.intersection(path.parts)):
        raise ReleaseBuildError(f"Unsafe release path: {name}")
    if not readme and name not in ALLOWED_ROOT_FILES:
        if path.parts[0] not in RUNTIME_ROOTS or (
            path.suffix not in ALLOWED_SUFFIXES and path.name != "LICENSE"
        ):
            raise ReleaseBuildError(f"File is outside the runtime allowlist: {name}")
        if any(part.startswith(".") for part in path.parts):
            raise ReleaseBuildError(f"Hidden runtime file is not allowed: {name}")
    source = root / name
    if any(parent.is_symlink() for parent in (source, *source.parents) if parent != root.parent):
        raise ReleaseBuildError(f"Symbolic links are not allowed: {name}")
    if not source.is_file():
        raise ReleaseBuildError(f"Required release file was not found: {name}")
    data = source.read_bytes()
    if any(pattern.search(data) for pattern in SECRET_PATTERNS):
        raise ReleaseBuildError(f"Possible credential in {name}; no archive was created.")
    if name == ".env.example":
        for line in data.decode("utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and (key.endswith("_API_KEY") or key == "FLASK_SECRET_KEY"):
                value = value.strip()
                if value and not value.startswith("your-") and value != "change-me-in-development":
                    raise ReleaseBuildError("The settings template contains a non-placeholder credential.")
    return data


def source_identity(root: Path, paths: list[str]) -> dict:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True,
            check=True, timeout=10,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", *paths],
            cwd=root, capture_output=True, text=True, check=True, timeout=10,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {"commit": None, "uncommitted_release_files": None}
    return {"commit": commit, "uncommitted_release_files": bool(status.strip())}


def build_release(root: Path, output_dir: Path) -> Path:
    root = root.resolve()
    selection = json.loads((root / MANIFEST_PATH).read_text(encoding="utf-8"))
    names = selection["files"]
    if not isinstance(names, list) or any(not isinstance(name, str) for name in names):
        raise ReleaseBuildError("The release file list must contain file names.")
    if len(set(names)) != len(names) or not ALLOWED_ROOT_FILES.issubset(names):
        raise ReleaseBuildError("The release file list has duplicate or missing core files.")
    files = {name: selected_file(root, name) for name in names}
    readme = selection["readme"]
    if readme != "docs/readmes/SOURCE_LAUNCHER_README.md":
        raise ReleaseBuildError("The release instructions must use the source-launcher guide.")
    files["README.md"] = selected_file(root, readme, readme=True)
    version = files["VERSION"].decode("ascii").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ReleaseBuildError("VERSION must look like 1.2.3.")
    manifest = {
        "version": version,
        "distribution": "python-required",
        "source": source_identity(root, [*names, readme, MANIFEST_PATH, "packaging/build_source_release.py"]),
        "files": {name: {"sha256": digest(data), "bytes": len(data)} for name, data in sorted(files.items())},
    }
    files["RELEASE_MANIFEST.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    archive = output_dir / f"Delphic-AI-v{version}-Python.zip"
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    if archive.exists() or checksum.exists():
        raise ReleaseBuildError("Release files already exist; use a new output folder or an approved new version.")
    created_archive = False
    try:
        with archive.open("xb") as target:
            created_archive = True
            with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
                for name, data in sorted(files.items()):
                    entry = zipfile.ZipInfo(f"{PACKAGE_NAME}/{name}", date_time=(1980, 1, 1, 0, 0, 0))
                    entry.create_system = 3
                    mode = 0o755 if name == "run_mac.command" else 0o644
                    entry.external_attr = (0o100000 | mode) << 16
                    entry.compress_type = zipfile.ZIP_DEFLATED
                    bundle.writestr(entry, data)
        with checksum.open("x", encoding="ascii", newline="\n") as target:
            target.write(f"{digest(archive.read_bytes())}  {archive.name}\n")
    except Exception:
        if created_archive:
            archive.unlink(missing_ok=True)
        raise
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist" / "candidates")
    args = parser.parse_args()
    try:
        archive = build_release(ROOT, args.output_dir)
    except (ReleaseBuildError, OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Cannot build the download: {error}\n")
    print(f"Created candidate: {archive}")
    print(f"Checksum: {archive}.sha256")
    print("This is not a published release. Check the manifest and test the extracted download first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
