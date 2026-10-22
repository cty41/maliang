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
                         "--provider", "offline-synthetic", "--character", "bird", ok=False)
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

    def prepare(self, attempt, *extra, character="bird", provider="offline-synthetic", ok=True):
        return self.cli("prepare", "--attempt", attempt, "--design", "design.json", "--parameters", "params.json",
                        "--provider", provider, "--character", character, *extra, ok=ok)

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

    def test_review_quick_records_chat_choice_without_inventing_passes(self):
        candidate = self.complete("quick", self.prepare("quick"))
        rejected = self.cli("review-quick", "--attempt", "quick", "--choice", "reject", "--issues", "pose,palette",
                            "--note", "smirk reads as angry", "--quote", "不通过", "--reviewer", "fixture-human")
        self.assertEqual(rejected["decision"], "reject")
        self.assertEqual(rejected["checklist"]["pose"], "fail")
        self.assertEqual(rejected["checklist"]["palette"], "fail")
        self.assertEqual(rejected["checklist"]["identity"], "pending")
        self.assertNotIn("pass", rejected["checklist"].values())
        evidence = json.loads((self.root / rejected["sourceEvidence"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(evidence["capturedVia"], "host-chat")
        self.assertEqual(evidence["revisionNotes"], {"issues": ["pose", "palette"], "note": "smirk reads as angry"})
        self.assertIn("不通过", evidence["statement"])
        self.cli("review-quick", "--attempt", "quick", "--choice", "reject", "--issues", "nonexistent", ok=False)
        self.cli("review-quick", "--attempt", "quick", "--choice", "pass", ok=False)
        self.cli("review-quick", "--attempt", "quick", "--choice", "pass", "--issues", "pose", "--quote", "ok", ok=False)
        self.cli("review-quick", "--attempt", "quick", "--choice", "reject", "--quote", " ", ok=False)
        technical = self.cli("technical", "--attempt", "quick")
        passed = self.cli("review-quick", "--attempt", "quick", "--choice", "pass", "--quote", "通过")
        self.assertTrue(passed["reviewer"].strip())
        self.assertEqual(set(passed["checklist"].values()), {"pass"})
        adoption = self.cli("adopt", "--attempt", "quick", "--asset", "bird", "--review", self.event_path(passed),
                            "--result", self.event_path(technical[0]))
        self.assertEqual(adoption["candidate"]["attemptId"], candidate["attemptId"])

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
                 "--provider", "offline-synthetic", "--character", "bird", ok=False)

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
                 "--provider", "offline-synthetic", "--character", "bird", ok=False)
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

    def matte_candidate(self, attempt, draw):
        image = Image.new("RGB", (32, 32), (250, 250, 250))
        draw(image)
        image.save(self.root / "image.png")
        return self.complete(attempt, self.prepare(attempt))

    def test_matte_resize_derives_target_sprite_and_requires_new_review(self):
        self.contract["targets"].update(sourceSize=[32, 32], outputSize=[16, 16], anchorX=16, groundY=28)
        self.compile()
        def capsule(image):
            image.paste((40, 40, 40), (10, 8, 22, 28))
            image.paste((245, 245, 240), (13, 14, 19, 20))
        parent = self.matte_candidate("raw", capsule)
        parent_review = self.review(parent)
        derived = self.cli("derive", "--attempt", "sprite", "--parent", "raw", "--operation", "matte-resize")
        self.assertEqual(derived["parent"], {k: parent[k] for k in ("eventId", "attemptId", "artifact")})
        params = derived["parameters"]
        self.assertEqual(params["floodFrom"], "edges")
        self.assertEqual(params["keyColorSource"], "corners")
        self.assertEqual(params["keyColor"], "#FAFAFA")
        self.assertEqual(params["sourceBox"], [10, 8, 22, 28])
        self.assertEqual(params["outputSize"], [16, 16])
        with Image.open(self.root / derived["artifact"]["path"]) as sprite:
            self.assertEqual(sprite.format, "PNG")
            self.assertEqual(sprite.size, (16, 16))
            sprite = sprite.convert("RGBA")
            box = sprite.getchannel("A").getbbox()
            self.assertLessEqual(abs(box[3] - 14), 1)
            self.assertLessEqual(abs((box[0] + box[2]) / 2 - 8), 1)
            inner = sprite.getpixel((8, 8))
            self.assertEqual(inner[3], 255)
            self.assertGreater(min(inner[:3]), 200)
        results = self.cli("technical", "--attempt", "sprite")
        self.assertEqual([r["status"] for r in results], ["pass"])
        self.cli("adopt", "--attempt", "sprite", "--asset", "bird", "--review", self.event_path(parent_review),
                 "--result", self.event_path(results[0]), ok=False)
        review = self.review(derived)
        adoption = self.cli("adopt", "--attempt", "sprite", "--asset", "bird", "--review", self.event_path(review),
                            "--result", self.event_path(results[0]))
        self.assertEqual(adoption["candidate"]["attemptId"], "sprite")

    def test_matte_resize_rejects_without_claiming_attempt(self):
        self.contract["targets"].update(sourceSize=[32, 32], outputSize=[16, 16], anchorX=16, groundY=28)
        self.compile()
        cases = {
            "empty": lambda image: None,
            "edge": lambda image: image.paste((40, 40, 40), (0, 8, 12, 28)),
            "overflow": lambda image: image.paste((40, 40, 40), (10, 1, 22, 31)),
        }
        for name, draw in cases.items():
            with self.subTest(name=name):
                self.matte_candidate(name, draw)
                self.cli("derive", "--attempt", f"{name}-sprite", "--parent", name, "--operation", "matte-resize", ok=False)
                self.assertFalse((self.root / f"production/attempts/{name}-sprite/claim.json").exists())
        self.matte_candidate("keyed", lambda image: (image.paste((0, 200, 0), (2, 2, 30, 30)),
                                                     image.paste((40, 40, 40), (10, 8, 22, 28))))
        for bad in (["--key-color", "#12345G"], ["--key-color", "#1234"], ["--tolerance", "256"]):
            with self.subTest(bad=bad):
                self.cli("derive", "--attempt", "keyed-bad", "--parent", "keyed", "--operation", "matte-resize", *bad, ok=False)
                self.assertFalse((self.root / "production/attempts/keyed-bad/claim.json").exists())
        keyed = self.cli("derive", "--attempt", "keyed-sprite", "--parent", "keyed", "--operation", "matte-resize",
                         "--key-color", "#FAFAFA", "--tolerance", "8")
        self.assertEqual((keyed["parameters"]["keyColor"], keyed["parameters"]["keyColorSource"]), ("#FAFAFA", "explicit"))
        self.assertEqual(keyed["parameters"]["sourceBox"], [2, 2, 30, 30])
        Image.new("RGB", (16, 16), (250, 250, 250)).save(self.root / "image.png")
        self.complete("small", self.prepare("small"))
        self.assertIn("sourceSize", self.cli("derive", "--attempt", "small-sprite", "--parent", "small",
                                              "--operation", "matte-resize", ok=False))
        self.assertFalse((self.root / "production/attempts/small-sprite/claim.json").exists())

    def lock(self, character):
        return json.loads((self.root / f"production/host-locks/{character}.json").read_text(encoding="utf-8"))

    def claimed(self, attempt):
        return (self.root / f"production/attempts/{attempt}/claim.json").exists()

    def test_character_host_lock(self):
        self.cli("prepare", "--attempt", "no-character", "--design", "design.json", "--parameters", "params.json",
                 "--provider", "offline-synthetic", ok=False)
        self.assertFalse(self.claimed("no-character"))
        self.prepare("bad-id", character="../x", ok=False)
        self.assertFalse(self.claimed("bad-id"))
        first = self.complete("first", self.prepare("first"))
        self.assertEqual({k: self.lock("bird")[k] for k in ("character", "provider", "model", "firstAttemptId")},
                         {"character": "bird", "provider": "offline-synthetic", "model": "unknown", "firstAttemptId": "first"})
        self.prepare("other-host", provider="other-synthetic", ok=False)
        self.assertFalse(self.claimed("other-host"))
        self.prepare("named-model", "--model", "named-model", ok=False)
        self.assertFalse(self.claimed("named-model"))
        self.prepare("second")
        self.assertEqual(self.lock("bird")["firstAttemptId"], "first")
        self.prepare("typo", character="brid", ok=False)
        self.assertFalse(self.claimed("typo"))
        self.assertFalse((self.root / "production/host-locks/brid.json").exists())
        self.complete("cat", self.prepare("cat", "--new-character", character="cat", provider="other-synthetic"))
        self.prepare("cross-edit", "--parent", "cat", "--instruction", "change wing", ok=False)
        self.assertFalse(self.claimed("cross-edit"))
        self.cli("derive", "--attempt", "first-copy", "--parent", "first", "--operation", "copy")
        self.prepare("edit-derived", "--parent", "first-copy", "--instruction", "change wing")
        self.prepare("edit-derived-cat", "--parent", "first-copy", "--instruction", "change wing",
                     character="cat", provider="other-synthetic", ok=False)
        self.assertEqual(first["attemptId"], "first")

    def test_cursor_like_provider_must_be_cursor_desktop(self):
        self.prepare("loose-cursor", character="cursor-bird", provider="cursor", ok=False)
        self.assertFalse(self.claimed("loose-cursor"))

    def test_preview_writes_viewing_copy_and_reports_absolute_paths(self):
        candidate = self.complete("view", self.prepare("view"))
        report = self.cli("preview", "--attempt", "view")
        copy = Path(report["viewingCopy"]["path"])
        self.assertTrue(copy.is_absolute())
        self.assertEqual(copy.name, "view.png")
        self.assertEqual(copy.read_bytes(), (self.root / candidate["artifact"]["path"]).read_bytes())
        self.assertEqual(report["candidate"]["sha256"], candidate["artifact"]["sha256"])
        self.assertTrue(Path(report["candidate"]["path"]).is_absolute())
        self.assertFalse(report["viewingCopy"]["evidence"])
        events = sorted(p.name for p in (self.root / "production/events").iterdir())
        self.cli("preview", "--attempt", "view")
        self.assertEqual(events, sorted(p.name for p in (self.root / "production/events").iterdir()))

    def test_revisions_lists_rejected_quick_review_notes_for_character(self):
        self.complete("r1", self.prepare("r1"))
        self.cli("review-quick", "--attempt", "r1", "--choice", "reject", "--issues", "pose",
                 "--note", "less angry", "--quote", "不通过", "--reviewer", "fixture-human")
        notes = self.cli("revisions", "--character", "bird")
        self.assertEqual([(n["attemptId"], n["issues"], n["note"]) for n in notes], [("r1", ["pose"], "less angry")])

    def test_default_reviewer_falls_back_without_git_identity(self):
        import os
        empty = self.root / "empty.gitconfig"
        empty.write_text("", encoding="utf-8")
        self.complete("nogit", self.prepare("nogit"))
        env = {**os.environ, "GIT_CONFIG_GLOBAL": str(empty), "GIT_CONFIG_NOSYSTEM": "1"}
        done = subprocess.run([sys.executable, "-I", str(CLI), "--project", str(self.root), "review-quick",
                               "--attempt", "nogit", "--choice", "reject", "--quote", "no"],
                              cwd=self.root.parent, capture_output=True, text=True, env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        import getpass
        self.assertEqual(json.loads(done.stdout)["reviewer"], getpass.getuser())

    def cursor_prepared(self, attempt, params=None):
        self.write("cursor-params.json", {"aspect_ratio": "1:1"} if params is None else params)
        return self.cli("prepare", "--attempt", attempt, "--design", "design.json", "--parameters", "cursor-params.json",
                        "--provider", "cursor-desktop", "--character", "cursor-bird", "--new-character")

    def cursor_output(self, attempt, image=None):
        out = self.root / "host-assets"
        out.mkdir(exist_ok=True)
        path = out / f"{attempt}.jpg"
        (image or Image.new("RGB", (16, 16), (200, 10, 10))).save(path, format="JPEG")
        return path

    def test_cursor_packet_maps_frozen_request(self):
        self.prepare("offline")
        self.assertIn("cursor-desktop", self.cli("cursor-packet", "--attempt", "offline", ok=False))
        prepared = self.cursor_prepared("cursor-1")
        packet = self.cli("cursor-packet", "--attempt", "cursor-1")
        call = packet["call"]
        self.assertEqual(call["description"], prepared["invocation"]["request"]["prompt"])
        self.assertEqual(call["aspect_ratio"], "1:1")
        self.assertEqual(call["filename"], "cursor-1.png")
        expected = [i["artifact"]["sha256"] for i in prepared["invocation"]["request"]["inputs"]]
        self.assertEqual([hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in call["reference_image_paths"]], expected)
        self.assertTrue(all(Path(p).is_absolute() and Path(p).suffix == ".png" for p in call["reference_image_paths"]))
        stored = self.root / "production/attempts/cursor-1/cursor-call.json"
        self.assertEqual(json.loads(stored.read_text(encoding="utf-8")), call)
        self.assertEqual(packet["sha256"], hashlib.sha256(stored.read_bytes()).hexdigest())
        self.cli("cursor-packet", "--attempt", "cursor-1", ok=False)
        for index, params in enumerate([{"aspect_ratio": "2:1"}, {"aspect_ratio": "1:1", "size": "256x256"}, {"background": "transparent"}]):
            with self.subTest(params=params):
                self.cursor_prepared(f"bad-{index}", params)
                self.cli("cursor-packet", "--attempt", f"bad-{index}", ok=False)
                self.assertFalse((self.root / f"production/attempts/bad-{index}/cursor-call.json").exists())

    def test_cursor_complete_and_fail(self):
        import os
        self.cursor_prepared("cursor-2")
        output = self.cursor_output("cursor-2")
        self.cli("cursor-complete", "--attempt", "cursor-2", "--output", str(output), ok=False)
        packet = self.cli("cursor-packet", "--attempt", "cursor-2")
        stored = self.root / "production/attempts/cursor-2/cursor-call.json"
        old = stored.stat().st_mtime - 60
        os.utime(output, (old, old))
        self.cli("cursor-complete", "--attempt", "cursor-2", "--output", str(output), ok=False)
        wrong = self.cursor_output("other-name")
        self.cli("cursor-complete", "--attempt", "cursor-2", "--output", str(wrong), ok=False)
        broken = output.with_name("cursor-2.png")
        broken.write_bytes(b"not an image")
        self.cli("cursor-complete", "--attempt", "cursor-2", "--output", str(broken), ok=False)
        output = self.cursor_output("cursor-2")
        candidate = self.cli("cursor-complete", "--attempt", "cursor-2", "--output", str(output))
        self.assertEqual(candidate["artifact"]["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
        receipt = json.loads((self.root / candidate["delivery"]["metadata"]["receipt"]["path"]).read_text(encoding="utf-8"))
        self.assertIn("host-agent-attested", receipt["executionEvidence"])
        self.assertIn(packet["sha256"], receipt["executionEvidence"])
        self.cli("cursor-complete", "--attempt", "cursor-2", "--output", str(output), ok=False)
        self.cursor_prepared("cursor-3")
        self.cli("cursor-packet", "--attempt", "cursor-3")
        failure = self.cli("cursor-fail", "--attempt", "cursor-3", "--message", "host reported an error")
        self.assertEqual(failure["recordType"], "failure")

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
