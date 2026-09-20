from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from maliang_art.statemachine import PolicyValidationError, builtin_template_path, default_template_text, load_policy


def write_policy(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "policy.yaml"
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return path


def test_builtin_template_loads():
    path = builtin_template_path()
    policy = load_policy(path)
    assert policy.name == "default-art-pipeline"
    assert policy.states == ("draft", "review", "done", "rejected")
    assert policy.source_path is not None
    assert default_template_text().startswith("schemaVersion: 1")


def test_empty_approvers_load():
    policy = load_policy(builtin_template_path())
    approve = policy.transition("approve")
    assert approve.approver_in == "policy.approvers"
    assert policy.policy["approvers"] == []


def test_rule1_unknown_top_level(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null}
        transitions:
          - {id: go, from: [draft], to: draft}
        extra: true
    """)
    with pytest.raises(PolicyValidationError, match="policy fields are invalid"):
        load_policy(path)


def test_rule2_bad_schema_version(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 2
        name: demo
        states: {draft: null}
        transitions:
          - {id: go, from: [draft], to: draft}
    """)
    with pytest.raises(PolicyValidationError, match="unsupported policy schemaVersion"):
        load_policy(path)


def test_rule3_empty_name(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: " "
        states: {draft: null}
        transitions:
          - {id: go, from: [draft], to: draft}
    """)
    with pytest.raises(PolicyValidationError, match="name must be non-empty text"):
        load_policy(path)


def test_rule4_states_must_be_mapping(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: []
        transitions:
          - {id: go, from: [draft], to: draft}
    """)
    with pytest.raises(PolicyValidationError, match="states must be a non-empty mapping"):
        load_policy(path)


def test_rule4_invalid_state_name(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states:
          "bad name": null
        transitions:
          - {id: go, from: [draft], to: draft}
    """)
    with pytest.raises(PolicyValidationError, match="state name is invalid"):
        load_policy(path)


def test_rule5_state_fields_invalid(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states:
          draft:
            nope: 1
        transitions:
          - {id: go, from: [draft], to: draft}
    """)
    with pytest.raises(PolicyValidationError, match="state fields are invalid"):
        load_policy(path)


def test_rule6_transitions_empty(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null}
        transitions: []
    """)
    with pytest.raises(PolicyValidationError, match="transitions must be a non-empty list"):
        load_policy(path)


def test_rule7_transition_fields(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null}
        transitions:
          - {id: go, from: [draft], to: draft, nope: 1}
    """)
    with pytest.raises(PolicyValidationError, match="transition fields are invalid"):
        load_policy(path)


def test_rule8_invalid_and_duplicate_id(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        transitions:
          - {id: "bad id", from: [draft], to: review}
    """)
    with pytest.raises(PolicyValidationError, match="transition id is invalid"):
        load_policy(path)
    path2 = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        transitions:
          - {id: go, from: [draft], to: review}
          - {id: go, from: [review], to: draft}
    """)
    with pytest.raises(PolicyValidationError, match="transition id is duplicated"):
        load_policy(path2)


def test_rule9_unknown_from_state(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        transitions:
          - {id: go, from: [missing], to: review}
    """)
    with pytest.raises(PolicyValidationError, match="transition from must be a non-empty list of known states"):
        load_policy(path)


def test_rule10_unknown_to_state(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        transitions:
          - {id: go, from: [draft], to: missing}
    """)
    with pytest.raises(PolicyValidationError, match="transition to must be a known state"):
        load_policy(path)


def test_rule11_unknown_step_reference(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        steps:
          clean:
            action: chroma-key
            key: "#ff00ff"
        transitions:
          - {id: go, from: [draft], to: review, steps: [nope]}
    """)
    with pytest.raises(PolicyValidationError, match="transition steps are invalid"):
        load_policy(path)


def test_rule12_require_fields(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        policy: {approvers: [alice]}
        transitions:
          - {id: go, from: [draft], to: review, require: {nope: x}}
    """)
    with pytest.raises(PolicyValidationError, match="transition require is invalid"):
        load_policy(path)


def test_rule13_approver_path_must_start_with_policy(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        policy: {approvers: [alice]}
        transitions:
          - {id: go, from: [draft], to: review, require: {approverIn: reviewers.list}}
    """)
    with pytest.raises(PolicyValidationError, match="approverIn path is invalid"):
        load_policy(path)


def test_rule14_empty_approvers_allowed_at_load(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        policy: {approvers: []}
        transitions:
          - {id: go, from: [draft], to: review, require: {approverIn: policy.approvers}}
    """)
    policy = load_policy(path)
    assert policy.policy["approvers"] == []


def test_rule14_invalid_approver_entries_rejected_at_load(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        policy: {approvers: ["alice", 3]}
        transitions:
          - {id: go, from: [draft], to: review, require: {approverIn: policy.approvers}}
    """)
    with pytest.raises(PolicyValidationError, match="approverIn path is invalid"):
        load_policy(path)
    path2 = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        policy: {approvers: [" "]}
        transitions:
          - {id: go, from: [draft], to: review, require: {approverIn: policy.approvers}}
    """)
    with pytest.raises(PolicyValidationError, match="approverIn path is invalid"):
        load_policy(path2)


def test_explicit_null_steps_rejected(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        steps: null
        transitions:
          - {id: go, from: [draft], to: review}
    """)
    with pytest.raises(PolicyValidationError, match="steps must be a non-empty mapping"):
        load_policy(path)


def test_explicit_null_transition_steps_rejected(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        transitions:
          - {id: go, from: [draft], to: review, steps: null}
    """)
    with pytest.raises(PolicyValidationError, match="transition steps are invalid"):
        load_policy(path)


def test_explicit_null_require_rejected(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        transitions:
          - {id: go, from: [draft], to: review, require: null}
    """)
    with pytest.raises(PolicyValidationError, match="transition require is invalid"):
        load_policy(path)


def test_explicit_null_policy_rejected(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null}
        transitions:
          - {id: go, from: [draft], to: draft}
        policy: null
    """)
    with pytest.raises(PolicyValidationError, match="policy must be a mapping"):
        load_policy(path)


def test_chroma_key_normalized_on_load(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        steps:
          clean:
            action: chroma-key
            key: "#ff00ff"
        transitions:
          - {id: go, from: [draft], to: review, steps: [clean]}
    """)
    policy = load_policy(path)
    assert policy.steps["clean"].params["key"] == "FF00FF"


def test_rule15_unknown_step_action(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null, review: null}
        steps:
          bad:
            action: not-a-step
        transitions:
          - {id: go, from: [draft], to: review, steps: [bad]}
    """)
    with pytest.raises(PolicyValidationError, match="unknown step action"):
        load_policy(path)


def test_rule16_policy_must_be_mapping(tmp_path):
    path = write_policy(tmp_path, """
        schemaVersion: 1
        name: demo
        states: {draft: null}
        transitions:
          - {id: go, from: [draft], to: draft}
        policy: []
    """)
    with pytest.raises(PolicyValidationError, match="policy must be a mapping"):
        load_policy(path)


def test_missing_file(tmp_path):
    with pytest.raises(PolicyValidationError, match="cannot load policy"):
        load_policy(tmp_path / "missing.yaml")
