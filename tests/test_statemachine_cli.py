from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from maliang_art.cli import main


def test_flow_validate_template(capsys, tmp_path):
    code = main(["flow", "show-default-template"])
    assert code == 0
    template = capsys.readouterr().out
    path = tmp_path / "policy.yaml"
    path.write_text(template, encoding="utf-8")
    code = main(["flow", "validate", str(path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "valid policy: default-art-pipeline" in out


def test_flow_validate_invalid(tmp_path, capsys):
    path = tmp_path / "bad.yaml"
    path.write_text("schemaVersion: 1\nname: x\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        main(["flow", "validate", str(path)])
    assert exc.value.code not in (0, None)


def test_flow_show_default_template(capsys):
    assert main(["flow", "show-default-template"]) == 0
    out = capsys.readouterr().out
    assert "default-art-pipeline" in out
    assert "submit-for-review" in out


def test_flow_transitions_draft(capsys, tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(
        textwrap.dedent(
            """
            schemaVersion: 1
            name: demo
            states:
              draft:
              review:
              done:
            transitions:
              - id: submit-for-review
                from: [draft]
                to: review
              - id: approve
                from: [review]
                to: done
            """
        ).lstrip(),
        encoding="utf-8",
    )
    assert main(["flow", "transitions", str(path), "--state", "draft"]) == 0
    out = capsys.readouterr().out
    assert "submit-for-review -> review" in out
    assert "approve" not in out


def test_flow_transitions_unknown_state(tmp_path, capsys):
    path = tmp_path / "policy.yaml"
    path.write_text(
        textwrap.dedent(
            """
            schemaVersion: 1
            name: demo
            states:
              draft:
            transitions:
              - id: stay
                from: [draft]
                to: draft
            """
        ).lstrip(),
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as exc:
        main(["flow", "transitions", str(path), "--state", "nope"])
    assert exc.value.code not in (0, None)

