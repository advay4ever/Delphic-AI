"""Keep a few concrete README claims synchronized without importing the app."""

import ast
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "docs/readmes/PROJECT_README.md").read_text()


def source_tree(relative):
    return ast.parse((ROOT / relative).read_text())


def assigned_value(tree, name):
    return next(node.value for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == name for target in node.targets))


def test_readme_default_models_match_configuration_not_a_live_catalog():
    configured = assigned_value(source_tree("ai/service.py"), "SUPPORTED_AI_PROVIDERS")
    expected = {}
    for config in configured.values:
        fields = {ast.literal_eval(key): value for key, value in zip(config.keys, config.values)}
        expected[ast.literal_eval(fields["label"])] = ast.literal_eval(fields["model"])
    section = README.split("### Default AI models\n", 1)[1].split("### Installation\n", 1)[0]
    documented = dict(re.findall(r"^\| ([^|]+?) \| `([^`]+)` \|$", section, re.MULTILINE))
    assert documented == expected


def test_readme_routes_exist_in_source():
    routes = set()
    for node in ast.walk(source_tree("app.py")):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "route" and node.args
                and isinstance(node.args[0], ast.Constant)):
            routes.add(node.args[0].value)
    section = README.split("## Main Routes\n", 1)[1].split("## Project Structure\n", 1)[0]
    documented = {value.split()[-1] for value in re.findall(r"`([^`]+)`", section)
                  if value.split()[-1].startswith("/")}
    assert documented
    assert documented <= routes


def test_readme_output_and_note_limits_match_source():
    output = ast.literal_eval(assigned_value(source_tree("ai/service.py"), "TUTOR_MAX_OUTPUT_TOKENS"))
    notes = ast.literal_eval(assigned_value(source_tree("ai/study_library.py"), "MAX_NOTE_TEXT"))
    assert f"{output:,}-token tutor output budget" in README
    assert f"60 to {notes:,} characters per note" in README


def test_readme_browser_server_description_matches_configuration():
    config = (ROOT / "playwright.config.js").read_text()
    assert 'process.env.DELPHIC_TEST_PORT || "5004"' in config
    assert "reuseExistingServer: false" in config
    assert "isolated server on port `5004`" in README
    assert "refuses to reuse an existing server" in README
    assert "DELPHIC_TEST_PORT=5004 npm run test:e2e" in README
