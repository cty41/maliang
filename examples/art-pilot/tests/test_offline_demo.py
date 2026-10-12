"""Black-box checks for the documented synthetic-only exercise."""
import json
from pathlib import Path
import subprocess
import sys


SAMPLE = Path(__file__).resolve().parents[1]
SCRIPT = SAMPLE / "scripts/offline_demo.py"
PROJECT = "work/art-pilot/synthetic-demo-001"


def run_demo(cwd):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--project", PROJECT],
        cwd=cwd, capture_output=True, text=True,
    )


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_documented_offline_demo_and_refusal(tmp_path):
    runbook = SAMPLE / "docs/runbook.md"
    if runbook.exists():
        assert f"python -I examples/art-pilot/scripts/offline_demo.py --project {PROJECT}" in runbook.read_text(encoding="utf-8")
    result = run_demo(tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    root = tmp_path / PROJECT
    assert Path(report["project"]) == root
    assert report["synthetic"] is True
    assert report["realProviderExecution"] is False
    assert report["realHumanApproval"] is False
    assert report["status"] == "synthetic-adopted"
    for relative in report["artifacts"].values():
        assert (root / relative).is_file()
    receipt = read_json(root / "synthetic-receipt.json")
    assert receipt["invocation"]["provider"] == "offline-synthetic"
    assert "not a real provider execution" in receipt["executionEvidence"]
    human = read_json(root / "synthetic-human.json")
    assert human["reviewer"] == "synthetic-fixture-human"
    assert "not production approval" in human["statement"]
    assert human["actorType"] == "human"
    projection = read_json(root / "production/current/synthetic-demo.json")
    assert projection["status"] == "adopted"
    assert projection["candidate"]["attemptId"] == "synthetic-001"
    assert read_json(root / "design.json")["imageInputs"] == []
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    repeated = run_demo(tmp_path)
    assert repeated.returncode != 0
    assert "new project directory" in repeated.stderr
    assert before == {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_offline_demo_preserves_existing_directory(tmp_path):
    root = tmp_path / PROJECT
    root.mkdir(parents=True)
    sentinel = root / "keep.txt"
    sentinel.write_text("unrelated", encoding="utf-8")
    result = run_demo(tmp_path)
    assert result.returncode != 0
    assert "new project directory" in result.stderr
    assert list(root.iterdir()) == [sentinel]
    assert sentinel.read_text(encoding="utf-8") == "unrelated"
