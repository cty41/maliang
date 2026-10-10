"""Install a supplied wheel in a disposable environment and verify every resource."""
from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

LOCK = runpy.run_path(str(Path(__file__).with_name("lock_environment.py")))


def smoke_wheel(wheel, wheelhouse=None):
    wheel = Path(wheel).resolve()
    with zipfile.ZipFile(wheel) as archive:
        names = [name for name in archive.namelist() if name.startswith("maliang_art/")
                 and not name.endswith("/") and "__pycache__" not in Path(name).parts
                 and Path(name).suffix not in {".pyc", ".pyo"}]
        if not names or len(names) != len(set(names)):
            raise ValueError("missing or duplicate package wheel members")
        hashes = {name: hashlib.sha256(archive.read(name)).hexdigest() for name in names}
    with tempfile.TemporaryDirectory(prefix="maliang-wheel-") as temporary:
        root = Path(temporary)
        environment = root / "venv"
        python = LOCK["venv_python"](environment)
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True, cwd=root)
        command = [str(python), "-I", "-m", "pip", "install", "--disable-pip-version-check"]
        if wheelhouse is not None:
            command.extend(["--no-index", "--find-links", str(Path(wheelhouse).resolve())])
        subprocess.run([*command, str(wheel)], check=True, cwd=root)
        installed = subprocess.check_output(
            [str(python), "-I", "-c", "import maliang_art; print(maliang_art.__file__)"],
            cwd=root, text=True).strip()
        package = Path(installed).resolve().parent
        if not package.is_relative_to(environment.resolve()):
            raise ValueError("wheel import escaped the isolated environment")
        LOCK["verify_installed"](package, hashes)
        if "maliang_art/__main__.py" in hashes:
            subprocess.run([str(python), "-I", "-m", "maliang_art", "--help"], check=True, cwd=root)
            subprocess.run([str(python), "-I", "-c",
                            "import importlib.resources as r, json; root = r.files('maliang_art').joinpath('schemas/v1'); "
                            "[json.loads(root.joinpath(name).read_text(encoding='utf-8')) for name in "
                            "('artifact.schema.json', 'pose-draft.schema.json', 'pose-card.schema.json', 'art-family-contract.schema.json')]; "
                            "assert r.files('maliang_art').joinpath('statemachine/templates/default-policy.yaml').is_file()"],
                           check=True, cwd=root)
        result = {"wheel": str(wheel), "wheelSha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
                  "verifiedResources": len(hashes), "environment": str(environment)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, help="use only this offline dependency wheelhouse")
    args = parser.parse_args()
    print(json.dumps(smoke_wheel(args.wheel, args.wheelhouse), indent=2))


if __name__ == "__main__":
    main()
