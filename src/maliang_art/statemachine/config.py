"""YAML policy loading and validation for the state-machine core."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml

from ..core import MaLiangError


class PolicyValidationError(MaLiangError):
    """Raised when a state-machine policy is malformed."""


_STATE_RE = __import__("re").compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_ID_RE = __import__("re").compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

_TOP_LEVEL = {"schemaVersion", "name", "states", "transitions", "steps", "policy"}
_STATE_FIELDS = {"description"}
_TRANSITION_FIELDS = {"id", "from", "to", "steps", "require"}
_REQUIRE_FIELDS = {"approverIn"}


@dataclass(frozen=True)
class StepDecl:
    step_id: str
    action: str
    params: Mapping[str, Any]


@dataclass(frozen=True)
class TransitionDecl:
    transition_id: str
    from_states: tuple[str, ...]
    to_state: str
    step_ids: tuple[str, ...]
    approver_in: str | None


@dataclass(frozen=True)
class PolicyModel:
    schema_version: int
    name: str
    states: tuple[str, ...]
    transitions: tuple[TransitionDecl, ...]
    steps: Mapping[str, StepDecl]
    policy: Mapping[str, Any]
    source_path: str | None

    def transition(self, transition_id: str) -> TransitionDecl:
        for item in self.transitions:
            if item.transition_id == transition_id:
                return item
        raise PolicyValidationError("unknown transition")

    def resolve_approver_path(self, path: str) -> list[Any]:
        """Resolve policy dotted path to a list; empty list is allowed at load time."""
        if not isinstance(path, str) or not path.strip():
            raise PolicyValidationError("approverIn path is invalid")
        parts = path.split(".")
        if parts[0] != "policy" or len(parts) < 2:
            raise PolicyValidationError("approverIn path is invalid")
        current: Any = self.policy
        for part in parts[1:]:
            if not isinstance(current, Mapping) or part not in current:
                raise PolicyValidationError("approverIn path is invalid")
            current = current[part]
        if not isinstance(current, list):
            raise PolicyValidationError("approverIn path is invalid")
        if current and any(not isinstance(item, str) or not item.strip() for item in current):
            raise PolicyValidationError("approverIn path is invalid")
        return list(current)

    def approver_list(self, path: str) -> list[str]:
        """Resolve approvers for apply-time checks; empty list is rejected (fail-closed)."""
        values = self.resolve_approver_path(path)
        if not values:
            raise PolicyValidationError("approverIn path is invalid")
        return [str(item) for item in values]


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PolicyValidationError(f"{name} must be a mapping")
    return deepcopy(value)


def _nonempty_str(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyValidationError(f"{name} must be non-empty text")
    return value


def _normalize_chroma_key(value: Any) -> str:
    if not isinstance(value, str):
        raise PolicyValidationError("step fields are invalid")
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise PolicyValidationError("step fields are invalid")
    try:
        int(text, 16)
    except ValueError as exc:
        raise PolicyValidationError("step fields are invalid") from exc
    return text.upper()


def _parse_steps(raw: Any, registry: Any, *, present: bool) -> dict[str, StepDecl]:
    if not present:
        return {}
    if not isinstance(raw, dict) or not raw:
        raise PolicyValidationError("steps must be a non-empty mapping")
    steps: dict[str, StepDecl] = {}
    for step_id, body in raw.items():
        if not isinstance(step_id, str) or not _ID_RE.fullmatch(step_id):
            raise PolicyValidationError("step fields are invalid")
        if not isinstance(body, dict) or "action" not in body:
            raise PolicyValidationError("step fields are invalid")
        action = _nonempty_str(body["action"], "step action")
        if action not in registry.actions():
            raise PolicyValidationError("unknown step action")
        params = {key: deepcopy(value) for key, value in body.items() if key != "action"}
        if action == "chroma-key":
            if "key" not in params:
                raise PolicyValidationError("step fields are invalid")
            params["key"] = _normalize_chroma_key(params["key"])
        steps[step_id] = StepDecl(step_id=step_id, action=action, params=params)
    return steps


def _parse_transitions(raw: Any, state_names: set[str], steps: Mapping[str, StepDecl]) -> tuple[TransitionDecl, ...]:
    if not isinstance(raw, list) or not raw:
        raise PolicyValidationError("transitions must be a non-empty list")
    seen: set[str] = set()
    parsed: list[TransitionDecl] = []
    for item in raw:
        if not isinstance(item, dict):
            raise PolicyValidationError("transition fields are invalid")
        if set(item) - _TRANSITION_FIELDS or not {"id", "from", "to"} <= set(item):
            raise PolicyValidationError("transition fields are invalid")
        transition_id = item["id"]
        if not isinstance(transition_id, str) or not _ID_RE.fullmatch(transition_id):
            raise PolicyValidationError("transition id is invalid")
        if transition_id in seen:
            raise PolicyValidationError("transition id is duplicated")
        seen.add(transition_id)
        from_raw = item["from"]
        if not isinstance(from_raw, list) or not from_raw or any(not isinstance(s, str) or s not in state_names for s in from_raw):
            raise PolicyValidationError("transition from must be a non-empty list of known states")
        to_state = item["to"]
        if not isinstance(to_state, str) or to_state not in state_names:
            raise PolicyValidationError("transition to must be a known state")
        if "steps" not in item:
            step_ids: tuple[str, ...] = ()
        else:
            steps_raw = item["steps"]
            if not isinstance(steps_raw, list) or any(not isinstance(s, str) or s not in steps for s in steps_raw):
                raise PolicyValidationError("transition steps are invalid")
            step_ids = tuple(steps_raw)
        approver_in: str | None = None
        if "require" in item:
            require = item["require"]
            if not isinstance(require, dict) or set(require) - _REQUIRE_FIELDS:
                raise PolicyValidationError("transition require is invalid")
            if "approverIn" in require:
                approver_in = _nonempty_str(require["approverIn"], "require.approverIn")
        parsed.append(TransitionDecl(transition_id=transition_id, from_states=tuple(from_raw), to_state=to_state, step_ids=step_ids, approver_in=approver_in))
    return tuple(parsed)


def load_policy(path: str | Path, *, registry: Any | None = None) -> PolicyModel:
    from .steps import StepRegistry

    if registry is None:
        registry = StepRegistry.with_builtins()
    policy_path = Path(path)
    try:
        text = policy_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise PolicyValidationError(f"cannot load policy: {exc}") from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PolicyValidationError(f"cannot load policy: {exc}") from exc
    if not isinstance(raw, dict):
        raise PolicyValidationError("policy root must be a mapping")
    if set(raw) - _TOP_LEVEL:
        raise PolicyValidationError("policy fields are invalid")
    version = raw.get("schemaVersion")
    if isinstance(version, bool) or not isinstance(version, int) or version != 1:
        raise PolicyValidationError("unsupported policy schemaVersion")
    name = _nonempty_str(raw.get("name"), "name")
    states_raw = raw.get("states")
    if not isinstance(states_raw, dict) or not states_raw:
        raise PolicyValidationError("states must be a non-empty mapping")
    states: list[str] = []
    for state_name, state_body in states_raw.items():
        if not isinstance(state_name, str) or not _STATE_RE.fullmatch(state_name):
            raise PolicyValidationError("state name is invalid")
        if state_body is not None:
            if not isinstance(state_body, dict) or set(state_body) - _STATE_FIELDS:
                raise PolicyValidationError("state fields are invalid")
            if "description" in state_body and not isinstance(state_body["description"], str):
                raise PolicyValidationError("state fields are invalid")
        states.append(state_name)
    state_names = set(states)
    steps = _parse_steps(raw.get("steps"), registry, present="steps" in raw)
    transitions = _parse_transitions(raw.get("transitions"), state_names, steps)
    if "policy" in raw:
        policy_section = raw["policy"]
        if policy_section is None:
            raise PolicyValidationError("policy must be a mapping")
        policy_map = _mapping(policy_section, "policy")
    else:
        policy_map = {}
    model = PolicyModel(schema_version=1, name=name, states=tuple(states), transitions=transitions, steps=steps, policy=policy_map, source_path=str(policy_path))
    for transition in transitions:
        if transition.approver_in is not None:
            model.resolve_approver_path(transition.approver_in)
    return model
