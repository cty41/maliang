"""State-machine core: YAML policy, steps, and transition evaluation."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from .config import PolicyModel, PolicyValidationError, StepDecl, TransitionDecl, load_policy
from .machine import StateMachine, StateTransitionError
from .steps import StepRegistry

__all__ = [
    "PolicyValidationError",
    "StateTransitionError",
    "StateMachine",
    "StepRegistry",
    "load_policy",
    "PolicyModel",
    "TransitionDecl",
    "StepDecl",
    "builtin_template_path",
    "default_template_text",
]


def builtin_template_path() -> Path:
    """Return the packaged default-policy.yaml path.

    Prefer default_template_text() when the package may be loaded from a zip
    importer; this path is reliable for normal wheel installs.
    """
    ref = resources.files("maliang_art.statemachine").joinpath("templates/default-policy.yaml")
    return Path(str(ref))


def default_template_text() -> str:
    return resources.files("maliang_art.statemachine").joinpath("templates/default-policy.yaml").read_text(encoding="utf-8")
