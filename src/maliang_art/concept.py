"""Concept-art records and the identity bridge into in-game capsule assets.

Records only; no image generation and no image I/O. Approval is read from
records written by a human reviewer and is never produced here.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from .records import RecordValidationError, validate_artifact

_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
_APPROVAL_STATES = {"pending", "approved", "rejected"}
_REVIEWER_SOURCES = {"git-config", "os-user", "manual"}
_MARKER_CATEGORIES = {"species-silhouette", "costume-color", "weapon", "accessory", "mark", "transformation"}


def _fields(value: Any, name: str, required: set[str], optional: set[str] = frozenset()) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RecordValidationError(f"{name} must be an object")
    keys = set(value)
    if not required <= keys or not keys <= required | optional:
        raise RecordValidationError(f"{name} must contain {sorted(required)}" + (f" and optionally {sorted(optional)}" if optional else ""))
    return dict(value)


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RecordValidationError(f"{name} must be non-empty text")
    return value


def _texts(value: Any, name: str, *, minimum: int = 0, unique: bool = False) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum:
        raise RecordValidationError(f"{name} must be a list with at least {minimum} items")
    items = [_text(item, f"{name}[]") for item in value]
    if unique and len(set(items)) != len(items):
        raise RecordValidationError(f"{name} must not repeat values")
    return items


def _version(value: Mapping[str, Any]) -> None:
    if value.get("schemaVersion") != 1 or isinstance(value.get("schemaVersion"), bool):
        raise RecordValidationError("schemaVersion must be 1")


def _approval(value: Any, name: str) -> dict[str, Any]:
    approval = _fields(value, name, {"status"}, {"reviewer", "reviewerSource", "reviewedAt", "note"})
    if approval["status"] not in _APPROVAL_STATES:
        raise RecordValidationError(f"{name}.status must be one of {sorted(_APPROVAL_STATES)}")
    if "reviewerSource" in approval and approval["reviewerSource"] not in _REVIEWER_SOURCES:
        raise RecordValidationError(f"{name}.reviewerSource must be one of {sorted(_REVIEWER_SOURCES)}")
    if approval["status"] == "pending":
        if {"reviewer", "reviewerSource", "reviewedAt"} & set(approval):
            raise RecordValidationError(f"{name}: pending approval cannot name a reviewer")
    else:
        _text(approval.get("reviewer"), f"{name}.reviewer")
        _text(approval.get("reviewedAt"), f"{name}.reviewedAt")
    if "note" in approval and not isinstance(approval["note"], str):
        raise RecordValidationError(f"{name}.note must be text")
    return approval


def validate_style_guide(value: Any) -> dict[str, Any]:
    record = _fields(value, "concept-style-guide", {"schemaVersion", "styleId", "track", "framing", "references", "rules"})
    _version(record)
    _text(record["styleId"], "styleId")
    if record["track"] not in {"concept", "promo"}:
        raise RecordValidationError("track must be concept or promo")
    framing = _fields(record["framing"], "framing", {"subject", "body", "background"})
    for key, item in framing.items():
        _text(item, f"framing.{key}")
    if not isinstance(record["references"], list):
        raise RecordValidationError("references must be a list")
    for i, ref in enumerate(record["references"]):
        ref = _fields(ref, f"references[{i}]", {"title", "borrow", "forbid"})
        _text(ref["title"], f"references[{i}].title")
        _texts(ref["borrow"], f"references[{i}].borrow", minimum=1)
        _texts(ref["forbid"], f"references[{i}].forbid")
    if not isinstance(record["rules"], list) or not record["rules"]:
        raise RecordValidationError("rules must list at least one rule")
    for i, rule in enumerate(record["rules"]):
        rule = _fields(rule, f"rules[{i}]", {"id", "instruction", "method", "required"})
        _text(rule["id"], f"rules[{i}].id")
        _text(rule["instruction"], f"rules[{i}].instruction")
        if rule["method"] not in {"deterministic", "human"}:
            raise RecordValidationError(f"rules[{i}].method must be deterministic or human")
        if not isinstance(rule["required"], bool):
            raise RecordValidationError(f"rules[{i}].required must be boolean")
    return dict(value)


def _size(value: Any, name: str) -> list[int] | None:
    if value is None:
        return None
    if (not isinstance(value, list) or len(value) != 2
            or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in value)):
        raise RecordValidationError(f"{name} must be [width, height] positive integers or null")
    return value


def validate_concept(value: Any, *, root: Any = None, verify: bool = False) -> dict[str, Any]:
    record = _fields(value, "character-concept", {"schemaVersion", "conceptId", "characterId", "styleId", "form", "species", "image", "imageSize", "approval"})
    _version(record)
    for key in ("conceptId", "characterId", "styleId", "form", "species"):
        _text(record[key], key)
    if record["image"] is not None:
        validate_artifact(record["image"], root=root, verify=verify)
    size = _size(record["imageSize"], "imageSize")
    if (record["image"] is None) != (size is None):
        raise RecordValidationError("image and imageSize must both be set or both be null")
    approval = _approval(record["approval"], "approval")
    if approval["status"] == "approved" and record["image"] is None:
        raise RecordValidationError("an approved concept must bind its image")
    return dict(value)


def validate_markers(value: Any) -> dict[str, Any]:
    record = _fields(value, "identity-markers", {"schemaVersion", "markersId", "characterId", "status", "conceptIds", "markers", "palette", "tolerance"})
    _version(record)
    _text(record["markersId"], "markersId")
    _text(record["characterId"], "characterId")
    if record["status"] not in {"draft", "frozen"}:
        raise RecordValidationError("status must be draft or frozen")
    _texts(record["conceptIds"], "conceptIds", minimum=1, unique=True)
    if not isinstance(record["markers"], list) or not record["markers"]:
        raise RecordValidationError("markers must list at least one marker")
    ids = []
    for i, marker in enumerate(record["markers"]):
        marker = _fields(marker, f"markers[{i}]", {"id", "description", "category", "required", "capsuleTranslation"}, {"forms"})
        ids.append(_text(marker["id"], f"markers[{i}].id"))
        if "forms" in marker:
            _texts(marker["forms"], f"markers[{i}].forms", minimum=1, unique=True)
        _text(marker["description"], f"markers[{i}].description")
        _text(marker["capsuleTranslation"], f"markers[{i}].capsuleTranslation")
        if marker["category"] not in _MARKER_CATEGORIES:
            raise RecordValidationError(f"markers[{i}].category must be one of {sorted(_MARKER_CATEGORIES)}")
        if not isinstance(marker["required"], bool):
            raise RecordValidationError(f"markers[{i}].required must be boolean")
    if len(set(ids)) != len(ids):
        raise RecordValidationError("marker ids must be unique")
    if not isinstance(record["palette"], list) or not record["palette"]:
        raise RecordValidationError("palette must list at least one color")
    for i, color in enumerate(record["palette"]):
        color = _fields(color, f"palette[{i}]", {"role", "hex"})
        _text(color["role"], f"palette[{i}].role")
        if not isinstance(color["hex"], str) or not _HEX.fullmatch(color["hex"]):
            raise RecordValidationError(f"palette[{i}].hex must be #RRGGBB")
    tolerance = record["tolerance"]
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not 0 <= tolerance <= 442:
        raise RecordValidationError("tolerance must be a number from 0 to 442")
    return dict(value)


def validate_usage(value: Any) -> dict[str, Any]:
    record = _fields(value, "derived-usage", {"schemaVersion", "usageId", "conceptId", "kind", "purpose", "approval"}, {"crop"})
    _version(record)
    for key in ("usageId", "conceptId", "purpose"):
        _text(record[key], key)
    if record["kind"] not in {"portrait-bust", "promo"}:
        raise RecordValidationError("kind must be portrait-bust or promo")
    if record["kind"] == "portrait-bust" and "crop" not in record:
        raise RecordValidationError("portrait-bust requires crop")
    if "crop" in record:
        crop = _fields(record["crop"], "crop", {"x", "y", "width", "height"})
        for key, n in crop.items():
            low = 1 if key in {"width", "height"} else 0
            if isinstance(n, bool) or not isinstance(n, int) or n < low:
                raise RecordValidationError(f"crop.{key} must be an integer >= {low}")
    _approval(record["approval"], "approval")
    return dict(value)


def chain_findings(records: Iterable[Mapping[str, Any]]) -> list[str]:
    """Cross-record findings for already validated concept-chain records."""
    concepts: dict[str, Mapping[str, Any]] = {}
    others: list[Mapping[str, Any]] = []
    for record in records:
        if "conceptId" in record and "form" in record:
            concepts[record["conceptId"]] = record
        else:
            others.append(record)
    findings: list[str] = []
    for record in others:
        if "markersId" in record:
            for concept_id in record["conceptIds"]:
                concept = concepts.get(concept_id)
                if concept is None:
                    findings.append(f"{record['markersId']}: unknown concept {concept_id}")
                elif record["status"] == "frozen" and concept["approval"]["status"] != "approved":
                    findings.append(f"{record['markersId']}: frozen markers cite concept {concept_id} that is not approved")
        elif "usageId" in record:
            concept = concepts.get(record["conceptId"])
            if concept is None:
                findings.append(f"{record['usageId']}: unknown concept {record['conceptId']}")
                continue
            if concept["approval"]["status"] != "approved" or concept["imageSize"] is None:
                findings.append(f"{record['usageId']}: concept {record['conceptId']} has no approved image")
                continue
            crop = record.get("crop")
            width, height = concept["imageSize"]
            if crop and (crop["x"] + crop["width"] > width or crop["y"] + crop["height"] > height):
                findings.append(f"{record['usageId']}: crop is outside the {width}x{height} concept image")
    return findings


def markers_to_identity(markers: Mapping[str, Any], *, species: str) -> dict[str, Any]:
    """Build the sprite-slice draft identity block from capsule translations."""
    features = [m["capsuleTranslation"] for m in markers["markers"]]
    priority = [m["capsuleTranslation"] for m in markers["markers"] if m["required"]]
    return {"species": species, "features": features, "priority": priority, "forbiddenMirror": []}


def draft_identity_findings(draft: Mapping[str, Any], markers: Mapping[str, Any]) -> list[str]:
    features = set(draft.get("identity", {}).get("features", []))
    return [f"required marker {m['id']} is missing from draft identity: {m['capsuleTranslation']}"
            for m in markers["markers"] if m["required"] and m["capsuleTranslation"] not in features]


def _rgb(hex_value: str) -> tuple[int, int, int]:
    return tuple(int(hex_value[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def palette_findings(color_counts: Mapping[tuple[int, int, int], int], markers: Mapping[str, Any], *, coverage: float = 0.8) -> list[str]:
    """Report dominant colors (covering ``coverage`` of opaque pixels) outside the marker palette."""
    palette = [_rgb(c["hex"]) for c in markers["palette"]]
    limit = markers["tolerance"]
    total = sum(color_counts.values())
    if total <= 0:
        return ["no opaque pixels to compare with the marker palette"]
    findings: list[str] = []
    seen = 0
    for color, count in sorted(color_counts.items(), key=lambda item: (-item[1], item[0])):
        if seen >= coverage * total:
            break
        seen += count
        distance = min(sum((a - b) ** 2 for a, b in zip(color, p)) ** 0.5 for p in palette)
        if distance > limit:
            findings.append("dominant color #{:02X}{:02X}{:02X} is {:.0f} from the nearest marker palette color (tolerance {})"
                            .format(*color, distance, limit))
    return findings


def _form_markers(markers: Mapping[str, Any], form: str) -> list[Mapping[str, Any]]:
    return [m for m in markers["markers"] if form in m.get("forms", [form])]


_ALL_OK = {"id": "all-ok", "label": "全部满足"}
_OTHER = {"id": "other", "label": "有其他问题（请写在补充里）"}
_CONCLUSIONS = [{"id": "approved", "label": "通过"}, {"id": "rejected", "label": "不通过"},
                {"id": "revise", "label": "需修改（不满足项会写入备注）"}]


def review_questions(style: Mapping[str, Any], concept: Mapping[str, Any], markers: Mapping[str, Any]) -> dict[str, Any]:
    """AskQuestion-shaped review form; answers map back through decision_from_answers."""
    rules = [{"id": r["id"], "label": f"{r['id']}：{r['instruction']}"} for r in style["rules"] if r["method"] == "human"]
    marks = [{"id": m["id"], "label": f"{m['id']}{'（必需）' if m['required'] else ''}：{m['description']}"}
             for m in _form_markers(markers, concept["form"])]
    image = concept["image"]["path"] if concept["image"] else "尚未绑定图片"
    return {
        "title": f"原画确认：{concept['conceptId']}（{image}）",
        "questions": [
            {"id": "style", "prompt": f"风格检查（{style['styleId']}）：哪些不满足？", "allow_multiple": True,
             "options": [*rules, dict(_ALL_OK), dict(_OTHER)]},
            {"id": "markers", "prompt": f"认人特征（形态 {concept['form']}）：哪些不满足？", "allow_multiple": True,
             "options": [*marks, dict(_ALL_OK), dict(_OTHER)]},
            {"id": "decision", "prompt": "结论", "allow_multiple": False, "options": [dict(c) for c in _CONCLUSIONS]},
        ],
    }


def decision_from_answers(answers: Mapping[str, Any],
                          form: Mapping[str, Any] | None = None) -> tuple[str, str | None]:
    """Map review_questions answers, plus optional free text under "other", to a decision and note."""
    other = answers.get("other") or {}
    if not isinstance(other, Mapping):
        raise RecordValidationError("other must map question ids to free text")
    texts = {key: _text(value, f"other.{key}").strip() for key, value in other.items()}
    if form is not None:
        known = {q["id"]: {o["id"] for o in q["options"]} for q in form["questions"]}
        for key in ("style", "markers", "decision"):
            unknown = [x for x in answers.get(key) or [] if x not in known.get(key, set())]
            if unknown:
                raise RecordValidationError(f"{key} answer has options not in the form: {', '.join(unknown)}")
    conclusion = list(answers.get("decision") or [])
    if len(conclusion) != 1 or conclusion[0] not in {c["id"] for c in _CONCLUSIONS}:
        raise RecordValidationError("decision answer must be exactly one of approved, rejected, revise")
    failed = [x for key in ("style", "markers") for x in answers.get(key) or [] if x not in {_ALL_OK["id"], _OTHER["id"]}]
    issues = [texts[key] for key in ("style", "markers") if texts.get(key)]
    flagged_other = any(_OTHER["id"] in (answers.get(key) or []) for key in ("style", "markers"))
    if conclusion[0] == "approved":
        if failed or issues or flagged_other:
            raise RecordValidationError("cannot approve while checks are marked unmet or other issues are written")
        return "approved", texts.get("decision") or None
    parts = [", ".join(failed)] if failed else []
    if issues:
        parts.append("other: " + "; ".join(issues))
    if texts.get("decision"):
        parts.append(texts["decision"])
    prefix = "needs revision" if conclusion[0] == "revise" else "rejected"
    return "rejected", (f"{prefix}: " + "; ".join(parts)) if parts else (prefix if conclusion[0] == "revise" else None)


def review_sheet(style: Mapping[str, Any], concept: Mapping[str, Any], markers: Mapping[str, Any]) -> str:
    """Markdown sheet listing exactly what a human must confirm for one concept."""
    if concept["image"] is None:
        image_line = "- Image: no image bound yet; generate it only after explicit authorization."
    else:
        width, height = concept["imageSize"]
        image_line = f"- Image: `{concept['image']['path']}` ({width}x{height}, sha256 `{concept['image']['sha256'][:12]}`)"
    lines = [
        f"# Concept review: {concept['conceptId']}",
        "",
        f"- Character: {concept['characterId']} / form: {concept['form']} / species: {concept['species']}",
        image_line,
        f"- Current status: {concept['approval']['status']}",
        "",
        f"## Style checks ({style['styleId']})",
        "",
    ]
    lines += [f"- [ ] {rule['id']}: {rule['instruction']}" for rule in style["rules"] if rule["method"] == "human"]
    lines += ["- [ ] Other issues:", "", f"## Identity markers ({markers['markersId']})", ""]
    lines += [f"- [ ] {m['id']}{' (required)' if m['required'] else ''}: {m['description']}"
              for m in _form_markers(markers, concept["form"])]
    lines += ["- [ ] Other issues:"]
    lines += [
        "",
        "## Decision",
        "",
        "Reply with one of: approved / rejected / revise (list what to change).",
        "Nothing is recorded until you reply.",
        "",
    ]
    return "\n".join(lines)


def apply_decision(record: Mapping[str, Any], decision: str, *, reviewer: str, source: str, at: str,
                   note: str | None = None, image: Mapping[str, str] | None = None,
                   image_size: list[int] | None = None) -> dict[str, Any]:
    """Return a copy of a concept or derived-usage record carrying a human decision."""
    if decision not in {"approved", "rejected"}:
        raise RecordValidationError("decision must be approved or rejected")
    if source not in _REVIEWER_SOURCES:
        raise RecordValidationError(f"reviewer source must be one of {sorted(_REVIEWER_SOURCES)}")
    result = dict(record)
    if image is not None:
        if "form" not in result:
            raise RecordValidationError("only a character concept binds an image")
        result["image"] = dict(image)
        result["imageSize"] = list(image_size) if image_size is not None else None
    approval = {"status": decision, "reviewer": _text(reviewer, "reviewer"), "reviewerSource": source,
                "reviewedAt": _text(at, "reviewedAt")}
    if note:
        approval["note"] = note
    result["approval"] = approval
    return validate_concept(result) if "form" in result else validate_usage(result)
