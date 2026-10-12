"""Source-checkout documentation checks, not host skill activation or image trials."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/maliang-art/SKILL.md"
pytestmark = pytest.mark.skipif(
    not (ROOT / ".git").exists() and not SKILL.is_file(),
    reason="repository-only skill and runbook are not shipped in sdist",
)


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_skill_structure_and_portable_root():
    source = text(SKILL)
    frontmatter, body = source.split("---", 2)[1:]
    metadata = yaml.safe_load(frontmatter)
    assert set(metadata) == {"name", "description"}
    assert metadata["name"] == SKILL.parent.name == "maliang-art"
    assert 0 < len(metadata["description"]) < 1024
    assert "<" not in frontmatter and ">" not in frontmatter
    for heading in ("Quick Reference", "When to use", "Workflow", "Installation and discovery", "Checklist"):
        assert f"## {heading}" in body
    assert len(body.split()) < 5000
    assert "../../" not in source
    assert "explicit **MaLiang project root**" in body
    assert "If missing, ask" in body
    assert "not paths relative to this installed skill" in body
    assert "Do not auto-install" in body
    assert "Static documentation tests" in body
    assert not (SKILL.parent / "README.md").exists()
    assert list((ROOT / "skills").rglob("SKILL.md")) == [SKILL]


@pytest.mark.parametrize("locale", ["en-US", "zh-CN"])
def test_skill_display_metadata(locale):
    metadata = json.loads(text(SKILL.parent / "locales" / f"{locale}.json"))
    assert set(metadata) == {"displayName", "brief"}
    assert all(isinstance(value, str) and value.strip() for value in metadata.values())


@pytest.mark.parametrize("relative", [
    "AGENTS.md", "llms.txt", "README.md", "README.zh-CN.md",
    "skills/maliang-art/SKILL.md", "examples/art-pilot/README.md",
    "examples/art-pilot/docs/runbook.md",
])
def test_repository_document_links(relative):
    document = ROOT / relative
    assert document.is_file(), relative
    for destination in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", text(document)):
        parsed = urlsplit(destination.strip("<>"))
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        target = (document.parent / unquote(parsed.path)).resolve()
        assert target.is_relative_to(ROOT.resolve()), (relative, destination)
        assert target.exists(), (relative, destination)


def test_navigation_is_short_and_plans_are_nonfunctional():
    navigation = text(ROOT / "llms.txt")
    assert len(navigation.splitlines()) <= 50
    assert "v0.1.0" in navigation
    assert "not an image-generation service" in navigation
    heading = "## Optional design plans — nonfunctional references"
    main, plans = navigation.split(heading)
    assert "docs/compose/spec/" not in main
    assert "planned bridge, not an implemented API" in plans
    for relative in (
        "README.md", "src/maliang_art/cli.py", "src/maliang_art/__init__.py",
        "skills/maliang-art/SKILL.md", "examples/art-pilot/docs/runbook.md",
        "examples/art-pilot/scripts/production.py", "SECURITY.md",
    ):
        assert f"]({relative})" in navigation


def test_skill_repository_resource_paths_exist():
    source = text(SKILL)
    for relative in (
        "README.md", "pyproject.toml", "src/maliang_art",
        "examples/art-pilot/README.md", "examples/art-pilot/docs/runbook.md",
        "examples/art-pilot/scripts/production.py",
    ):
        assert relative in source
        assert (ROOT / relative).exists()


@pytest.mark.parametrize(("scenario", "required_guidance"), [
    ("development-no-generation", (
        "Do not use for developing MaLiang", "development guidance",
        "with no generation",
    )),
    ("zero-to-one", (
        "empty references", "require neither an existing character image",
        "nor a model sheet", "not a mandatory design stage",
    )),
    ("preserve-source-edits", (
        "Never overwrite", "keep source bytes and identity unchanged",
        "--parent", "--instruction", "first `edit-source`",
    )),
    ("absent-image-inputs", (
        "tools actually exposed", "An image path in prompt text is not",
        "an image attachment", "stop at\npreparation", "do not switch to text-only",
    )),
    ("mismatched-result", (
        "Reject a mismatched result", "must not be bound as success",
        "preparedEventId", "artifactSha256", "Never fabricate receipts",
    )),
    ("no-human-approval", (
        "show its image and artifact path", "real reviewer",
        "do not adopt", "Synthetic human fixtures are test data, never real approval",
        "agent cannot be the human reviewer",
    )),
])
def test_six_review_scenarios_have_explicit_guidance(scenario, required_guidance):
    """Guard reviewed instructions only; this does not simulate an agent or a host."""
    source = text(SKILL)
    for phrase in required_guidance:
        assert phrase in source, (scenario, phrase)


def test_execution_and_evidence_boundaries():
    source = text(SKILL)
    for phrase in (
        "host provides image", "planned, not implemented", "manually\ntested",
        "not a MaLiang command", "Never read subscription tokens or use an API fallback",
        "`unknown`", "`attested`", "hand-written receipt alone proves no call",
    ):
        assert phrase in source
    assert "python -m maliang_art production" not in source


@pytest.mark.parametrize("command", ["validate", "compile"])
def test_documented_design_commands_really_exist(command):
    result = subprocess.run(
        [sys.executable, "-m", "maliang_art", "design", command, "--help"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "--contract" in result.stdout and "--draft" in result.stdout
    if command == "compile":
        assert "--output-dir" in result.stdout


@pytest.mark.parametrize("command,flags", [
    ("prepare", ["--contract", "--draft", "--design", "--parameters", "--parent", "--instruction"]),
    ("acceptance", ["--contract", "--draft", "--design"]),
    ("complete", ["--receipt", "--image"]),
    ("fail", ["--category", "--message"]),
    ("import", ["--provenance", "--image"]),
    ("technical", ["--attempt"]),
    ("review", ["--decision-file"]),
    ("adopt", ["--review", "--result", "--asset"]),
])
def test_documented_sample_commands_really_exist(command, flags, tmp_path):
    script = ROOT / "examples/art-pilot/scripts/production.py"
    result = subprocess.run(
        [sys.executable, "-I", str(script), "--project", str(tmp_path), command, "--help"],
        cwd=tmp_path, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert all(flag in result.stdout for flag in flags)
    assert list(tmp_path.iterdir()) == []


def test_usage_resources_have_mit_reuse_coverage():
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib
    config = tomllib.loads(text(ROOT / "REUSE.toml"))
    mit_paths = {
        path
        for annotation in config["annotations"]
        if annotation["SPDX-License-Identifier"] == "MIT"
        for path in annotation["path"]
    }
    assert {"*.md", "llms.txt", "skills/**", "tests/**"} <= mit_paths
