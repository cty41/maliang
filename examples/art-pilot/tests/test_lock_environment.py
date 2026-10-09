"""Synthetic wheel resources; never modifies MaLiang source or an installed package."""
import contextlib
import io
import json
import runpy
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "lock_environment.py"


class WheelResources(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.files = {"maliang_art/__init__.py": b"", "maliang_art/templates/brief.txt": b"template",
                      "maliang_art/schemas/v1/sample.json": b'{"type":"object"}'}
        for name, data in self.files.items():
            relative = name.removeprefix("maliang_art/")
            path = self.repo / (relative if relative.startswith("schemas/") else "src/" + name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (self.repo / "dist").mkdir()
        self.wheel = self.repo / "dist" / "synthetic.whl"
        self.module = runpy.run_path(str(SCRIPT))

    def tearDown(self):
        self.temp.cleanup()

    def run_lock(self, files):
        with zipfile.ZipFile(self.wheel, "w") as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        argv = [str(SCRIPT), "--source-repo", str(self.repo), "--wheel", str(self.wheel),
                "--wheelhouse", str(self.repo), "--dry-run"]
        output = io.StringIO()
        with patch.object(sys, "argv", argv), patch("subprocess.check_output", side_effect=["a" * 40, ""]), contextlib.redirect_stdout(output):
            self.module["main"]()
        return json.loads(output.getvalue())

    def test_stale_schema_and_template_are_refused(self):
        for name in ("maliang_art/schemas/v1/sample.json", "maliang_art/templates/brief.txt"):
            with self.subTest(resource=name):
                files = dict(self.files)
                files[name] = b"stale resource"
                with self.assertRaisesRegex(ValueError, "stale wheel"):
                    self.run_lock(files)

    def test_all_resource_hashes_are_recorded_and_pycache_ignored(self):
        cache = self.repo / "src/maliang_art/__pycache__/ignored.pyc"
        cache.parent.mkdir()
        cache.write_bytes(b"cache")
        lock = self.run_lock(self.files)
        self.assertTrue(lock["sourceSnapshotMatchesWheel"])
        self.assertEqual(set(lock["packageSourceSha256"]), set(self.files))

    def test_installed_resource_bytes_and_set_are_verified(self):
        import hashlib
        installed = self.repo / "installed/maliang_art"
        hashes = {}
        for name, data in self.files.items():
            path = installed / name.removeprefix("maliang_art/")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            hashes[name] = hashlib.sha256(data).hexdigest()
        self.module["verify_installed"](installed, hashes)
        for name in ("schemas/v1/sample.json", "templates/brief.txt"):
            path = installed / name
            original = path.read_bytes()
            path.write_bytes(b"tampered installed resource")
            with self.assertRaisesRegex(ValueError, "differs from wheel"):
                self.module["verify_installed"](installed, hashes)
            path.write_bytes(original)
        (installed / "extra.txt").write_bytes(b"unexpected")
        with self.assertRaisesRegex(ValueError, "resource set"):
            self.module["verify_installed"](installed, hashes)

    def test_current_installed_wheel_all_resources_match(self):
        import hashlib
        import maliang_art.production
        project = SCRIPT.parents[1]
        lock = json.loads((project / "maliang.lock.json").read_text())
        wheel = Path(lock["wheel"])
        self.assertEqual(hashlib.sha256(wheel.read_bytes()).hexdigest(), lock["wheelSha256"])
        package = Path(maliang_art.production.__file__).resolve().parents[1]
        self.assertTrue(package.is_relative_to(project / ".venv"))
        with zipfile.ZipFile(wheel) as archive:
            hashes = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist()
                      if name.startswith("maliang_art/") and not name.endswith("/")
                      and "__pycache__" not in Path(name).parts and Path(name).suffix not in {".pyc", ".pyo"}}
        self.module["verify_installed"](package, hashes)
        self.assertIn("maliang_art/statemachine/templates/default-policy.yaml", hashes)
        self.assertIn("maliang_art/schemas/v1/art-family-contract.schema.json", hashes)

    def test_venv_is_created_only_when_interpreter_is_absent(self):
        self.run_lock(self.files)
        python = self.repo / ".venv/Scripts/python.exe"
        python.parent.mkdir(parents=True)
        argv = [str(SCRIPT), "--source-repo", str(self.repo), "--wheel", str(self.wheel),
                "--wheelhouse", str(self.repo)]
        installed = self.repo / ".venv/Lib/site-packages/maliang_art/production/__init__.py"
        for present in (True, False):
            with self.subTest(interpreter_exists=present):
                if present:
                    python.write_bytes(b"synthetic interpreter")
                else:
                    python.unlink()
                with patch.object(sys, "argv", argv), patch.dict(self.module["main"].__globals__,
                    {"PROJECT": self.repo, "verify_installed": lambda *_: None}), \
                    patch("subprocess.check_output", side_effect=["a" * 40, "", str(installed)]), \
                    patch("subprocess.run") as run, contextlib.redirect_stdout(io.StringIO()):
                    self.module["main"]()
                commands = [call.args[0] for call in run.call_args_list]
                self.assertEqual(sum(command[1:3] == ["-m", "venv"] for command in commands), 0 if present else 1)
                self.assertEqual(sum(command[1:4] == ["-m", "pip", "install"] for command in commands), 1)

    def test_missing_and_extra_resources_are_refused(self):
        files = dict(self.files)
        del files["maliang_art/templates/brief.txt"]
        with self.assertRaises(ValueError):
            self.run_lock(files)
        files = dict(self.files)
        files["maliang_art/templates/extra.txt"] = b"unexpected"
        with self.assertRaises(ValueError):
            self.run_lock(files)


if __name__ == "__main__":
    unittest.main()
