"""Offline black-box regression. Decisions and execution receipts are synthetic fixtures."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from maliang_art.authoring import compile_design

PROJECT = Path(__file__).resolve().parents[1]
CLI = PROJECT / "scripts" / "production.py"


class ProductionCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        image = Image.new("RGBA", (16, 16))
        image.paste((255, 0, 0, 255), (3, 3, 12, 12))
        image.save(self.root / "image.png")
        image.save(self.root / "ref-a.png")
        image.paste((0, 255, 0, 255), (4, 4, 10, 10))
        image.save(self.root / "ref-b.png")
        self.contract = {
            "schemaVersion": 1, "familyId": "synthetic",
            "camera": {"mode": "isometric", "profile": {"North": "UL", "South": "DR", "East": "UL+flipX", "West": "DR+flipX"}, "mirrorAccepted": True},
            "silhouettes": ["bird"], "attachments": ["wing"],
            "drawingRules": [{"id": "style", "instruction": "Readable toy-like form", "method": "human", "required": True}],
            "paletteRoles": {"main": "#8899AA", "secondary": "#334455", "outline": "#112233", "accent": "#EECC44"},
            "targets": {"sourceSize": [16, 16], "outputSize": [16, 16], "anchorX": 8, "groundY": 14, "displaySizes": [16, 32], "contextBoard": {"cellSize": [32, 32], "columns": 4}, "tolerance": 2},
            "statePolicy": {"allowedCoreTransforms": ["upright"], "allowedPartChanges": ["folded"]}}
        self.draft = {"schemaVersion": 1,
            "identity": {"species": "synthetic bird", "features": ["striped face"], "priority": ["striped face"], "forbiddenMirror": []},
            "topology": {"core": "torso excluding wings", "parts": [{"id": "wing", "description": "folded wing"}], "prohibited": ["extra wings"]},
            "silhouetteClass": "bird",
            "visualMoment": [{"view": "DR", "state": "Idle", "moment": "alert", "coreTransform": "upright", "partChanges": ["folded"]}],
            "paletteRoles": {}, "targets": {},
            "references": [{"path": p, "sha256": self.sha(p), "roles": [role], "borrow": ["listed role only"], "forbid": ["unlisted roles"]}
                           for p, role in [("ref-b.png", "style"), ("ref-a.png", "identity")]]}
        self.compile()
        self.write("params.json", {"size": "16x16", "output_format": "png", "background": "transparent"})

    def compile(self):
        self.write("contract.json", self.contract)
        self.write("draft.json", self.draft)
        self.packet = compile_design(self.contract, self.draft).document
        self.write("design.json", self.packet)

    def test_acceptance_wrapper_forwards_project_from_external_directory(self):
        import shutil
        project = self.root / "project with spaces"
        project.mkdir()
        for name in ("contract.json", "draft.json", "design.json"):
            shutil.copyfile(self.root / name, project / name)
        command = [sys.executable, "-I", str(CLI.with_name("extract_acceptance.py")),
                   "--project", str(project), "--design", "design.json",
                   "--contract", "contract.json", "--draft", "draft.json"]
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn({"id": "identity", "method": "human"}, json.loads(result.stdout))
        result = subprocess.run(command + ["--unknown"], cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)

    def test_design_trial_default_and_explicit_draft(self):
        command = [sys.executable, "-I", str(CLI.with_name("design_trial.py")), "--character", "falcon-idle"]
        for extra in ([], ["--draft", "characters/falcon-idle/draft-example.json"]):
            result = subprocess.run(command + extra, cwd=self.root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run(command + ["--draft", "missing.json"], cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", result.stderr)

    def test_tampered_execution_packet_is_rejected(self):
        import copy
        baseline = copy.deepcopy(self.packet)
        mutations = [
            lambda p: p.update(acceptance=[x for x in p["acceptance"] if x["id"] != "pose"]),
            lambda p: next(x for x in p["acceptance"] if x["id"] == "technical-targets").update(required=False),
            lambda p: next(x for x in p["acceptance"] if x["id"] == "technical-targets").update(method="human"),
            lambda p: next(x for x in p["acceptance"] if x["id"] == "palette").update(required=False),
            lambda p: p.update(prompt="arbitrary substituted prompt"),
            lambda p: p["imageInputs"].reverse(),
            lambda p: p["imageInputs"][0].update(roles=["identity"]),
            lambda p: p["tasks"][0].update(moment="invented action"),
            lambda p: p.update(designId="untrusted-design"),
            lambda p: p["targets"].update(outputSize=[32, 32])]
        for index, mutation in enumerate(mutations):
            with self.subTest(index=index):
                packet = copy.deepcopy(baseline)
                mutation(packet)
                self.write("design.json", packet)
                self.cli("prepare", "--attempt", f"tampered-{index}", "--design", "design.json", "--parameters", "params.json",
                         "--provider", "offline-synthetic", ok=False)
                self.assertFalse((self.root / f"production/attempts/tampered-{index}/claim.json").exists())
                self.cli("import", "--attempt", f"import-tampered-{index}", "--design", "design.json", "--image", "image.png",
                         "--provenance", "synthetic fixture", ok=False)
                self.assertFalse((self.root / f"production/attempts/import-tampered-{index}/claim.json").exists())

    def tearDown(self):
        self.tmp.cleanup()

    def sha(self, path):
        return hashlib.sha256((self.root / path).read_bytes()).hexdigest()

    def write(self, path, value):
        (self.root / path).write_text(json.dumps(value), encoding="utf-8")

    def cli(self, *args, ok=True):
        if args[0] in {"prepare", "import", "acceptance"}:
            args = (*args, "--contract", "contract.json", "--draft", "draft.json")
        completed = subprocess.run([sys.executable, "-I", str(CLI), "--project", str(self.root), *args],
                                   cwd=self.root.parent, capture_output=True, text=True)
        if ok:
            self.assertEqual(completed.returncode, 0, completed.stderr)
            return json.loads(completed.stdout)
        self.assertNotEqual(completed.returncode, 0, completed.stdout)
        return completed.stderr

    def prepare(self, attempt, *extra):
        return self.cli("prepare", "--attempt", attempt, "--design", "design.json", "--parameters", "params.json",
                        "--provider", "offline-synthetic", *extra)

    def complete(self, attempt, prepared):
        self.write("receipt.json", {"preparedEventId": prepared["eventId"], "invocation": prepared["invocation"],
                   "outcome": "success", "artifactSha256": self.sha("image.png"),
                   "executionEvidence": "synthetic offline adapter fixture; not a real provider execution"})
        return self.cli("complete", "--attempt", attempt, "--receipt", "receipt.json", "--image", "image.png")

    def review(self, candidate, omit=None):
        binding = {key: candidate[key] for key in ("eventId", "attemptId", "artifact")}
        self.write("human.json", {"actorType": "human", "candidate": binding, "identityChecklist": ["identity"],
            "statement": "Synthetic human decision fixture; not production approval", "reviewer": "fixture-human",
            "decision": "adopt", "checklist": {item["id"]: "pass" for item in candidate["requiredAcceptance"]
                if item["method"] == "human" and item["id"] != omit}, "decidedAt": "2026-01-01T00:00:00Z"})
        return self.cli("review", "--attempt", candidate["attemptId"], "--decision-file", "human.json")

    def event_path(self, event):
        return f"production/events/{event['eventId']}.json"

    def test_acceptance_strict_and_no_omission_flags(self):
        manifest = self.cli("acceptance", "--design", "design.json")
        self.assertEqual(manifest, [{"id": "style", "method": "human"},
            {"id": "technical-targets", "method": "automatic"}, {"id": "identity", "method": "human"},
            {"id": "pose", "method": "human"}, {"id": "palette", "method": "human"}])
        self.packet["acceptance"].append({"id": "identity", "method": "human", "required": False})
        self.write("design.json", self.packet)
        self.assertIn("duplicate", self.cli("acceptance", "--design", "design.json", ok=False))
        self.packet["acceptance"].pop()
        self.packet["acceptance"][1]["method"] = "unknown"
        self.write("design.json", self.packet)
        self.assertIn("unknown", self.cli("acceptance", "--design", "design.json", ok=False))
        self.cli("prepare", "--required-human", "identity", ok=False)

    def test_missing_technical_wrong_candidate_and_direct_adoption(self):
        v1 = self.complete("v1", self.prepare("v1"))
        original = (self.root / v1["artifact"]["path"]).read_bytes()
        review1 = self.review(v1)
        self.cli("adopt", "--attempt", "v1", "--asset", "bird", "--review", self.event_path(review1), ok=False)
        v2 = self.complete("v2", self.prepare("v2"))
        technical2 = self.cli("technical", "--attempt", "v2")
        self.cli("adopt", "--attempt", "v2", "--asset", "bird", "--review", self.event_path(review1),
                 "--result", self.event_path(technical2[0]), ok=False)
        review2 = self.review(v2)
        adoption = self.cli("adopt", "--attempt", "v2", "--asset", "bird", "--review", self.event_path(review2),
                            "--result", self.event_path(technical2[0]))
        self.assertEqual(adoption["candidate"]["attemptId"], "v2")
        projection = json.loads((self.root / "production/current/bird.json").read_text(encoding="utf-8"))
        self.assertEqual(projection["status"], "adopted")
        edit = self.complete("edit", self.prepare("edit", "--parent", "v1", "--instruction", "change only wing"))
        self.assertEqual(edit["parent"]["attemptId"], "v1")
        derived = self.cli("derive", "--attempt", "mirror", "--parent", "edit", "--operation", "flip-x")
        self.assertEqual(derived["sourceAttemptId"], "edit")
        self.cli("technical", "--attempt", "mirror")
        tech1 = self.cli("technical", "--attempt", "v1")
        self.cli("adopt", "--attempt", "v1", "--asset", "bird", "--review", self.event_path(review1),
                 "--result", self.event_path(tech1[0]))
        self.assertEqual(json.loads((self.root / "production/current/bird.json").read_text(encoding="utf-8"))["candidate"]["attemptId"], "v1")
        self.assertEqual((self.root / v1["artifact"]["path"]).read_bytes(), original)
        self.cli("derive", "--attempt", "mirror", "--parent", "v2", "--operation", "copy", ok=False)
        self.cli("prepare", "--attempt", "v1", "--design", "design.json", "--parameters", "params.json",
                 "--provider", "offline-synthetic", ok=False)

    def test_frozen_prompt_input_order_and_exact_completion(self):
        prepared = self.prepare("frozen")
        request = prepared["invocation"]["request"]
        self.assertEqual(request["prompt"], self.packet["prompt"])
        self.assertEqual([i["artifact"]["sha256"] for i in request["inputs"]], [self.sha("ref-b.png"), self.sha("ref-a.png")])
        self.assertEqual(prepared["identityChecklist"], ["identity"])
        sidecar = json.loads((self.root / f"production/designs/{request['designPackageSha256']}.authoring.json").read_text(encoding="utf-8"))
        for kind in ("contract", "draft"):
            self.assertEqual((self.root / sidecar[kind]["path"]).read_bytes(), (self.root / f"{kind}.json").read_bytes())
            self.assertEqual(self.sha(sidecar[kind]["path"]), sidecar[kind]["sha256"])
        self.write("receipt.json", {"preparedEventId": prepared["eventId"], "invocation": {}})
        self.cli("complete", "--attempt", "frozen", "--receipt", "receipt.json", "--image", "image.png", ok=False)
        self.complete("frozen", prepared)
        self.complete_twice_fails(prepared)

    def complete_twice_fails(self, prepared):
        self.cli("complete", "--attempt", prepared["attemptId"], "--receipt", "receipt.json", "--image", "image.png", ok=False)

    def test_refs_containment_import_fail_and_decoding(self):
        self.packet["imageInputs"][0]["sha256"] = "0" * 64
        self.write("design.json", self.packet)
        self.cli("prepare", "--attempt", "bad", "--design", "design.json", "--parameters", "params.json",
                 "--provider", "offline-synthetic", ok=False)
        self.cli("acceptance", "--design", "../outside.json", ok=False)
        self.cli("acceptance", "--design", str(self.root / "design.json"), ok=False)
        self.compile()
        imported = self.cli("import", "--attempt", "old", "--design", "design.json", "--image", "image.png",
                            "--provenance", "synthetic external drawing; no historical invocation", "--historical")
        self.assertNotIn("invocation", imported)
        with Image.open(self.root / imported["artifact"]["path"]) as decoded:
            self.assertEqual(decoded.format, "PNG")
        self.draft["references"] = []
        self.compile()
        self.prepare("failed")
        self.cli("fail", "--attempt", "failed", "--category", "timeout", "--message", "offline fixture")
        self.cli("technical", "--attempt", "failed", ok=False)

    def test_no_image_prepare_and_all_required_methods(self):
        self.draft["references"] = []
        self.contract["drawingRules"].extend([
            {"id": "extra-alpha", "instruction": "Output dimensions match; alpha is nonempty; no alpha touches canvas edge.", "method": "alpha-bounds", "required": True},
            {"id": "optional-style", "instruction": "Optional style preference", "method": "human", "required": False}])
        self.compile()
        prepared = self.prepare("no-input")
        self.assertEqual(prepared["invocation"]["request"]["inputs"], [])
        self.assertEqual(prepared["invocation"]["request"]["prompt"], self.packet["prompt"])
        self.assertEqual(prepared["requiredAcceptance"], [
            {"id": "style", "method": "human"}, {"id": "extra-alpha", "method": "automatic"},
            {"id": "technical-targets", "method": "automatic"}, {"id": "identity", "method": "human"},
            {"id": "pose", "method": "human"}, {"id": "palette", "method": "human"}])
        candidate = self.complete("no-input", prepared)
        results = self.cli("technical", "--attempt", "no-input")
        self.assertEqual(len(results), 2)
        review = self.review(candidate, omit="pose")
        self.cli("adopt", "--attempt", "no-input", "--asset", "bird", "--review", self.event_path(review),
                 "--result", self.event_path(results[0]), "--result", self.event_path(results[1]), ok=False)

    def test_edit_uses_its_own_frozen_packet_for_technical(self):
        self.complete("parent", self.prepare("parent"))
        self.contract["targets"]["outputSize"] = [32, 32]
        self.compile()
        edit = self.complete("edit-new-brief", self.prepare("edit-new-brief", "--parent", "parent", "--instruction", "enlarge output"))
        results = self.cli("technical", "--attempt", edit["attemptId"])
        self.assertEqual(results[0]["status"], "fail")
        review = self.review(edit)
        self.cli("adopt", "--attempt", edit["attemptId"], "--asset", "bird", "--review", self.event_path(review),
                 "--result", self.event_path(results[0]), ok=False)

    def test_current_entrypoints_reject_legacy_approval_shortcuts(self):
        for name in ("production.py", "extract_acceptance.py"):
            result = subprocess.run([sys.executable, "-I", str(PROJECT / "scripts" / name), "--decide", "approve"],
                                    cwd=self.root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("usage:", result.stderr)
        self.cli("adopt", "--attempt", "unreviewed", "--asset", "bird", ok=False)
        self.assertFalse((self.root / "production/current/bird.json").exists())
        for path in (PROJECT / "scripts").glob("*.py"):
            self.assertNotIn("sys.path.insert", path.read_text(encoding="utf-8"))


def test_mirror_rejects_header_before_decode(monkeypatch, tmp_path):
    import runpy
    import pytest
    from PIL import ImageOps
    module = runpy.run_path(str(CLI))
    class Store:
        def __init__(self, root):
            pass
        def load_candidate(self, attempt):
            return {"artifact": {"path": "image.bin"}}
    class Header:
        width = height = 12000
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    (tmp_path / "image.bin").write_bytes(b"header")
    monkeypatch.setitem(module["main"].__globals__, "ProductionStore", Store)
    monkeypatch.setattr(Image, "open", lambda *args: Header())
    def unexpected_decode(*args):
        raise AssertionError("must reject before mirror decodes")
    monkeypatch.setattr(ImageOps, "mirror", unexpected_decode)
    with pytest.raises(ValueError, match="decode budget"):
        module["main"](["--project", str(tmp_path), "derive", "--attempt", "child",
                        "--parent", "parent", "--operation", "flip-x"])


def test_private_runtime_paths_ignored_without_hiding_public_assets(tmp_path):
    repo = PROJECT.parents[1]
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / ".gitignore").write_bytes((repo / ".gitignore").read_bytes())
    private = ["examples/art-pilot/maliang.lock.json", "examples/art-pilot/production/event.json", "work/art-pilot/preview.png"]
    public = ["examples/art-pilot/characters/falcon-idle/draft-example.json", "examples/poet-cast/assets.json",
              "examples/poet-cast/images/example.png", "schemas/v1/state-machine-policy.schema.json"]
    result = subprocess.run(["git", "check-ignore", "--no-index", *private, *public], cwd=tmp_path,
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.splitlines() == private


def test_source_features_are_distinct_from_release_docs():
    repo = PROJECT.parents[1]
    schema = json.loads((repo / "schemas/v1/state-machine-policy.schema.json").read_text(encoding="utf-8"))
    assert schema["$id"] == "urn:maliang:schema:state-machine-policy:v1"
    for name in ("README.md", "README.zh-CN.md"):
        text = (repo / name).read_text(encoding="utf-8")
        install = text.index("python -m pip install .")
        assert text.index("v0.1.0") < install
        assert text.index("`design`") < install and text.index("`flow`") < install
        assert install < text.index("python -I examples/art-pilot/scripts/offline_demo.py")
        assert "git clone https://github.com/cty41/maliang.git" in text


if __name__ == "__main__":
    unittest.main()
