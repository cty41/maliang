"""Stable identity helper for state-transition records."""
from __future__ import annotations

from typing import Any, Mapping

from ..core import stable_id


def transition_payload_id(payload: Mapping[str, Any]) -> str:
    return stable_id("state-transition", payload)
