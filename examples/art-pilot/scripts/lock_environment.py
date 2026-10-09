"""Re-lock and install a wheel built by the parent; never builds or edits MaLiang."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]


def verify_installed(package_root, sources):
    installed = {"maliang_art/" + path.relative_to(package_root).as_posix(): path
                 for path in package_root.rglob("*") if path.is_file()
                 and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}}
    if set(installed) != set(sources):
        raise ValueError("installed package resource set differs from wheel")
    for name, sha in sources.items():
        if hashlib.sha256(installed[name].read_bytes()).hexdigest() != sha:
            raise ValueError(f"installed package differs from wheel: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True, help="offline dependency wheels")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--record-existing-test-install", action="store_true", help="record stale test wheel honestly without certifying a production rebuild")
    args = parser.parse_args()
    repo, wheel = args.source_repo.resolve(), args.wheel.resolve()
    wheel.relative_to(repo / "dist")
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True).splitlines()
    sources, mismatches = {}, []
    expected = {}
    for directory, prefix in ((repo / "src" / "maliang_art", "maliang_art/"),
                              (repo / "schemas", "maliang_art/schemas/")):
        for path in directory.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}:
                name = prefix + path.relative_to(directory).as_posix()
                if name in expected:
                    raise ValueError(f"ambiguous packaged source resource: {name}")
                expected[name] = path
    with zipfile.ZipFile(wheel) as archive:
        members = [name for name in archive.namelist() if name.startswith("maliang_art/")
                   and not name.endswith("/") and "__pycache__" not in Path(name).parts
                   and Path(name).suffix not in {".pyc", ".pyo"}]
        if len(members) != len(set(members)):
            raise ValueError("duplicate package wheel member")
        mismatches.extend(sorted(set(members) ^ set(expected)))
        for name in members:
            data = archive.read(name)
            if name not in expected or data != expected[name].read_bytes():
                mismatches.append(name)
            sources[name] = hashlib.sha256(data).hexdigest()
    if mismatches and not args.record_existing_test_install:
        raise ValueError(f"stale wheel members: {mismatches}; parent must rebuild")
    lock = {"distribution": "maliang-game-art", "wheel": str(wheel),
            "wheelSha256": hashlib.sha256(wheel.read_bytes()).hexdigest(), "baseCommit": commit,
            "sourceDirty": bool(status), "sourceStatus": status, "packageSourceSha256": sources,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
            "sourceSnapshotMatchesWheel": not mismatches, "mismatchedSourceMembers": mismatches,
            "readiness": "test-only-pending-parent-rebuild" if mismatches else "locked",
            "note": "Base commit alone does NOT contain the new uncommitted code. Source status is observed at lock time, not proof of historic build time. Wheel member hashes are the exact executable snapshot. Mismatches require parent rebuild and re-lock before real imagery."}
    if args.dry_run:
        print(json.dumps(lock, indent=2))
        return
    python = PROJECT / ".venv" / "Scripts" / "python.exe"
    if not args.record_existing_test_install:
        if not python.is_file():
            subprocess.run([sys.executable, "-m", "venv", str(PROJECT / ".venv")], check=True)
        subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--find-links", str(args.wheelhouse.resolve()),
                        "--force-reinstall", str(wheel)], check=True)
    installed = subprocess.check_output([str(python), "-I", "-c", "import maliang_art.production, maliang_art.authoring; print(maliang_art.production.__file__)"], cwd=repo.parent, text=True).strip()
    if not Path(installed).is_relative_to(PROJECT / ".venv"):
        raise ValueError("independent installed package smoke test failed")
    package_root = Path(installed).parents[1]
    verify_installed(package_root, sources)
    lock["installedProductionModule"] = installed
    destination = PROJECT / "maliang.lock.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    print(json.dumps(lock, indent=2))


if __name__ == "__main__":
    main()
