"""Art direction intake: a project-owned question tree for broad art requests.

Pure functions only. MaLiang never calls a language model here: the host agent
asks the questions, may add suggestions on ``suggest`` dimensions, and records
only what the human actually chose.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Mapping

from .core import MaLiangError

_MODES = {"fixed", "suggest", "free"}
_SOURCES = {"catalog-option", "ai-suggested-option", "user-text", "ai-inferred-confirmed"}
_FIELD = re.compile(r"[A-Za-z][A-Za-z0-9]*(\.[A-Za-z][A-Za-z0-9]*)*(\[\])?")


class IntakeError(MaLiangError):
    """An art direction catalog or intake record is invalid."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntakeError(f"{name} must be non-empty text")
    return value


def _object(value: Any, name: str, required: set[str], optional: set[str] = frozenset()) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IntakeError(f"{name} must be an object")
    keys = set(value)
    if not required <= keys:
        raise IntakeError(f"{name} is missing {sorted(required - keys)}")
    if not keys <= required | optional:
        raise IntakeError(f"{name} has unsupported fields {sorted(keys - required - optional)}")
    return value


def _condition(value: Any, name: str, options_by_dim: Mapping[str, set[str]]) -> None:
    if not isinstance(value, Mapping) or not value:
        raise IntakeError(f"{name} must map dimension ids to option ids")
    for dim_id, option_ids in value.items():
        if dim_id not in options_by_dim:
            raise IntakeError(f"{name} references unknown dimension {dim_id}")
        if not isinstance(option_ids, list) or not option_ids:
            raise IntakeError(f"{name}.{dim_id} must list option ids")
        unknown = [o for o in option_ids if o not in options_by_dim[dim_id]]
        if unknown:
            raise IntakeError(f"{name}.{dim_id} references unknown options {unknown}")


def validate_catalog(value: Any) -> dict[str, Any]:
    catalog = _object(value, "catalog", {"schemaVersion", "catalogId", "dimensions"})
    if catalog["schemaVersion"] != 1 or isinstance(catalog["schemaVersion"], bool):
        raise IntakeError("catalog schemaVersion must be 1")
    _text(catalog["catalogId"], "catalogId")
    dims = catalog["dimensions"]
    if not isinstance(dims, list) or not dims:
        raise IntakeError("dimensions must list at least one dimension")
    options_by_dim: dict[str, set[str]] = {}
    for i, dim in enumerate(dims):
        dim = _object(dim, f"dimensions[{i}]", {"id", "prompt", "priority", "optionsMode", "options"}, {"when", "whenMode"})
        dim_id = _text(dim["id"], f"dimensions[{i}].id")
        if dim_id in options_by_dim:
            raise IntakeError(f"duplicate dimension id {dim_id}")
        if not isinstance(dim["options"], list):
            raise IntakeError(f"{dim_id}.options must be a list")
        options_by_dim[dim_id] = {o.get("id") for o in dim["options"] if isinstance(o, Mapping)}
    for dim in dims:
        dim_id = dim["id"]
        _text(dim["prompt"], f"{dim_id}.prompt")
        if isinstance(dim["priority"], bool) or not isinstance(dim["priority"], int) or dim["priority"] < 1:
            raise IntakeError(f"{dim_id}.priority must be a positive integer")
        mode = dim["optionsMode"]
        if mode not in _MODES:
            raise IntakeError(f"{dim_id}.optionsMode must be one of {sorted(_MODES)}")
        if mode == "free" and dim["options"]:
            raise IntakeError(f"{dim_id}: free dimensions take no options")
        if mode != "free" and len(dim["options"]) < 2:
            raise IntakeError(f"{dim_id}: a question needs at least two options")
        if "when" in dim:
            _condition(dim["when"], f"{dim_id}.when", options_by_dim)
        if dim.get("whenMode", "all") not in {"all", "any"}:
            raise IntakeError(f"{dim_id}.whenMode must be all or any")
        seen: set[str] = set()
        for j, opt in enumerate(dim["options"]):
            name = f"{dim_id}.options[{j}]"
            opt = _object(opt, name, {"id", "label", "references", "consequence", "risk"}, {"maps", "recommendWhen", "stop"})
            opt_id = _text(opt["id"], f"{name}.id")
            if opt_id in seen:
                raise IntakeError(f"{dim_id}: duplicate option id {opt_id}")
            seen.add(opt_id)
            for key in ("label", "consequence", "risk"):
                _text(opt[key], f"{name}.{key}")
            if not isinstance(opt["references"], list):
                raise IntakeError(f"{name}.references must be a list")
            for ref in opt["references"]:
                _text(ref, f"{name}.references[]")
            if "maps" in opt:
                maps = _object(opt["maps"], f"{name}.maps", {"target", "field", "value"})
                if maps["target"] not in {"styleGuide", "contract"}:
                    raise IntakeError(f"{name}.maps.target must be styleGuide or contract")
                if not isinstance(maps["field"], str) or not _FIELD.fullmatch(maps["field"]):
                    raise IntakeError(f"{name}.maps.field must be a dotted path, optionally ending in []")
            if "recommendWhen" in opt:
                _condition(opt["recommendWhen"], f"{name}.recommendWhen", options_by_dim)
            if "stop" in opt:
                _text(opt["stop"], f"{name}.stop")
    return copy.deepcopy(dict(catalog))


def _satisfied(condition: Mapping[str, list[str]] | None, chosen: Mapping[str, str | None], mode: str = "all") -> bool:
    if not condition:
        return True
    hits = [chosen.get(dim_id) in option_ids for dim_id, option_ids in condition.items()]
    return any(hits) if mode == "any" else all(hits)


def _visible(dim: Mapping[str, Any], chosen: Mapping[str, str | None]) -> bool:
    return _satisfied(dim.get("when"), chosen, dim.get("whenMode", "all"))


def gate_dimensions(catalog: Mapping[str, Any]) -> set[str]:
    """Dimensions whose answer stops the intake or decides which later dimensions appear."""
    gates = {d["id"] for d in catalog["dimensions"] if any("stop" in o for o in d["options"])}
    for dim in catalog["dimensions"]:
        gates.update(dim.get("when", {}))
    return gates


def _state(catalog: Mapping[str, Any], record: Any) -> tuple[dict[str, str | None], dict[str, Any] | None]:
    catalog = validate_catalog(catalog)
    gates = gate_dimensions(catalog)
    record = _object(record, "intake", {"schemaVersion", "intakeId", "catalogId", "request", "answers"})
    if record["schemaVersion"] != 1 or isinstance(record["schemaVersion"], bool):
        raise IntakeError("intake schemaVersion must be 1")
    _text(record["intakeId"], "intakeId")
    _text(record["request"], "request")
    if record["catalogId"] != catalog["catalogId"]:
        raise IntakeError("intake catalogId does not match the catalog")
    if not isinstance(record["answers"], list):
        raise IntakeError("answers must be a list")
    dims = {d["id"]: d for d in catalog["dimensions"]}
    chosen: dict[str, str | None] = {}
    answered: set[str] = set()
    stopped: dict[str, Any] | None = None
    for i, answer in enumerate(record["answers"]):
        name = f"answers[{i}]"
        answer = _object(answer, name, {"dimension", "source"},
                         {"option", "text", "confirmation", "followUpOf", "prompt", "presented"})
        if stopped:
            raise IntakeError(f"{name}: the intake already stopped at {stopped['dimension']}")
        dim_id = _text(answer["dimension"], f"{name}.dimension")
        if dim_id in answered:
            raise IntakeError(f"{name}: dimension {dim_id} is already answered")
        if "presented" not in answer or not isinstance(answer["presented"], list):
            raise IntakeError(f"{name}: presented must record the options actually shown")
        shown: dict[str, str] = {}
        for item in answer["presented"]:
            item = _object(item, f"{name}.presented[]", {"id", "label", "source"})
            _text(item["id"], f"{name}.presented[].id")
            _text(item["label"], f"{name}.presented[].label")
            if item["source"] not in {"catalog", "ai"}:
                raise IntakeError(f"{name}.presented[].source must be catalog or ai")
            shown[item["id"]] = item["source"]
        source = answer["source"]
        if source not in _SOURCES:
            raise IntakeError(f"{name}.source must be one of {sorted(_SOURCES)}")
        if ("option" in answer) == ("text" in answer):
            raise IntakeError(f"{name}: give exactly one of option or text")
        if "followUpOf" in answer:
            parent = _text(answer["followUpOf"], f"{name}.followUpOf")
            if dim_id in dims:
                raise IntakeError(f"{name}: a follow-up cannot reuse catalog dimension {dim_id}")
            if parent not in answered:
                raise IntakeError(f"{name}: follow-up parent {parent} is not answered yet")
            _text(answer.get("prompt"), f"{name}.prompt")
            if source != "user-text" or "text" not in answer:
                raise IntakeError(f"{name}: follow-ups record the user's own text")
            _text(answer["text"], f"{name}.text")
            answered.add(dim_id)
            continue
        dim = dims.get(dim_id)
        if dim is None:
            raise IntakeError(f"{name}: unknown dimension {dim_id}")
        if not _visible(dim, chosen):
            raise IntakeError(f"{name}: dimension {dim_id} is not available after the earlier answers")
        if dim["optionsMode"] == "fixed" and (source == "ai-suggested-option" or "ai" in shown.values()):
            raise IntakeError(f"{name}: dimension {dim_id} is fixed; AI-suggested options are not allowed")
        catalog_ids = {o["id"]: o for o in dim["options"]}
        if source == "ai-inferred-confirmed":
            _text(answer.get("confirmation"), f"{name}.confirmation")
        elif "confirmation" in answer:
            raise IntakeError(f"{name}: confirmation belongs only to ai-inferred-confirmed answers")
        if "text" in answer:
            _text(answer["text"], f"{name}.text")
            if source not in {"user-text", "ai-inferred-confirmed"}:
                raise IntakeError(f"{name}: text answers use user-text or ai-inferred-confirmed")
            if dim_id in gates:
                raise IntakeError(f"{name}: {dim_id} is a gate question; map the user's words to one option, "
                                  "confirm it with the user, and record it as ai-inferred-confirmed")
            chosen[dim_id] = None
        else:
            option_id = _text(answer["option"], f"{name}.option")
            if source == "user-text":
                raise IntakeError(f"{name}: user-text answers give text, not an option")
            if source == "ai-suggested-option":
                if dim["optionsMode"] != "suggest":
                    raise IntakeError(f"{name}: AI suggestions need a suggest dimension")
                if shown.get(option_id) != "ai" or option_id in catalog_ids:
                    raise IntakeError(f"{name}: {option_id} was not presented as an AI suggestion")
            else:
                if option_id not in catalog_ids:
                    raise IntakeError(f"{name}: {option_id} is not a catalog option of {dim_id}")
                if shown.get(option_id) != "catalog":
                    raise IntakeError(f"{name}: {option_id} was not presented to the user")
                if "stop" in catalog_ids[option_id]:
                    stopped = {"dimension": dim_id, "option": option_id, "reason": catalog_ids[option_id]["stop"]}
            chosen[dim_id] = option_id
        answered.add(dim_id)
    return chosen, stopped


def validate_intake(record: Any, catalog: Mapping[str, Any]) -> dict[str, Any]:
    _state(catalog, record)
    return copy.deepcopy(dict(record))


def _pending(catalog: Mapping[str, Any], chosen: Mapping[str, str | None]) -> list[Mapping[str, Any]]:
    order = {d["id"]: i for i, d in enumerate(catalog["dimensions"])}
    pending = [d for d in catalog["dimensions"] if d["id"] not in chosen and _visible(d, chosen)]
    return sorted(pending, key=lambda d: (d["priority"], order[d["id"]]))


def option_label(option: Mapping[str, Any], chosen: Mapping[str, str | None]) -> str:
    prefix = "[推荐] " if "recommendWhen" in option and _satisfied(option["recommendWhen"], chosen) else ""
    return f"{prefix}{option['label']}：{option['consequence']}｜风险：{option['risk']}"


def next_questions(catalog: Mapping[str, Any], record: Any, *, limit: int = 3) -> dict[str, Any]:
    """Next round of questions in AskQuestion form; free-text dimensions are listed separately."""
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise IntakeError("limit must be a positive integer")
    chosen, stopped = _state(catalog, record)
    result: dict[str, Any] = {"title": f"美术方向问询：{record['intakeId']}", "questions": [],
                              "freeText": [], "suggestable": [], "stopped": stopped}
    if stopped is None:
        pending = _pending(catalog, chosen)
        gates = gate_dimensions(validate_catalog(catalog))
        for dim in [d for d in pending if d["optionsMode"] != "free"][:limit]:
            result["questions"].append({
                "id": dim["id"], "prompt": dim["prompt"], "allow_multiple": False, "gate": dim["id"] in gates,
                "options": [{"id": o["id"], "label": option_label(o, chosen)} for o in dim["options"]],
            })
            if dim["optionsMode"] == "suggest":
                result["suggestable"].append(dim["id"])
        result["freeText"] = [{"id": d["id"], "prompt": d["prompt"]} for d in pending if d["optionsMode"] == "free"]
    result["done"] = stopped is not None or not (result["questions"] or result["freeText"])
    return result


def presented_options(catalog: Mapping[str, Any], dimension: str) -> list[dict[str, str]]:
    """The catalog options of ``dimension`` as recorded in ``presented``."""
    catalog = validate_catalog(catalog)
    dim = next((d for d in catalog["dimensions"] if d["id"] == dimension), None)
    if dim is None:
        raise IntakeError(f"unknown dimension {dimension}")
    return [{"id": o["id"], "label": o["label"], "source": "catalog"} for o in dim["options"]]


def _assign(target: dict[str, Any], field: str, value: Any) -> None:
    append = field.endswith("[]")
    parts = field.removesuffix("[]").split(".")
    node = target
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    if append:
        node.setdefault(parts[-1], []).append(copy.deepcopy(value))
    else:
        node[parts[-1]] = copy.deepcopy(value)


def draft_from_intake(catalog: Mapping[str, Any], record: Any) -> dict[str, Any]:
    """Map chosen catalog options into draft fields; nothing unanswered gets a default."""
    chosen, stopped = _state(catalog, record)
    dims = {d["id"]: d for d in catalog["dimensions"]}
    draft: dict[str, Any] = {"styleGuide": {}, "contractHints": {}, "needsTranslation": [], "open": [], "stopped": stopped}
    for answer in record["answers"]:
        if "text" in answer:
            draft["needsTranslation"].append({"dimension": answer["dimension"], "text": answer["text"], "source": answer["source"]})
            continue
        if answer["source"] == "ai-suggested-option":
            label = next(p["label"] for p in answer["presented"] if p["id"] == answer["option"])
            draft["needsTranslation"].append({"dimension": answer["dimension"], "label": label, "source": answer["source"]})
            continue
        option = next(o for o in dims[answer["dimension"]]["options"] if o["id"] == answer["option"])
        if "maps" in option:
            target = draft["styleGuide"] if option["maps"]["target"] == "styleGuide" else draft["contractHints"]
            _assign(target, option["maps"]["field"], option["maps"]["value"])
    if stopped is None:
        draft["open"] = [d["id"] for d in _pending(catalog, chosen)]
    return draft
