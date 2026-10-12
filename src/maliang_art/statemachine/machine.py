"""State-machine evaluation and transition application."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from ..core import MaLiangError
from ..ports import Clock
from .config import PolicyModel, PolicyValidationError, TransitionDecl
from .records import transition_payload_id
from .steps import AlignCanvasStep, ChromaKeyStep, StepRegistry


class StateTransitionError(MaLiangError):
    """Raised when a state transition cannot be applied."""


@dataclass(frozen=True)
class TransitionResult:
    record: dict[str, Any]
    record_id: str


class StateMachine:
    def __init__(self, policy: PolicyModel, registry: StepRegistry | None = None) -> None:
        self.policy = policy
        self.registry = registry if registry is not None else StepRegistry.with_builtins()

    def transitions_from(self, state: str) -> tuple[TransitionDecl, ...]:
        return tuple(item for item in self.policy.transitions if state in item.from_states)

    def can_apply(self, state: str, transition_id: str) -> bool:
        try:
            transition = self.policy.transition(transition_id)
        except PolicyValidationError:
            return False
        return state in transition.from_states

    def apply(
        self,
        record: Mapping[str, Any],
        transition_id: str,
        *,
        reviewer: str,
        applied_at: str,
        context: Mapping[str, Any] | None = None,
        clock: Clock | None = None,
    ) -> TransitionResult:
        if not isinstance(record, Mapping):
            raise StateTransitionError("record must be a mapping")
        schema_version = record.get("schemaVersion")
        if isinstance(schema_version, bool) or not isinstance(schema_version, int) or schema_version != 1:
            raise StateTransitionError("record schemaVersion must be 1")
        asset_id = record.get("assetId")
        if not isinstance(asset_id, str) or not asset_id.strip():
            raise StateTransitionError("record assetId must be non-empty text")
        current_state = record.get("state")
        if not isinstance(current_state, str):
            raise StateTransitionError("record state must be text")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise StateTransitionError("reviewer must be non-empty text")
        if not isinstance(applied_at, str) or not applied_at.strip():
            raise StateTransitionError("appliedAt must be non-empty text")
        try:
            parsed = datetime.fromisoformat(applied_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise StateTransitionError("appliedAt must be ISO-8601") from exc
        if parsed.tzinfo is None:
            raise StateTransitionError("appliedAt must include a timezone offset")
        try:
            transition = self.policy.transition(transition_id)
        except PolicyValidationError as exc:
            raise StateTransitionError("unknown transition") from exc
        if current_state not in transition.from_states:
            raise StateTransitionError("transition is not allowed from current state")
        if transition.approver_in is not None:
            try:
                allowed = self.policy.approver_list(transition.approver_in)
            except PolicyValidationError as exc:
                raise StateTransitionError("reviewer is not allowed") from exc
            if reviewer not in allowed:
                raise StateTransitionError("reviewer is not allowed")
        step_results: list[dict[str, Any]] = []
        run_context = dict(context or {})
        for step_id in transition.step_ids:
            decl = self.policy.steps[step_id]
            try:
                step = self.registry.get(decl.action)
                detail = step.run(decl.params, run_context)
            except Exception as exc:  # noqa: BLE001 - boundary: wrap step lookup and run failures
                raise StateTransitionError(f"step failed: {step_id}: {exc}") from exc
            if not isinstance(detail, Mapping):
                raise StateTransitionError("step returned invalid result")
            step_results.append(
                {
                    "stepId": decl.step_id,
                    "action": decl.action,
                    "ok": True,
                    "detail": deepcopy(dict(detail)),
                }
            )
            # Only these built-ins define output as the next image input.
            if type(step) in (ChromaKeyStep, AlignCanvasStep) and "output" in detail:
                run_context["image_path"] = detail["output"]
        payload_for_id = {
            "assetId": asset_id,
            "fromState": current_state,
            "toState": transition.to_state,
            "transitionId": transition.transition_id,
            "reviewer": reviewer,
            "appliedAt": applied_at,
            "stepResults": step_results,
        }
        record_id = transition_payload_id(payload_for_id)
        new_record = {
            "schemaVersion": 1,
            "transitionRecordId": record_id,
            "assetId": asset_id,
            "state": transition.to_state,
            "transitionId": transition.transition_id,
            "reviewer": reviewer,
            "appliedAt": applied_at,
            "stepResults": step_results,
        }
        return TransitionResult(record=new_record, record_id=record_id)
