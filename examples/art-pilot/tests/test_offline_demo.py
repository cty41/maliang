"""Black-box checks for the documented synthetic-only exercise."""
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


SAMPLE = Path(__file__).resolve().parents[1]
SCRIPT = SAMPLE / "scripts/offline_demo.py"
PROJECT = "work/art-pilot/synthetic-demo-001"


def run_demo(cwd, command=None):
    return subprocess.run(
        command if command is not None else [sys.executable, "-I", str(SCRIPT), "--project", PROJECT],
        cwd=cwd, capture_output=True, text=True,
    )


def documented_demo_command():
    root = SAMPLE.parents[1]
    commands = []
    for filename in ("README.md", "README.zh-CN.md"):
        source = (root / filename).read_text(encoding="utf-8")
        blocks = re.findall(r"^```[^\n]*\n(.*?)^```\s*$", source, re.MULTILINE | re.DOTALL)
        candidates = [
            shlex.split(line.strip())
            for block in blocks for line in block.splitlines()
            if "offline_demo.py" in line
        ]
        assert len(candidates) == 1, (filename, candidates)
        commands.append(candidates[0])
    assert commands[0] == commands[1], commands
    command = commands[0]
    assert command[:4] == ["python", "-I", "examples/art-pilot/scripts/offline_demo.py", "--project"]
    assert len(command) == 5, command
    project = Path(command[4])
    assert not project.is_absolute() and ".." not in project.parts
    assert project.parts[:2] == ("work", "art-pilot")
    # Only relocate the interpreter and script; run the documented arguments unchanged.
    return [sys.executable, command[1], str(root / command[2]), *command[3:]]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_documented_offline_demo_and_refusal(tmp_path):
    command = documented_demo_command()
    result = run_demo(tmp_path, command)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    root = tmp_path / command[-1]
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
    repeated = run_demo(tmp_path, command)
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
