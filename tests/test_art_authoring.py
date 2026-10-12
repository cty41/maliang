import copy
import io
import json
from pathlib import Path

import pytest
from PIL import Image
from jsonschema import Draft202012Validator

from maliang_art.authoring import DesignError, audit_alpha_bounds, compile_design, validate_design
from maliang_art.core import canonical_bytes


def inputs():
    contract = {
        "schemaVersion": 1, "familyId": "synthetic",
        "camera": {"mode": "isometric", "profile": {"North": "UL", "South": "DR", "East": "UL+flipX", "West": "DR+flipX"}, "mirrorAccepted": True},
        "silhouettes": ["capsule", "ball"], "attachments": ["wing"],
        "drawingRules": [{"id": "style", "instruction": "Readable toy-like form", "method": "human", "required": True}],
        "paletteRoles": {"main": "#8899AA", "secondary": "#334455", "outline": "#112233", "accent": "#EECC44"},
        "targets": {"sourceSize": [96, 96], "outputSize": [64, 64], "anchorX": 48, "groundY": 80, "displaySizes": [64, 128], "contextBoard": {"cellSize": [128, 128], "columns": 4}, "tolerance": 2},
        "variants": [{"id": "narrow", "coreWidth": 0.3, "coreHeight": 0.5}, {"id": "wide", "coreWidth": 0.4, "coreHeight": 0.5}],
        "statePolicy": {"allowedCoreTransforms": ["upright", "lean"], "allowedPartChanges": ["folded", "extended"]},
    }
    draft = {
        "schemaVersion": 1,
        "identity": {"species": "synthetic bird", "features": ["striped face"], "priority": ["striped face"], "forbiddenMirror": []},
        "topology": {"core": "torso excluding wings", "parts": [{"id": "wing", "anchor": [0.3, 0.5], "size": [0.2, 0.3]}], "prohibited": ["extra wings"]},
        "silhouetteClass": "capsule",
        "visualMoment": [{"view": "DR", "state": "Idle", "moment": "resting upright", "coreTransform": "upright", "partChanges": ["folded"]}],
        "paletteRoles": {}, "targets": {}, "references": [],
    }
    return contract, draft


def test_no_geometry_falcon_prepares_visual_brief():
    c, d = inputs()
    del c["variants"]
    c["silhouettes"] = ["bird"]
    c["attachments"] = ["wings", "feet", "tail", "beak"]
    d["identity"] = {"species": "peregrine falcon", "features": ["hooked beak", "cheek markings"], "priority": ["hooked beak"], "forbiddenMirror": []}
    d["silhouetteClass"] = "bird"
    d["topology"] = {"core": "bird torso excluding wings, feet and tail", "parts": [
        {"id": "wings", "description": "two folded wings"},
        {"id": "feet", "description": "two feet"},
        {"id": "tail", "description": "short tail"},
        {"id": "beak", "description": "hooked beak"},
    ], "prohibited": ["four paws", "dog face"]}
    d["visualMoment"][0]["moment"] = "alert standing with folded wings"
    assert validate_design(c, d) == []
    packet = compile_design(c, d)
    assert packet.guides == {}
    assert packet.document["imageInputs"] == []
    assert packet.document["options"] == []
    assert "peregrine falcon" in packet.document["prompt"]
    assert packet.document["artDecision"]["status"] == "pending"
    root = Path(__file__).parents[1] / "schemas/v1"
    for name, value in [("art-family-contract", c), ("sprite-slice-draft", d)]:
        Draft202012Validator(json.loads((root / f"{name}.schema.json").read_text())).validate(value)


def test_default_packet_never_uses_debug_geometry_as_generation_input():
    c, d = inputs()
    d["references"] = [{"path": "refs/style.png", "sha256": "a" * 64, "roles": ["style"], "borrow": ["line weight"], "forbid": ["identity"]}]
    packet = compile_design(c, d)
    assert packet.guides == {}
    assert packet.document["imageInputs"] == d["references"]
    assert "Select one exploration option" not in packet.document["prompt"]
    prompt_data = json.loads(packet.document["prompt"].split("\n", 1)[1])
    assert "anchor" not in prompt_data["topology"]["parts"][0]
    assert "size" not in prompt_data["topology"]["parts"][0]


def test_incomplete_falcon_reports_decisions_not_defaults():
    c, _ = inputs()
    diagnostics = validate_design(c, {"schemaVersion": 1, "identity": {"species": "falcon"}})
    paths = {d.path for d in diagnostics}
    assert "draft.topology" in paths
    assert "draft.visualMoment" in paths
    assert "draft.identity.features" in paths
    assert all(d.message for d in diagnostics)
    with pytest.raises(DesignError):
        compile_design(c, {"schemaVersion": 1})


@pytest.mark.parametrize("shape", ["capsule", "ball"])
def test_packet_is_stable_and_honest(shape):
    c, d = inputs()
    d["silhouetteClass"] = shape
    assert validate_design(c, d) == []
    a, b = compile_design(c, d, debug_geometry=True), compile_design(copy.deepcopy(c), copy.deepcopy(d), debug_geometry=True)
    assert a.json_bytes == b.json_bytes
    assert a.guides == b.guides
    assert len(a.guides) == 2
    p = a.document
    assert p["imageInputs"] == []
    assert p["debugArtifacts"]
    for artifact in p["debugArtifacts"] + p["options"]:
        assert (artifact["kind"], artifact["status"], artifact["usage"]) == ("debug-layout", "unapproved", "not-generation-input")
    assert "options" not in json.loads(p["prompt"].split("\n", 1)[1])
    assert p["references"] == []
    assert p["contextBoard"]["status"] == "layout-only"
    assert p["acceptance"][0]["status"] == "pending"
    assert "not a compliance guarantee" in p["prompt"]
    assert p["identityInvariant"]["poseProjection"] == "variable"
    for guide in a.guides.values():
        image = Image.open(io.BytesIO(guide))
        assert image.size == (96, 96)
        assert image.getbbox() is not None
    assert a.json_bytes == canonical_bytes(p)


def test_reference_order_and_role_boundaries():
    c, d = inputs()
    d["references"] = [{"path": "refs/style.png", "sha256": "a" * 64, "roles": ["style", "pose"], "borrow": ["line weight"], "forbid": ["identity"]}]
    p = compile_design(c, d).document
    assert p["references"] == d["references"]
    assert p["imageInputs"][-1]["roles"] == ["style", "pose"]
    assert p["imageInputs"][-1]["forbid"] == ["identity"]
    assert p["imageInputs"] == d["references"]
    d["references"].append({"path": "refs/identity.png", "sha256": "b" * 64, "roles": ["identity"], "borrow": ["facial stripes"], "forbid": ["style", "pose"]})
    d["references"].append({"path": "refs/shape.png", "sha256": "c" * 64, "roles": ["shape"], "borrow": ["body volume"], "forbid": ["identity"]})
    assert validate_design(c, d) == []
    schema = json.loads((Path(__file__).parents[1] / "schemas/v1/sprite-slice-draft.schema.json").read_text())
    Draft202012Validator(schema).validate(d)
    packet = compile_design(c, d)
    assert packet.document["references"] == d["references"]
    assert packet.document["imageInputs"][-3:] == d["references"]
    assert packet.document["imageInputs"] == d["references"]
    prompt_data = json.loads(packet.document["prompt"].split("\n", 1)[1])
    assert prompt_data["imageInputs"][-3:] == d["references"]
    assert packet.json_bytes == compile_design(copy.deepcopy(c), copy.deepcopy(d)).json_bytes
    reverse = copy.deepcopy(d)
    reverse["references"].reverse()
    assert compile_design(c, reverse).document["imageInputs"][-3:] == reverse["references"]
    assert packet.document["designId"] != compile_design(c, reverse).document["designId"]


@pytest.mark.parametrize("mutation,path", [
    (lambda c, d: c["camera"].update(mode="flat2d"), "contract.camera.mode"),
    (lambda c, d: d.update(silhouetteClass="triangle"), "draft.silhouetteClass"),
    (lambda c, d: d["visualMoment"][0].update(moment=""), "draft.visualMoment[0].moment"),
    (lambda c, d: c["drawingRules"][0].update(method="recognize-falcon"), "contract.drawingRules[0].method"),
    (lambda c, d: d["identity"].update(forbiddenMirror=["left badge"]), "draft.identity.forbiddenMirror"),
    (lambda c, d: d["references"].append({"path": "C:/private.png", "sha256": "a" * 64, "roles": ["style"], "borrow": ["color"], "forbid": ["identity"]}), "draft.references[0].path"),
])
def test_specific_invalid_or_unsupported(mutation, path):
    c, d = inputs()
    mutation(c, d)
    assert any(x.path == path for x in validate_design(c, d))


def test_schemas_match_valid_documents():
    c, d = inputs()
    root = Path(__file__).parents[1] / "schemas" / "v1"
    for name, value in [("art-family-contract", c), ("sprite-slice-draft", d)]:
        schema = json.loads((root / f"{name}.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(value)


def test_identity_vs_projection_and_pending_attack():
    c, d = inputs()
    d["visualMoment"].append({"view": "UL", "state": "Attack", "moment": "", "coreTransform": "lean", "partChanges": ["extended"]})
    assert any(x.path == "draft.visualMoment[1].moment" for x in validate_design(c, d))
    d["visualMoment"][1]["moment"] = "contact instant with wing extended"
    packet = compile_design(c, d)
    assert packet.document["tasks"][1]["coreTransform"] == "lean"
    assert "equal" not in packet.document["identityInvariant"]["shape"]


@pytest.mark.parametrize("expected", [[64, 64], [12000, 12000]])
def test_alpha_audit_rejects_header_before_decode(monkeypatch, expected):
    class Header:
        size = (12000, 12000)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def convert(self, *args):
            raise AssertionError("must not decode oversized image")
    monkeypatch.setattr("maliang_art.authoring.compiler.Image.open", lambda *args: Header())
    assert audit_alpha_bounds(b"header", expected) == {
        "status": "fail", "size": [12000, 12000], "alphaBounds": None}


def test_alpha_audit_invalid_image_fails_clearly():
    with pytest.raises(OSError):
        audit_alpha_bounds(b"invalid", [64, 64])
    png = io.BytesIO()
    Image.new("RGBA", (64, 64), "red").save(png, format="PNG")
    with pytest.raises(OSError):
        audit_alpha_bounds(png.getvalue()[:60], [64, 64])


def test_machine_checks_never_prove_subjective_instructions():
    c, d = inputs()
    c["drawingRules"][0]["method"] = "alpha-bounds"
    assert any(x.path.endswith(".instruction") for x in validate_design(c, d))
    c["drawingRules"][0]["instruction"] = "Output dimensions match; alpha is nonempty; no alpha touches canvas edge."
    assert validate_design(c, d) == []
    image = Image.new("RGBA", (64, 64))
    from PIL import ImageDraw
    ImageDraw.Draw(image).ellipse((10, 10, 40, 40), fill="red")
    out = io.BytesIO()
    image.save(out, format="PNG")
    assert audit_alpha_bounds(out.getvalue(), [64, 64])["status"] == "pass"
    assert audit_alpha_bounds(out.getvalue(), [96, 96])["status"] == "fail"
    blank = io.BytesIO()
    Image.new("RGBA", (64, 64)).save(blank, format="PNG")
    assert audit_alpha_bounds(blank.getvalue(), [64, 64])["status"] == "fail"
    edge = io.BytesIO()
    Image.new("RGBA", (64, 64), "red").save(edge, format="PNG")
    assert audit_alpha_bounds(edge.getvalue(), [64, 64])["status"] == "fail"


@pytest.mark.parametrize("mutation", [
    lambda c, d: d["targets"].update(sourceSize=[8, 8]),
    lambda c, d: d["paletteRoles"].update(main="not-a-color"),
    lambda c, d: d["topology"]["parts"][0].update(id="leg"),
    lambda c, d: d["identity"]["priority"].append("unknown feature"),
    lambda c, d: d["visualMoment"][0].update(view="UR"),
    lambda c, d: c["camera"]["profile"].update(East="DR+flipX"),
    lambda c, d: d["visualMoment"][0].update(coreTransform="invented attack"),
    lambda c, d: d["targets"].update(groundY=float("nan")),
    lambda c, d: d.update(schemaVersion=True),
    lambda c, d: d.update(extra="unknown"),
])
def test_no_silent_fallback_or_clipping(mutation):
    c, d = inputs()
    mutation(c, d)
    assert validate_design(c, d)
    with pytest.raises(DesignError):
        compile_design(c, d)


def test_default_compilation_does_not_call_debug_renderer(monkeypatch):
    import maliang_art.authoring.compiler as compiler
    import maliang_art.authoring.validation as validation

    def forbidden(*args):
        pytest.fail("Default visual brief must not depend on debug geometry")

    monkeypatch.setattr(compiler, "geometry", forbidden)
    monkeypatch.setattr(compiler, "render_blockout", forbidden)
    monkeypatch.setattr(validation, "geometry", forbidden)
    c, d = inputs()
    assert validate_design(c, d) == []
    assert compile_design(c, d).guides == {}


def test_debug_layout_bounds_do_not_constrain_visual_brief():
    c, d = inputs()
    d["targets"]["anchorX"] = 0
    assert validate_design(c, d) == []
    assert compile_design(c, d).guides == {}
    assert any(x.path == "contract.variants[0]" for x in validate_design(c, d, debug_geometry=True))
    with pytest.raises(DesignError):
        compile_design(c, d, debug_geometry=True)


def test_debug_geometry_requires_explicit_layout_decisions():
    c, d = inputs()
    del c["variants"]
    del d["topology"]["parts"][0]["anchor"]
    assert validate_design(c, d) == []
    paths = {x.path for x in validate_design(c, d, debug_geometry=True)}
    assert paths == {"contract.variants", "draft.topology.parts[0].anchor"}
    with pytest.raises(DesignError):
        compile_design(c, d, debug_geometry=True)


def test_visual_shape_intention_is_independent_of_debug_renderer():
    c, d = inputs()
    c["silhouettes"].append("bird")
    d["silhouetteClass"] = "bird"
    assert validate_design(c, d) == []
    assert compile_design(c, d).document["silhouetteClass"] == "bird"
    assert any(x.path == "draft.silhouetteClass" for x in validate_design(c, d, debug_geometry=True))


def test_debug_mode_preserves_reference_order_without_submitting_debug_images():
    c, d = inputs()
    d["references"] = [
        {"path": "refs/identity.png", "sha256": "b" * 64, "roles": ["identity"], "borrow": ["face"], "forbid": ["style"]},
        {"path": "refs/style.png", "sha256": "a" * 64, "roles": ["style"], "borrow": ["line weight"], "forbid": ["identity"]},
    ]
    normal = compile_design(c, d)
    debug = compile_design(c, d, debug_geometry=True)
    assert debug.guides
    assert debug.document["imageInputs"] == d["references"]
    assert debug.document["prompt"] == normal.document["prompt"]
    assert debug.document["acceptance"] == normal.document["acceptance"]
    assert debug.document["artDecision"]["status"] == "pending"


def test_override_inheritance_and_deterministic_ul_comparison():
    c, d = inputs()
    original = copy.deepcopy((c, d))
    d["targets"] = {"displaySizes": [80]}
    d["paletteRoles"] = {"accent": "#FFFFFF"}
    d["visualMoment"].append({**d["visualMoment"][0], "view": "UL"})
    before = copy.deepcopy((c, d))
    packet = compile_design(c, d)
    assert (c, d) == before
    assert packet.document["targets"]["displaySizes"] == [80]
    assert packet.document["palettePlan"]["roles"]["accent"] == "#FFFFFF"
    assert packet.guides == {}
    assert len(compile_design(c, d, debug_geometry=True).guides) == 4
    assert {x["status"] for x in packet.document["contextBoard"]["cells"]} == {"pending"}
    assert packet.document["designId"] != compile_design(*original).document["designId"]


@pytest.mark.parametrize("reserved", ["technical-targets", "identity", "pose", "palette"])
def test_family_rule_cannot_shadow_builtin_acceptance_id(reserved):
    c, d = inputs()
    c["drawingRules"][0]["id"] = reserved
    diagnostics = validate_design(c, d)
    assert any(x.path == "contract.drawingRules[0].id" and x.code == "conflict" for x in diagnostics)
    with pytest.raises(DesignError):
        compile_design(c, d)


def test_acceptance_ids_are_unique_and_preserve_family_sources():
    c, d = inputs()
    c["drawingRules"].append({"id": "identity-detail", "instruction": "Visible facial stripes", "method": "human", "required": True})
    cases = compile_design(c, d).document["acceptance"]
    assert len({case["id"] for case in cases}) == len(cases)
    assert [(case["id"], case["source"]) for case in cases[:2]] == [
        ("style", "contract.drawingRules.style"),
        ("identity-detail", "contract.drawingRules.identity-detail"),
    ]
    assert {case["id"]: case["source"] for case in cases[2:]} == {
        "technical-targets": "draft.targets+contract.targets",
        "identity": "draft.identity",
        "pose": "draft.visualMoment",
        "palette": "draft.paletteRoles+contract.paletteRoles",
    }


def test_camera_profile_key_order_does_not_change_packet():
    c, d = inputs()
    original = compile_design(c, d)
    reordered = copy.deepcopy(c)
    reordered["camera"]["profile"] = dict(reversed(list(c["camera"]["profile"].items())))
    assert validate_design(reordered, d) == []
    packet = compile_design(reordered, d)
    assert packet.document["designId"] == original.document["designId"]
    assert packet.document["contextBoard"] == original.document["contextBoard"]
    assert packet.json_bytes == original.json_bytes
    assert packet.guides == original.guides


def test_reference_conflicts_and_traversal():
    c, d = inputs()
    d["references"] = [{"path": "../ref.png", "sha256": "a" * 64, "roles": ["identity"], "borrow": ["identity"], "forbid": ["identity"]}]
    diagnostics = validate_design(c, d)
    assert any(x.path.endswith(".path") for x in diagnostics)
    assert any(x.code == "conflict" for x in diagnostics)
