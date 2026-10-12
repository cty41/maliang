from __future__ import annotations

import textwrap
from copy import deepcopy
from dataclasses import replace

from PIL import Image

from maliang_art.statemachine.records import transition_payload_id
from maliang_art.statemachine.steps import StepRegistry
from pathlib import Path

import pytest

from maliang_art.statemachine import (
    PolicyValidationError,
    StateMachine,
    StateTransitionError,
    load_policy,
)
from maliang_art.statemachine.config import PolicyModel, StepDecl, TransitionDecl


def make_policy(*, approvers: list[str] | None = None, with_steps: bool = False) -> PolicyModel:
    steps = {}
    transitions = [
        TransitionDecl("submit-for-review", ("draft",), "review", (), None),
        TransitionDecl("approve", ("review",), "done", (), "policy.approvers"),
    ]
    if with_steps:
        steps = {
            "clean": StepDecl("clean", "chroma-key", {"key": "FF00FF", "tolerance": 0}),
            "fit": StepDecl("fit", "align-canvas", {"canvas": [16, 16]}),
            "bad": StepDecl("bad", "chroma-key", {"key": "not-a-key"}),
        }
        transitions = [
            TransitionDecl("submit-for-review", ("draft",), "review", ("clean", "fit"), None),
            TransitionDecl("approve", ("review",), "done", (), "policy.approvers"),
            TransitionDecl("submit-bad", ("draft",), "review", ("bad",), None),
        ]
    return PolicyModel(
        schema_version=1,
        name="demo",
        states=("draft", "review", "done", "rejected"),
        transitions=tuple(transitions),
        steps=steps,
        policy={"approvers": [] if approvers is None else approvers},
        source_path=None,
    )


def base_record(state: str = "draft") -> dict:
    return {"schemaVersion": 1, "assetId": "asset-1", "state": state}


class EvidenceStep:
    action = "evidence"

    def __init__(self, detail):
        self.detail = detail

    def run(self, params, context):
        return self.detail


def apply_steps(step_ids, *, context=None, registry=None):
    policy = make_policy(with_steps=True)
    policy = replace(
        policy,
        steps={**policy.steps, "note": StepDecl("note", "evidence", {})},
        transitions=(TransitionDecl("run", ("draft",), "review", tuple(step_ids), None),),
    )
    return StateMachine(policy, registry).apply(
        base_record(), "run", reviewer="alice", applied_at="2026-01-01T12:00:00Z", context=context,
    )


@pytest.mark.parametrize("same_path", [False, True])
@pytest.mark.parametrize("step_ids", [("clean",), ("clean", "fit"), ("clean", "note", "fit")])
def test_image_steps_chain_outputs(tmp_path, same_path, step_ids):
    source = tmp_path / "source.png"
    output = source if same_path else tmp_path / "output.png"
    Image.new("RGBA", (4, 4), "magenta").save(source)
    registry = StepRegistry.with_builtins()
    registry.register("evidence", EvidenceStep({"output": "not-an-image.png"}))
    context = {"image_path": str(source), "image_out": str(output)}
    result = apply_steps(step_ids, context=context, registry=registry)
    with Image.open(output) as image:
        assert image.getchannel("A").getextrema() == (0, 0)
        assert image.size == ((16, 16) if "fit" in step_ids else (4, 4))
    assert context["image_path"] == str(source)
    assert len(result.record["stepResults"]) == len(step_ids)
    if not same_path:
        with Image.open(source) as image:
            assert image.getchannel("A").getextrema() == (255, 255)


@pytest.mark.parametrize("mutate_during_run", [False, True])
def test_step_evidence_is_snapshotted_before_later_mutation(mutate_during_run):
    shared = {"nested": {"values": [1]}}
    original = deepcopy(shared)
    registry = StepRegistry()
    registry.register("evidence", EvidenceStep(shared))

    class MutatingStep:
        action = "align-canvas"

        def run(self, params, context):
            context["shared"]["nested"]["values"].append(2)
            return {"mutated": True}

    registry.register("align-canvas", MutatingStep())
    result = apply_steps(("note", "fit") if mutate_during_run else ("note",),
                         registry=registry, context={"shared": shared})
    shared["nested"]["values"].append(3)
    shared["nested"]["held"] = [4]
    assert result.record["stepResults"][0]["detail"] == original
    record = result.record
    payload = {key: record[key] for key in ("assetId", "transitionId", "reviewer", "appliedAt", "stepResults")}
    payload.update(fromState="draft", toState="review")
    assert transition_payload_id(payload) == result.record_id


def test_custom_step_using_builtin_action_does_not_chain_arbitrary_output(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    Image.new("RGBA", (4, 4), "magenta").save(source)
    registry = StepRegistry()
    registry.register("chroma-key", EvidenceStep({"output": "not-an-image.png"}))
    registry.register("align-canvas", StepRegistry.with_builtins().get("align-canvas"))
    apply_steps(("clean", "fit"), registry=registry,
                context={"image_path": str(source), "image_out": str(output)})
    with Image.open(output) as image:
        assert image.getchannel("A").getextrema() == (0, 255)


def test_nested_evidence_keeps_existing_identity_algorithm():
    detail = {"nested": {"values": [1, "text", None, True]}}
    registry = StepRegistry()
    registry.register("evidence", EvidenceStep(detail))
    result = apply_steps(("note",), registry=registry)
    expected = transition_payload_id({
        "assetId": "asset-1", "fromState": "draft", "toState": "review", "transitionId": "run",
        "reviewer": "alice", "appliedAt": "2026-01-01T12:00:00Z",
        "stepResults": [{"stepId": "note", "action": "evidence", "ok": True, "detail": detail}],
    })
    assert result.record_id == expected


@pytest.mark.parametrize("invalid", [{1}, float("nan"), object()])
def test_nested_evidence_still_requires_json_values(invalid):
    from maliang_art.core import MaLiangError

    registry = StepRegistry()
    registry.register("evidence", EvidenceStep({"nested": [invalid]}))
    with pytest.raises(MaLiangError):
        apply_steps(("note",), registry=registry)


def test_later_step_failure_does_not_return_success(tmp_path):
    source = tmp_path / "source.png"
    output = tmp_path / "output.png"
    Image.new("RGBA", (4, 4), "magenta").save(source)
    with pytest.raises(StateTransitionError, match="step failed: bad"):
        apply_steps(("clean", "bad"), context={"image_path": str(source), "image_out": str(output)})
    with Image.open(output) as image:
        assert image.getchannel("A").getextrema() == (0, 0)


def test_draft_to_review_success_record_shape():
    machine = StateMachine(make_policy())
    result = machine.apply(
        base_record("draft"),
        "submit-for-review",
        reviewer="alice",
        applied_at="2026-01-01T12:00:00Z",
    )
    record = result.record
    assert record["schemaVersion"] == 1
    assert record["state"] == "review"
    assert record["assetId"] == "asset-1"
    assert record["transitionId"] == "submit-for-review"
    assert record["reviewer"] == "alice"
    assert record["appliedAt"] == "2026-01-01T12:00:00Z"
    assert record["stepResults"] == []
    assert record["transitionRecordId"] == result.record_id
    assert result.record_id.startswith("state-transition-")


def test_wrong_state_rejected():
    machine = StateMachine(make_policy())
    with pytest.raises(StateTransitionError, match="not allowed from current state"):
        machine.apply(base_record("review"), "submit-for-review", reviewer="alice", applied_at="2026-01-01T12:00:00Z")


def test_unknown_transition_rejected():
    machine = StateMachine(make_policy())
    with pytest.raises(StateTransitionError, match="unknown transition"):
        machine.apply(base_record("draft"), "nope", reviewer="alice", applied_at="2026-01-01T12:00:00Z")


def test_approve_empty_approvers_rejected():
    machine = StateMachine(make_policy(approvers=[]))
    with pytest.raises(StateTransitionError, match="reviewer is not allowed"):
        machine.apply(base_record("review"), "approve", reviewer="alice", applied_at="2026-01-01T12:00:00Z")


def test_approve_with_allowed_reviewer():
    machine = StateMachine(make_policy(approvers=["alice", "bob"]))
    result = machine.apply(base_record("review"), "approve", reviewer="bob", applied_at="2026-01-01T12:00:00Z")
    assert result.record["state"] == "done"


def test_step_failure_does_not_return_success():
    machine = StateMachine(make_policy(with_steps=True))
    with pytest.raises(StateTransitionError, match="step failed: bad"):
        machine.apply(
            base_record("draft"),
            "submit-bad",
            reviewer="alice",
            applied_at="2026-01-01T12:00:00Z",
            context={"image_path": None},
        )


def test_step_order_in_results():
    machine = StateMachine(make_policy(with_steps=True))
    result = machine.apply(
        base_record("draft"),
        "submit-for-review",
        reviewer="alice",
        applied_at="2026-01-01T12:00:00Z",
        context={"image_path": None},
    )
    actions = [item["action"] for item in result.record["stepResults"]]
    assert actions == ["chroma-key", "align-canvas"]
    assert all(item["detail"].get("skipped") is True for item in result.record["stepResults"])


def test_can_apply_and_transitions_from():
    machine = StateMachine(make_policy())
    assert machine.can_apply("draft", "submit-for-review") is True
    assert machine.can_apply("review", "submit-for-review") is False
    assert machine.can_apply("draft", "missing") is False
    ids = [item.transition_id for item in machine.transitions_from("draft")]
    assert ids == ["submit-for-review"]


def test_apply_validation_order_reviewer_before_state():
    machine = StateMachine(make_policy())
    with pytest.raises(StateTransitionError, match="reviewer must be non-empty text"):
        machine.apply(base_record("done"), "submit-for-review", reviewer=" ", applied_at="2026-01-01T12:00:00Z")


def test_apply_validation_order_unknown_transition_before_state():
    machine = StateMachine(make_policy())
    with pytest.raises(StateTransitionError, match="unknown transition"):
        machine.apply(base_record("done"), "missing", reviewer="alice", applied_at="2026-01-01T12:00:00Z")


def test_apply_validation_order_state_before_approver():
    machine = StateMachine(make_policy(approvers=[]))
    with pytest.raises(StateTransitionError, match="not allowed from current state"):
        machine.apply(base_record("draft"), "approve", reviewer="alice", applied_at="2026-01-01T12:00:00Z")


def test_missing_applied_at_timezone():
    machine = StateMachine(make_policy())
    with pytest.raises(StateTransitionError, match="timezone"):
        machine.apply(base_record("draft"), "submit-for-review", reviewer="alice", applied_at="2026-01-01T12:00:00")


def test_load_policy_from_yaml(tmp_path: Path):
    path = tmp_path / "p.yaml"
    path.write_text(
        textwrap.dedent(
            """
            schemaVersion: 1
            name: yaml-demo
            states:
              draft:
              review:
            transitions:
              - id: submit-for-review
                from: [draft]
                to: review
            policy:
              approvers: []
            """
        ).lstrip(),
        encoding="utf-8",
    )
    policy = load_policy(path)
    machine = StateMachine(policy)
    result = machine.apply(base_record("draft"), "submit-for-review", reviewer="x", applied_at="2026-01-01T00:00:00Z")
    assert result.record["state"] == "review"
