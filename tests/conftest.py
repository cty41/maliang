from __future__ import annotations

import copy
import pytest


@pytest.fixture
def draft():
    value = {
        "schemaVersion": 1,
        "assetId": "asset-synthetic",
        "characterId": "character-synthetic",
        "poseId": "cast",
        "direction": "down-right",
        "visualMoment": {"consumer": "test", "phase": "release", "spriteRole": "action"},
        "canvas": [256, 256],
        "options": [],
    }
    for option_id, shift in (("a", 0), ("b", 8)):
        value["options"].append({
            "optionId": option_id, "title": f"Option {option_id}", "caption": "Synthetic geometry",
            "head": {"center": [128 + shift, 48], "radius": 16},
            "spine": [[128 + shift, 64], [128, 160]],
            "segments": [[[128, 80], [80, 120]], [[128, 80], [176, 120]], [[128, 160], [96, 220]], [[128, 160], [160, 220]]],
            "supportPoints": [[96, 220], [160, 220]], "contactPoints": [[80, 120], [176, 120]],
            "equipmentAxis": [[80, 180], [180, 70]],
        })
    return copy.deepcopy(value)
