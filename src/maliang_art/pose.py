"""Deterministic stick-figure pose-option drafting and selection."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from .adapters import PillowImageAdapter
from .core import MaLiangError, stable_id, write_immutable_json

ORANGE = (255, 106, 0, 255)
BACKGROUND = (10, 10, 12, 255)
TEXT = (220, 220, 220, 255)
DIVIDER = (55, 55, 60, 255)
DIRECTIONS = {"down-right", "up-left", "down-left", "up-right", "non-directional"}
DRAFT_KEYS = {"schemaVersion", "assetId", "characterId", "poseId", "direction", "visualMoment", "canvas", "options", "historicalEvidence"}
OPTION_KEYS = {"optionId", "title", "caption", "head", "spine", "segments", "supportPoints", "contactPoints", "equipmentAxis"}


class PoseProofError(MaLiangError):
    pass


def _timestamp(value: Any) -> None:
    if not isinstance(value, str):
        raise PoseProofError("selected-at must be ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise PoseProofError("selected-at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise PoseProofError("selected-at must include a timezone offset")


def _size(value: Any, label: str, *, minimum: int = 1, maximum: int = 8192) -> tuple[int, int]:
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(channel) is not int or not minimum <= channel <= maximum for channel in value)):
        raise PoseProofError(f"{label} must be two integers from {minimum} through {maximum}")
    return value[0], value[1]


def _point(value: Any, canvas: list[int], label: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2 or any(type(channel) is not int for channel in value):
        raise PoseProofError(f"{label} must be an integer [x,y] point")
    x, y = value
    if not 0 <= x < canvas[0] or not 0 <= y < canvas[1]:
        raise PoseProofError(f"{label} is outside the canvas")
    return x, y


def validate_draft(draft: Any) -> dict[str, Any]:
    if not isinstance(draft, dict) or set(draft) - DRAFT_KEYS:
        raise PoseProofError("draft contains unknown fields or is not an object")
    required = DRAFT_KEYS - {"historicalEvidence"}
    if draft.get("schemaVersion") != 1 or required - set(draft):
        raise PoseProofError("draft is missing required schema v1 fields")
    for key in ("assetId", "characterId", "poseId", "direction"):
        if not isinstance(draft.get(key), str) or not draft[key].strip():
            raise PoseProofError(f"{key} must be a non-empty string")
    if draft["direction"] not in DIRECTIONS:
        raise PoseProofError("draft direction is invalid")
    canvas = draft["canvas"]
    canvas_width, canvas_height = _size(canvas, "pose proof canvas", minimum=16)
    moment = draft["visualMoment"]
    if not isinstance(moment, dict) or set(moment) != {"consumer", "phase", "spriteRole"} or any(not isinstance(moment[key], str) or not moment[key].strip() for key in moment):
        raise PoseProofError("visualMoment must define consumer, phase, and spriteRole")
    options = draft["options"]
    if not isinstance(options, list) or not 1 <= len(options) <= 4 or not all(isinstance(item, dict) for item in options):
        raise PoseProofError("draft must contain 1-4 pose options")
    ids: set[str] = set()
    for index, option in enumerate(options):
        if set(option) != OPTION_KEYS:
            raise PoseProofError(f"option {index} fields are invalid")
        option_id = option["optionId"]
        if not isinstance(option_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", option_id) or option_id in ids:
            raise PoseProofError("optionId values must be unique safe slugs")
        ids.add(option_id)
        if any(not isinstance(option[key], str) or not option[key].strip() for key in ("title", "caption")):
            raise PoseProofError(f"option {option_id} needs title and caption")
        head = option["head"]
        if not isinstance(head, dict) or set(head) != {"center", "radius"}:
            raise PoseProofError(f"option {option_id} head is invalid")
        _point(head["center"], canvas, f"option {option_id} head center")
        if (type(head["radius"]) is not int or head["radius"] < 1
                or head["radius"] > min(canvas_width, canvas_height) // 4):
            raise PoseProofError(f"option {option_id} head radius is invalid for the canvas")
        if not isinstance(option["spine"], list) or len(option["spine"]) != 2:
            raise PoseProofError(f"option {option_id} spine is invalid")
        for point in option["spine"]:
            _point(point, canvas, f"option {option_id} spine")
        if not isinstance(option["segments"], list) or not option["segments"]:
            raise PoseProofError(f"option {option_id} segments is invalid")
        for polyline in option["segments"]:
            if not isinstance(polyline, list) or len(polyline) < 2:
                raise PoseProofError(f"option {option_id} segment is invalid")
            for point in polyline:
                _point(point, canvas, f"option {option_id} segment")
        for field in ("supportPoints", "contactPoints"):
            if not isinstance(option[field], list):
                raise PoseProofError(f"option {option_id} {field} is invalid")
            for point in option[field]:
                _point(point, canvas, f"option {option_id} {field}")
        axis = option["equipmentAxis"]
        if axis is not None:
            if not isinstance(axis, list) or len(axis) != 2:
                raise PoseProofError(f"option {option_id} equipmentAxis is invalid")
            for point in axis:
                _point(point, canvas, f"option {option_id} equipmentAxis")
    evidence = draft.get("historicalEvidence")
    if evidence is not None:
        from .records import validate_artifact
        try:
            validate_artifact(evidence)
        except MaLiangError as exc:
            raise PoseProofError("historicalEvidence is invalid") from exc
    return draft


def validate_card(card: Any) -> dict[str, Any]:
    if not isinstance(card, dict):
        raise PoseProofError("pose proof card must be an object")
    optional = {"historicalEvidence"}
    required = {"schemaVersion", "poseProofId", "assetId", "characterId", "poseId", "direction", "canvas", "visualMoment", "selectedOption", "selection"}
    if set(card) - required - optional or required - set(card) or card.get("schemaVersion") != 1:
        raise PoseProofError("pose proof card fields are invalid")
    pseudo = {"schemaVersion": 1, "assetId": card["assetId"], "characterId": card["characterId"], "poseId": card["poseId"], "direction": card["direction"], "visualMoment": card["visualMoment"], "canvas": card["canvas"], "options": [card["selectedOption"]]}
    if card.get("historicalEvidence") is not None:
        pseudo["historicalEvidence"] = card["historicalEvidence"]
    validate_draft(pseudo)
    selection = card["selection"]
    if not isinstance(selection, dict) or set(selection) != {"optionId", "reviewer", "reason", "rejectedOptions", "selectedAt"} or selection.get("optionId") != card["selectedOption"]["optionId"] or not isinstance(selection.get("reviewer"), str) or not selection["reviewer"].strip() or not isinstance(selection.get("reason"), str) or not selection["reason"].strip() or not isinstance(selection.get("rejectedOptions"), list) or not all(isinstance(item, dict) and set(item) == {"optionId", "reason"} and isinstance(item["optionId"], str) and isinstance(item["reason"], str) and item["reason"].strip() for item in selection["rejectedOptions"]):
        raise PoseProofError("pose proof card selection is invalid")
    rejected_ids = [item["optionId"] for item in selection["rejectedOptions"]]
    if len(rejected_ids) != len(set(rejected_ids)) or selection["optionId"] in rejected_ids:
        raise PoseProofError("pose proof card rejected option ids are invalid")
    _timestamp(selection["selectedAt"])
    payload = {key: value for key, value in card.items() if key not in {"schemaVersion", "poseProofId"}}
    if card["poseProofId"] != stable_id("pose-proof", payload):
        raise PoseProofError("pose proof card identity is invalid")
    return card


def load_draft(path: str | Path) -> dict[str, Any]:
    try:
        return validate_draft(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PoseProofError(f"cannot load pose proof draft: {exc}") from exc


def _draw_option(image: Image.Image, option: dict[str, Any], origin: tuple[int, int], scale: float = 1.0) -> None:
    draw = ImageDraw.Draw(image)
    ox, oy = origin
    def point(value: list[int]) -> tuple[int, int]:
        return round(ox + value[0] * scale), round(oy + value[1] * scale)
    width = max(3, round(10 * scale))
    center = point(option["head"]["center"])
    radius = round(option["head"]["radius"] * scale)
    draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline=ORANGE, width=width)
    draw.line([point(value) for value in option["spine"]], fill=ORANGE, width=width, joint="curve")
    for segment in option["segments"]:
        draw.line([point(value) for value in segment], fill=ORANGE, width=width, joint="curve")
    for field, radius_value in (("supportPoints", 5), ("contactPoints", 4)):
        for value in option[field]:
            x, y = point(value)
            radius = max(2, round(radius_value * scale))
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=ORANGE)
    if option["equipmentAxis"] is not None:
        draw.line([point(value) for value in option["equipmentAxis"]], fill=ORANGE, width=max(2, round(5 * scale)))


def render_board(draft: dict[str, Any]) -> Image.Image:
    validate_draft(draft)
    canvas_width, canvas_height = draft["canvas"]
    panel_width = max(300, canvas_width + 44)
    art_height = max(300, canvas_height + 44)
    footer = 110
    image = Image.new("RGBA", (panel_width * len(draft["options"]), art_height + footer), BACKGROUND)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    for index, option in enumerate(draft["options"]):
        origin_x = index * panel_width
        if index:
            draw.line((origin_x, 0, origin_x, image.height), fill=DIVIDER, width=2)
        _draw_option(image, option, (origin_x + 22, 20), 0.84)
        draw.text((origin_x + panel_width // 2, 12), option["optionId"], fill=TEXT, font=font, anchor="ma")
        draw.text((origin_x + 18, art_height + 18), option["title"], fill=TEXT, font=font)
        draw.text((origin_x + 18, art_height + 42), option["caption"][:42], fill=TEXT, font=font)
    return image


def render_preview(
    option: dict[str, Any], canvas: list[int] | tuple[int, int],
    size: list[int] | tuple[int, int] | None = None,
) -> Image.Image:
    """Render an option at an explicit size or half its declared canvas size."""
    canvas_width, canvas_height = _size(canvas, "pose proof canvas", minimum=16)
    if size is None:
        preview_width = max(1, round(canvas_width / 2))
        preview_height = max(1, round(canvas_height / 2))
    else:
        preview_width, preview_height = _size(size, "preview size")
    scale = min(preview_width / canvas_width, preview_height / canvas_height)
    origin = (
        round((preview_width - canvas_width * scale) / 2),
        round((preview_height - canvas_height * scale) / 2),
    )
    image = Image.new("RGBA", (preview_width, preview_height), BACKGROUND)
    _draw_option(image, option, origin, scale)
    return image


def select_option(draft: dict[str, Any], option_id: str, reviewer: str, reason: str, rejected_reasons: dict[str, str], selected_at: str) -> dict[str, Any]:
    validate_draft(draft)
    _timestamp(selected_at)
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise PoseProofError("pose proof selection requires a reviewer")
    if not reason.strip():
        raise PoseProofError("pose proof selection requires a reason")
    selected = next((item for item in draft["options"] if item["optionId"] == option_id), None)
    if selected is None:
        raise PoseProofError("selected option does not exist")
    rejected_ids = {item["optionId"] for item in draft["options"] if item["optionId"] != option_id}
    if set(rejected_reasons) != rejected_ids or any(not value.strip() for value in rejected_reasons.values()):
        raise PoseProofError("every unselected option requires one rejection reason")
    payload = {"assetId": draft["assetId"], "characterId": draft["characterId"], "poseId": draft["poseId"], "direction": draft["direction"], "canvas": draft["canvas"], "visualMoment": draft["visualMoment"], "selectedOption": selected, "selection": {"optionId": option_id, "reviewer": reviewer, "reason": reason, "rejectedOptions": [{"optionId": key, "reason": rejected_reasons[key]} for key in sorted(rejected_ids)], "selectedAt": selected_at}}
    if draft.get("historicalEvidence"):
        payload["historicalEvidence"] = draft["historicalEvidence"]
    return {"schemaVersion": 1, "poseProofId": stable_id("pose-proof", payload), **payload}


def write_card(card: dict[str, Any], path: str | Path) -> Path:
    validate_card(card)
    target = Path(path).resolve()
    return write_immutable_json(target.parent, target.name, card)


def save_png(image: Image.Image, path: str | Path) -> Path:
    target = Path(path).resolve()
    return PillowImageAdapter().publish_png(target.parent, target.name, image)


def parse_rejected(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise PoseProofError("rejected-reason must use OPTION=reason")
        key, reason = value.split("=", 1)
        if key in result:
            raise PoseProofError("duplicate rejected-reason option")
        result[key] = reason
    return result
