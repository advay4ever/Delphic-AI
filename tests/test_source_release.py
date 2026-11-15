"""The curated source archive must be complete, reproducible, and private-data-free."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import zipfile

import pytest

from scripts.check_source_release import verify_archive


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_source_release", ROOT / "packaging/build_source_release.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


@pytest.fixture
def source_tree(tmp_path):
    root = tmp_path / "source with spaces"
    root.mkdir()
    for name in builder.ALLOWED_ROOT_FILES:
        (root / name).write_text("# synthetic fixture\n", encoding="utf-8")
    (root / "VERSION").write_text("0.2.0\n")
    (root / ".env.example").write_text("OPENAI_API_KEY=your-openai-api-key-here\nFLASK_SECRET_KEY=change-me-in-development\n")
    (root / "ai").mkdir()
    (root / "ai/__init__.py").write_text("# synthetic module\n")
    (root / "docs/readmes").mkdir(parents=True)
    (root / "docs/readmes/SOURCE_LAUNCHER_README.md").write_text("# Synthetic instructions\n")
    (root / "packaging").mkdir()
    selection = {"files": sorted([*builder.ALLOWED_ROOT_FILES, "ai/__init__.py"]),
                 "readme": "docs/readmes/SOURCE_LAUNCHER_README.md"}
    (root / builder.MANIFEST_PATH).write_text(json.dumps(selection))
    return root


def test_release_excludes_unselected_private_files_and_has_verified_hashes(source_tree, tmp_path):
    (source_tree / ".env").write_text("private-fixture-not-for-distribution")
    (source_tree / "chat_history.db").write_text("private chat")
    (source_tree / "ai/private-notes.txt").write_text("private note")
    (source_tree / "ai/__pycache__").mkdir()
    (source_tree / "ai/__pycache__/cached.pyc").write_bytes(b"cached")
    archive = builder.build_release(source_tree, tmp_path / "out")
    assert verify_archive(archive)["version"] == "0.2.0"
    checksum = archive.with_suffix(".zip.sha256").read_text().split()[0]
    assert checksum == hashlib.sha256(archive.read_bytes()).hexdigest()
    with zipfile.ZipFile(archive) as bundle:
        names = set(bundle.namelist())
        assert "Delphic AI/run_mac.command" in names
        assert "Delphic AI/run_windows.bat" in names
        assert not any("private" in name or "__pycache__" in name or name.endswith(".db") for name in names)
        assert "Delphic AI/.env" not in names
        metadata = json.loads(bundle.read("Delphic AI/RELEASE_MANIFEST.json"))
        assert metadata["distribution"] == "python-required"
        for name, info in metadata["files"].items():
            contents = bundle.read("Delphic AI/" + name)
            assert info["sha256"] == hashlib.sha256(contents).hexdigest()
            assert info["bytes"] == len(contents)
        assert len(names) == len(metadata["files"]) + 1
        assert (bundle.getinfo("Delphic AI/run_mac.command").external_attr >> 16) & 0o111


def test_same_source_produces_the_same_archive(source_tree, tmp_path):
    first = builder.build_release(source_tree, tmp_path / "first")
    second = builder.build_release(source_tree, tmp_path / "second")
    assert first.read_bytes() == second.read_bytes()


def test_damaged_archive_is_rejected_before_extraction(source_tree, tmp_path):
    archive = builder.build_release(source_tree, tmp_path / "out")
    with archive.open("ab") as target:
        target.write(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        verify_archive(archive)


def test_added_archive_entries_are_rejected_even_with_a_new_checksum(source_tree, tmp_path):
    archive = builder.build_release(source_tree, tmp_path / "out")
    with zipfile.ZipFile(archive, "a") as bundle:
        bundle.writestr("../outside.py", "not allowed")
    archive.with_suffix(".zip.sha256").write_text(f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n")
    with pytest.raises(ValueError, match="unsafe"):
        verify_archive(archive)


def test_existing_download_cannot_be_overwritten(source_tree, tmp_path):
    archive = builder.build_release(source_tree, tmp_path / "out")
    original = archive.read_bytes()
    with pytest.raises(builder.ReleaseBuildError, match="already exist"):
        builder.build_release(source_tree, tmp_path / "out")
    assert archive.read_bytes() == original


@pytest.mark.parametrize("name", ["../outside.py", "ai/../../outside.py", "ai/.env", "ai/cache.pyc", "ai/__pycache__/module.py", "database.db", "static/private.txt"])
def test_unsafe_or_private_manifest_paths_are_rejected(source_tree, tmp_path, name):
    manifest = source_tree / builder.MANIFEST_PATH
    selection = json.loads(manifest.read_text())
    selection["files"].append(name)
    manifest.write_text(json.dumps(selection))
    with pytest.raises(builder.ReleaseBuildError):
        builder.build_release(source_tree, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_missing_runtime_file_stops_the_build(source_tree, tmp_path):
    (source_tree / "app.py").unlink()
    with pytest.raises(builder.ReleaseBuildError, match="not found"):
        builder.build_release(source_tree, tmp_path / "out")


def test_possible_credentials_stop_the_build_without_printing_them(source_tree, tmp_path):
    fake_key = "sk-proj-" + "syntheticcredential" * 3
    (source_tree / "app.py").write_text(f'key = "{fake_key}"\n')
    with pytest.raises(builder.ReleaseBuildError) as error:
        builder.build_release(source_tree, tmp_path / "out")
    assert "app.py" in str(error.value)
    assert fake_key not in str(error.value)


def test_nonplaceholder_settings_stop_the_build(source_tree, tmp_path):
    (source_tree / ".env.example").write_text("OPENROUTER_API_KEY=not-a-placeholder\n")
    with pytest.raises(builder.ReleaseBuildError, match="non-placeholder"):
        builder.build_release(source_tree, tmp_path / "out")


@pytest.mark.skipif(os.name == "nt", reason="Symlink creation may need Windows privileges")
def test_symlink_cannot_smuggle_an_external_file(source_tree, tmp_path):
    outside = tmp_path / "private.py"
    outside.write_text("private data")
    (source_tree / "ai/__init__.py").unlink()
    (source_tree / "ai/__init__.py").symlink_to(outside)
    with pytest.raises(builder.ReleaseBuildError, match="Symbolic links"):
        builder.build_release(source_tree, tmp_path / "out")


def test_actual_manifest_contains_every_current_runtime_file():
    selection = json.loads((ROOT / builder.MANIFEST_PATH).read_text())
    names = set(selection["files"])
    assert builder.ALLOWED_ROOT_FILES <= names
    for folder in builder.RUNTIME_ROOTS:
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and not path.name.startswith("."):
                if path.suffix in builder.ALLOWED_SUFFIXES or path.name == "LICENSE":
                    assert path.relative_to(ROOT).as_posix() in names
    for name in names:
        assert (ROOT / name).is_file()
