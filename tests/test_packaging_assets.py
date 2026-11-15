from pathlib import Path

import pytest

import desktop_launcher
from version import APP_VERSION, load_app_version


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_legacy_corpus_is_not_bundled_and_personal_library_is_available():
    spec = (PROJECT_ROOT / "delphic_desktop.spec").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "packaging" / "build_mac_source_release.sh").read_text(encoding="utf-8")
    requirements = (PROJECT_ROOT / "requirements.txt").read_text(encoding="utf-8")

    assert "corpus" not in spec
    assert "corpus" not in script
    # Both attachments and personal-library previews use the document parsers.
    assert "pypdf" in requirements
    assert "python-docx" in requirements
    assert not (PROJECT_ROOT / "ai" / "corpus.py").exists()
    assert not (PROJECT_ROOT / "images" / "context.py").exists()
    assert (PROJECT_ROOT / "ai" / "study_library.py").is_file()
    assert (PROJECT_ROOT / "templates" / "_study_library.html").is_file()
    assert (PROJECT_ROOT / "static" / "study-library.js").is_file()



def test_desktop_packages_include_the_local_work_checker():
    spec = (PROJECT_ROOT / "delphic_desktop.spec").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "packaging" / "build_mac_source_release.sh").read_text(
        encoding="utf-8"
    )

    assert 'collect_submodules("ai")' in spec
    assert 'cp -R "$project_dir/ai/." "$package_dir/ai/"' in script
    assert (PROJECT_ROOT / "ai" / "work_checker.py").is_file()


def test_desktop_packages_include_the_safe_math_boundary():
    spec = (PROJECT_ROOT / "delphic_desktop.spec").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "packaging" / "build_mac_source_release.sh").read_text(encoding="utf-8")
    assert 'collect_submodules("ai")' in spec
    assert 'cp -R "$project_dir/ai/." "$package_dir/ai/"' in script
    assert (PROJECT_ROOT / "ai" / "safe_math.py").is_file()


def test_desktop_packages_include_the_image_generation_foundation():
    spec = (PROJECT_ROOT / "delphic_desktop.spec").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "packaging" / "build_mac_source_release.sh").read_text(
        encoding="utf-8"
    )

    assert 'collect_submodules("images")' in spec
    assert '("images/evaluation_cases.json", "images")' in spec
    assert 'cp -R "$project_dir/images/." "$package_dir/images/"' in script
    assert (PROJECT_ROOT / "images" / "service.py").is_file()
    assert (PROJECT_ROOT / "images" / "evaluation_cases.json").is_file()



def test_desktop_packages_include_local_science_diagrams():
    spec = (PROJECT_ROOT / "delphic_desktop.spec").read_text(encoding="utf-8")
    script = (PROJECT_ROOT / "packaging" / "build_mac_source_release.sh").read_text(encoding="utf-8")

    assert 'collect_submodules("science")' in spec
    assert 'cp -R "$project_dir/science/." "$package_dir/science/"' in script
    assert (PROJECT_ROOT / "static" / "science-diagrams.js").is_file()




def test_version_file_is_the_shared_application_version():
    assert APP_VERSION == (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert APP_VERSION.count(".") == 2


def test_invalid_version_file_is_rejected(tmp_path):
    version_file = tmp_path / "VERSION"
    version_file.write_text("newest", encoding="utf-8")

    with pytest.raises(RuntimeError, match="invalid version"):
        load_app_version(version_file)


def test_desktop_spec_bundles_and_reads_the_shared_version():
    spec = (PROJECT_ROOT / "delphic_desktop.spec").read_text(encoding="utf-8")

    assert '("VERSION", ".")' in spec
    assert 'Path(SPECPATH) / "VERSION"' in spec
    assert '"CFBundleShortVersionString": APP_VERSION' in spec
    assert '"CFBundleVersion": APP_VERSION' in spec
    assert '"0.1.8"' not in spec


def test_mac_release_script_builds_and_smoke_tests_a_dmg():
    script = (PROJECT_ROOT / "packaging" / "build_mac_release.sh").read_text(encoding="utf-8")

    assert '"$python_bin" -m pytest -q' in script
    assert "npm run test:e2e" in script
    assert '"$python_bin" -m PyInstaller --clean --noconfirm' in script
    assert "DELPHIC_HEADLESS=true" in script
    assert 'curl -fsS "http://127.0.0.1:$smoke_port/science"' in script
    assert "hdiutil create" in script
    assert "notarytool submit" in script
    assert "stapler staple" in script


def test_mac_source_release_uses_and_includes_shared_version():
    script = (PROJECT_ROOT / "packaging" / "build_mac_source_release.sh").read_text(encoding="utf-8")

    assert 'project_dir/VERSION' in script
    assert 'cp "$project_dir/VERSION" "$package_dir/VERSION"' in script
    assert 'cp "$project_dir/version.py" "$package_dir/version.py"' in script


def test_portfolio_demo_package_covers_the_real_product_and_privacy_rules():
    demo_dir = PROJECT_ROOT / "docs" / "demo"
    script = (demo_dir / "DEMO_SCRIPT.md").read_text(encoding="utf-8")
    checklist = (demo_dir / "RECORDING_CHECKLIST.md").read_text(encoding="utf-8")
    portfolio_copy = (demo_dir / "PORTFOLIO_COPY.md").read_text(encoding="utf-8")

    for required_demo_topic in (
        "Step-by-Step Mode",
        "2D graph",
        "3D graph",
        "science diagram",
        "HTML",
    ):
        assert required_demo_topic.lower() in script.lower()

    assert "API key" in checklist
    assert "captions" in checklist
    assert "Honest Current Boundaries" in portfolio_copy


def test_busy_desktop_port_has_a_readable_error(monkeypatch):
    def fail_to_bind(*_args, **_kwargs):
        # Werkzeug converts its socket bind error into SystemExit.
        raise SystemExit(1)

    monkeypatch.setattr(desktop_launcher, "BoundedDesktopServer", fail_to_bind)

    with pytest.raises(desktop_launcher.DesktopLaunchError, match="Close another copy"):
        desktop_launcher.start_local_server(object(), 5001)
