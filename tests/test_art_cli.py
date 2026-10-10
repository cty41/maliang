import json
import os
import subprocess
import sys
import pytest

from maliang_art import cli
from maliang_art.authoring import ConstructionPacket, compile_design
from maliang_art.core import canonical_bytes


@pytest.fixture
def design_files(tmp_path):
    contract = {
        "schemaVersion": 1, "familyId": "cli-synthetic",
        "camera": {"mode": "isometric", "profile": {"North": "UL", "South": "DR", "East": "UL+flipX", "West": "DR+flipX"}, "mirrorAccepted": True},
        "silhouettes": ["capsule", "ball"], "attachments": [],
        "drawingRules": [{"id": "style", "instruction": "Readable toy-like form", "method": "human", "required": True}],
        "paletteRoles": {"main": "#8899AA", "secondary": "#334455", "outline": "#112233", "accent": "#EECC44"},
        "targets": {"sourceSize": [96, 96], "outputSize": [64, 64], "anchorX": 48, "groundY": 80, "displaySizes": [64], "contextBoard": {"cellSize": [128, 128], "columns": 4}, "tolerance": 2},
        "variants": [{"id": "neutral", "coreWidth": 0.3, "coreHeight": 0.5}, {"id": "wide", "coreWidth": 0.4, "coreHeight": 0.5}],
        "statePolicy": {"allowedCoreTransforms": ["upright"], "allowedPartChanges": ["folded"]},
    }
    draft = {
        "schemaVersion": 1,
        "identity": {"species": "synthetic ball", "features": ["striped face"], "priority": ["striped face"], "forbiddenMirror": []},
        "topology": {"core": "body", "parts": [], "prohibited": []},
        "silhouetteClass": "ball",
        "visualMoment": [{"view": "DR", "state": "Idle", "moment": "resting upright", "coreTransform": "upright", "partChanges": ["folded"]}],
        "paletteRoles": {}, "targets": {}, "references": [],
    }
    paths = (tmp_path / "contract.json", tmp_path / "draft.json")
    for path, value in zip(paths, (contract, draft)):
        path.write_bytes(canonical_bytes(value))
    return contract, draft, paths


def arguments(command, paths, output=None):
    args = ["design", command, "--contract", str(paths[0]), "--draft", str(paths[1])]
    if output is not None:
        args.extend(["--output-dir", str(output)])
    return args


def run_cli(args):
    return subprocess.run([sys.executable, "-m", "maliang_art", *args], capture_output=True, text=True, encoding="utf-8")


def test_validate_valid_black_box(design_files):
    result = run_cli(arguments("validate", design_files[2]))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"valid": True, "diagnostics": []}
    assert result.stderr == ""


@pytest.mark.parametrize("command", ["validate", "compile"])
@pytest.mark.parametrize("invalid", ["incomplete", "unsupported", "malformed", "missing-file", "invalid-reference"])
def test_invalid_design_json_diagnostics(design_files, tmp_path, command, invalid):
    _, draft, paths = design_files
    if invalid == "incomplete":
        paths[1].write_text('{"schemaVersion":1}', encoding="utf-8")
        expected = "draft.identity"
    elif invalid == "unsupported":
        draft["silhouetteClass"] = "triangle"
        paths[1].write_bytes(canonical_bytes(draft))
        expected = "draft.silhouetteClass"
    elif invalid == "invalid-reference":
        draft["references"] = [{"path": "../outside.png", "sha256": "a" * 64, "roles": ["style"], "borrow": ["colors"], "forbid": ["identity"]}]
        paths[1].write_bytes(canonical_bytes(draft))
        expected = "draft.references[0].path"
    elif invalid == "malformed":
        paths[1].write_text("{", encoding="utf-8")
        expected = "draft"
    else:
        paths[1].unlink()
        expected = "draft"
    output = tmp_path / "packet"
    result = run_cli(arguments(command, paths, output if command == "compile" else None))
    assert result.returncode != 0
    report = json.loads(result.stdout)
    assert report["valid"] is False
    assert any(item["path"] == expected for item in report["diagnostics"])
    assert all(set(item) == {"path", "code", "message"} and item["message"] for item in report["diagnostics"])
    assert not output.exists()
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("debug", [False, True])
def test_compile_stable_immutable_packet(design_files, tmp_path, debug):
    _, _, paths = design_files
    output = tmp_path / "packet"
    args = arguments("compile", paths, output)
    if debug:
        args.append("--debug-geometry")
    first = run_cli(args)
    assert first.returncode == 0, first.stderr
    packet = compile_design(*(json.loads(path.read_text(encoding="utf-8")) for path in paths), debug_geometry=debug)
    assert (output / "design.json").read_bytes() == packet.json_bytes
    assert bool(packet.guides) is debug
    if debug:
        assert all(item["usage"] == "not-generation-input" for item in packet.document["debugArtifacts"])
    else:
        assert not (output / "guides").exists()
    assert packet.document["imageInputs"] == []
    for relative, data in packet.guides.items():
        assert (output / relative).read_bytes() == data
    snapshot = {p.relative_to(output): (p.read_bytes(), p.stat().st_mtime_ns) for p in output.rglob("*") if p.is_file()}
    second = run_cli(args)
    assert second.returncode == 0, second.stderr
    assert second.stdout == first.stdout
    assert snapshot == {p.relative_to(output): (p.read_bytes(), p.stat().st_mtime_ns) for p in output.rglob("*") if p.is_file()}
    document = json.loads((output / "design.json").read_text(encoding="utf-8"))
    assert document["execution"]["status"] == "not-executed"
    assert document["artDecision"]["status"] == "pending"
    assert all(item["status"] == "pending" for item in document["acceptance"])


@pytest.mark.parametrize("relative", ["design.json", "guides/neutral-DR.png"])
def test_default_compile_preserves_existing_bytes(design_files, tmp_path, relative):
    output = tmp_path / "packet"
    destination = output / relative
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing unrelated bytes")
    result = run_cli(arguments("compile", design_files[2], output))
    if relative == "design.json":
        assert result.returncode != 0
        assert "collision" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["guides"] == []
    assert destination.read_bytes() == b"existing unrelated bytes"
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("relative", ["design.json", "guides/neutral-DR.png"])
def test_debug_compile_collision_preserves_existing_bytes(design_files, tmp_path, relative):
    output = tmp_path / "packet"
    destination = output / relative
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"existing unrelated bytes")
    result = run_cli(arguments("compile", design_files[2], output) + ["--debug-geometry"])
    assert result.returncode != 0
    assert "collision" in result.stderr
    assert destination.read_bytes() == b"existing unrelated bytes"
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("missing", ["variants", "part-geometry"])
def test_debug_compile_reports_missing_geometry_without_blocking_visual_validate(design_files, tmp_path, missing):
    contract, draft, paths = design_files
    if missing == "variants":
        del contract["variants"]
        expected = "contract.variants"
    else:
        contract["attachments"] = ["wing"]
        draft["topology"]["parts"] = [{"id": "wing", "description": "folded wing"}]
        expected = "draft.topology.parts[0].anchor"
    for path, value in zip(paths, (contract, draft)):
        path.write_bytes(canonical_bytes(value))
    visual = run_cli(arguments("validate", paths))
    assert visual.returncode == 0, visual.stderr
    output = tmp_path / "debug"
    result = run_cli(arguments("compile", paths, output) + ["--debug-geometry"])
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["valid"] is False
    assert any(item["path"] == expected for item in report["diagnostics"])
    assert not output.exists()
    assert "Traceback" not in result.stderr
    normal = run_cli(arguments("compile", paths, tmp_path / "visual"))
    assert normal.returncode == 0, normal.stderr
    assert json.loads(normal.stdout)["guides"] == []


@pytest.mark.parametrize("relative", ["../escape.png", "guides/../../escape.png", "C:/escape.png", "/escape.png"])
def test_compile_rejects_uncontained_guide_before_publication(design_files, tmp_path, monkeypatch, relative):
    output = tmp_path / "packet"
    monkeypatch.setattr(cli.authoring, "compile_design", lambda *_, **__: ConstructionPacket({}, {relative: b"png"}))
    with pytest.raises(SystemExit) as exc:
        cli.main(arguments("compile", design_files[2], output) + ["--debug-geometry"])
    assert exc.value.code != 0
    assert not output.exists()
    assert not (tmp_path / "escape.png").exists()


@pytest.mark.parametrize("debug", [False, True])
def test_compile_does_not_follow_debug_symlink(design_files, tmp_path, debug):
    output = tmp_path / "packet"
    outside = tmp_path / "outside"
    output.mkdir()
    outside.mkdir()
    try:
        os.symlink(outside, output / "guides", target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation unavailable")
    args = arguments("compile", design_files[2], output)
    if debug:
        args.append("--debug-geometry")
    result = run_cli(args)
    if debug:
        assert result.returncode != 0
        assert not (output / "design.json").exists()
    else:
        assert result.returncode == 0, result.stderr
        assert (output / "design.json").exists()
    assert not list(outside.iterdir())


def test_design_help_has_no_production_entry():
    result = run_cli(["--help"])
    assert result.returncode == 0
    assert "design" in result.stdout
    assert "production" not in result.stdout
