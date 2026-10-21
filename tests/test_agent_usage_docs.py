"""Source-checkout documentation checks, not host skill activation or image trials."""
from __future__ import annotations

from html import unescape
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
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


LANGUAGE_PAIRS = (
    ("README.md", "README.zh-CN.md"),
    ("docs/usage.md", "docs/usage.zh-CN.md"),
    ("examples/art-pilot/README.en.md", "examples/art-pilot/README.md"),
    ("examples/art-pilot/docs/runbook.en.md", "examples/art-pilot/docs/runbook.md"),
)
GUIDE_PAIRS = (
    ("docs/getting-started.md", "docs/getting-started.zh-CN.md"),
    ("docs/agent-setup.md", "docs/agent-setup.zh-CN.md"),
    ("docs/concepts.md", "docs/concepts.zh-CN.md"),
)


def without_code_blocks(source):
    lines = []
    fence = None
    for line in source.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            lines.append("")
        elif marker:
            fence = marker[1]
            lines.append("")
        else:
            lines.append("" if line.startswith(("    ", "\t")) else line)
    return "\n".join(lines)


def markdown_links(source):
    source = without_code_blocks(source)
    source = re.sub(r"(`+).*?\1", "", source)
    inline = re.findall(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", source)
    references = re.findall(r"^ {0,3}\[[^\]]+\]:\s*(\S+)", source, re.MULTILINE)
    return [destination.strip("<>") for destination in inline + references]


def markdown_anchors(source):
    anchors = set()
    previous = ""
    for line in without_code_blocks(source).splitlines():
        heading = re.match(r"^ {0,3}#{1,6}(?:\s+(.*)|\s*)$", line)
        title = re.sub(r"\s+#+\s*$", "", heading[1] or "").strip() if heading else None
        if title is None and previous.strip() and re.fullmatch(r" {0,3}(?:=+|-+)\s*", line):
            title = previous.strip()
        previous = line
        if title is None:
            continue
        title = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", title)
        title = re.sub(
            r"(`+)(.*?)\1|(?<!\w)(_+)(.+?)\3(?!\w)",
            lambda match: match[2] if match[1] else match[4], title,
        )
        title = unescape(re.sub(r"<[^>]+>", "", title)).lower()
        slug = "".join(
            char for char in title
            if char in "-_" or not unicodedata.category(char).startswith(("P", "S"))
        ).replace(" ", "-")
        anchor = slug
        suffix = 0
        while anchor in anchors:
            suffix += 1
            anchor = f"{slug}-{suffix}"
        anchors.add(anchor)
    return anchors


def test_markdown_anchors_handle_formatting_code_and_duplicates():
    source = '''# Hello, `API` & **world**! ###
## 中文：使用 [指南](usage.md)
## _Emphasis_ and `_literal_` &amp; <em>HTML</em>
Setext title
------------
## Repeat
## Repeat
## Repeat-1
## Repeat
```markdown
# Not a heading
[not a link](missing.md)
```
~~~text
## Also not a heading
~~~
    # Indented code
`[inline code](missing.md)`
[local](#repeat-3)
[guide]: usage.md#中文
'''
    assert markdown_anchors(source) == {
        "hello-api--world", "中文使用-指南", "setext-title",
        "emphasis-and-_literal_--html",
        "repeat", "repeat-1", "repeat-1-1", "repeat-2",
    }
    assert markdown_links(source) == ["usage.md", "#repeat-3", "usage.md#中文"]


@pytest.mark.parametrize("relative", [
    "AGENTS.md", "llms.txt", "skills/maliang-art/SKILL.md", "CONTRIBUTING.md",
    *(relative for pair in LANGUAGE_PAIRS + GUIDE_PAIRS for relative in pair),
])
def test_repository_document_links(relative):
    document = ROOT / relative
    assert document.is_file(), relative
    for destination in markdown_links(text(document)):
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc:
            continue
        target = (document.parent / unquote(parsed.path)).resolve() if parsed.path else document
        assert target.is_relative_to(ROOT.resolve()), (relative, destination)
        assert target.exists(), (relative, destination)
        if parsed.fragment and target.suffix == ".md" and not target.is_relative_to(ROOT / "docs/compose/spec"):
            assert unquote(parsed.fragment) in markdown_anchors(text(target)), (relative, destination)


@pytest.mark.parametrize("pair", LANGUAGE_PAIRS + GUIDE_PAIRS)
def test_language_pairs_link_back_at_the_top(pair):
    for relative, counterpart in (pair, pair[::-1]):
        document = ROOT / relative
        destinations = {
            (document.parent / unquote(urlsplit(link).path)).resolve()
            for link in markdown_links("\n".join(text(document).splitlines()[:12]))
            if not urlsplit(link).scheme and not urlsplit(link).netloc
        }
        assert ROOT / counterpart in destinations, (relative, counterpart)


@pytest.mark.parametrize("pair", LANGUAGE_PAIRS + GUIDE_PAIRS)
def test_language_pairs_keep_executable_examples_in_sync(pair):
    blocks = [
        re.findall(r"^```[^\n]*\n(.*?)^```\s*$", text(ROOT / relative), re.MULTILINE | re.DOTALL)
        for relative in pair
    ]
    assert blocks[0] == blocks[1], pair


@pytest.mark.parametrize("locale", ["en", "zh-CN"])
def test_root_readmes_are_short_and_route_to_matching_language(locale):
    readme, usage, sample, runbook = (
        (pair[0] if locale == "en" else pair[1]) for pair in LANGUAGE_PAIRS
    )
    source = text(ROOT / readme)
    assert len(source.splitlines()) <= 90
    destinations = {urlsplit(link).path for link in markdown_links(source)}
    assert {usage, sample, runbook} <= destinations
    guides = {(pair[0] if locale == "en" else pair[1]) for pair in GUIDE_PAIRS}
    assert guides <= destinations


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


def test_agents_md_routes_usage_to_skill_before_development_rules():
    head = "\n".join(text(ROOT / "AGENTS.md").splitlines()[:10])
    assert "skills/maliang-art/SKILL.md" in markdown_links(head)
    assert "work/" in head and "development rules" in head.lower()


def test_user_workspace_is_ignored_by_git():
    assert "/work/" in text(ROOT / ".gitignore").splitlines()


def test_skill_triggers_on_conversation_intent_and_announces_route():
    frontmatter, body = text(SKILL).split("---", 2)[1:]
    description = yaml.safe_load(frontmatter)["description"]
    assert "earlier in the conversation" in description
    assert "earlier in this conversation" in body
    assert "Before calling any image tool" in body
    assert "never switch silently to a plain image tool" in body


def test_skill_routes_concept_track_and_camera_modes():
    skill = text(ROOT / "skills/maliang-art/SKILL.md")
    assert "concept review" in skill and "--format questions" in skill
    assert "0.2" in skill
    for mode in ("isometric", "side", "top-down", "front"):
        assert mode in skill
    assert "gate" in skill
