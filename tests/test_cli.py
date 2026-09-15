from __future__ import annotations

import json

from PIL import Image

from maliang_art.cli import main


def test_pose_render_and_select_cli(tmp_path, draft, capsys):
    spec = tmp_path / "draft.json"; spec.write_text(json.dumps(draft), encoding="utf-8")
    assert main(["pose", "render-options", "--spec", str(spec), "--output", str(tmp_path / "board.png"), "--preview-dir", str(tmp_path / "previews"), "--preview-size", "96x64"]) == 0
    with Image.open(tmp_path / "board.png") as image: assert image.size == (600, 410)
    with Image.open(tmp_path / "previews" / "a.png") as image: assert image.size == (96, 64)
    assert main(["pose", "select-option", "--spec", str(spec), "--option-id", "a", "--output-card", str(tmp_path / "card.json"), "--reviewer", "director", "--reason", "clear", "--rejected-reason", "b=less clear", "--selected-at", "2026-01-01T00:00:00Z"]) == 0
    assert "poseProofId" in capsys.readouterr().out


def test_records_validate_and_check_cli(tmp_path, draft, capsys):
    path = tmp_path / "draft.json"; path.write_text(json.dumps(draft), encoding="utf-8")
    assert main(["records", "validate", str(path), "--schema", "pose-draft"]) == 0
    assert main(["records", "check", str(tmp_path)]) == 0
    assert "0 error(s)" in capsys.readouterr().out


def test_review_validate_cli(tmp_path):
    rule = {"schemaVersion": 1, "ruleId": "r", "version": 1, "scope": {"project": "demo"}, "authority": "advisory", "autoRetryEligible": False, "requiredEvidenceRoles": [], "sources": [{"type": "guide", "id": "g"}], "positiveCaseIds": [], "negativeCaseIds": [], "lifecycle": "active", "statement": "synthetic"}
    path = tmp_path / "rule.json"; path.write_text(json.dumps(rule), encoding="utf-8")
    assert main(["review", "validate", "rule", str(path), "--authority-reviewer", "art-director"]) == 0
