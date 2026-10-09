"""Missing decisions and explicit first-slice capability boundaries."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .rendering import geometry
from .schema import schema_document, schema_errors

PROFILE = {"North": "UL", "South": "DR", "East": "UL+flipX", "West": "DR+flipX"}
REVIEW_METHODS = {"human", "alpha-bounds"}
ALPHA_INSTRUCTION = "Output dimensions match; alpha is nonempty; no alpha touches canvas edge."


@dataclass(frozen=True)
class Diagnostic:
    path: str
    code: str
    message: str


class DesignError(ValueError):
    def __init__(self, diagnostics: list[Diagnostic]):
        self.diagnostics = diagnostics
        super().__init__("; ".join(f"{d.path}: {d.message}" for d in diagnostics))


def effective_values(contract: dict, draft: dict) -> tuple[dict, dict]:
    return ({**contract["targets"], **draft["targets"]},
            {**contract["paletteRoles"], **draft["paletteRoles"]})


def validate_design(contract: Any, draft: Any, *, debug_geometry: bool = False) -> list[Diagnostic]:
    result = []
    for name, value, path in [("art-family-contract", contract, "contract"), ("sprite-slice-draft", draft, "draft")]:
        result.extend(Diagnostic(*error) for error in schema_errors(value, schema_document(name), path))
    if result:
        return result

    def report(path, message, code="unsupported"):
        result.append(Diagnostic(path, code, message))

    if contract["camera"]["mode"] != "isometric":
        report("contract.camera.mode", "Only isometric native DR/UL is supported; flat2d is unsupported.")
    if contract["camera"]["profile"] != PROFILE:
        report("contract.camera.profile", "Only the explicit North=UL, South=DR, East=UL+flipX, West=DR+flipX profile is supported.")
    if not contract["camera"]["mirrorAccepted"]:
        report("contract.camera.mirrorAccepted", "Project must explicitly accept mirror-derived handedness changes.", "missing-decision")
    if draft["identity"]["forbiddenMirror"]:
        report("draft.identity.forbiddenMirror", "Identity forbids mirroring but the profile derives two views by flipX.", "conflict")
    if draft["silhouetteClass"] not in contract["silhouettes"]:
        report("draft.silhouetteClass", "Choose a visual shape intention permitted by the family.")
    if any(feature not in draft["identity"]["features"] for feature in draft["identity"]["priority"]):
        report("draft.identity.priority", "Priority must name declared identity features.", "conflict")
    seen_parts = set()
    for i, part in enumerate(draft["topology"]["parts"]):
        if part["id"] not in contract["attachments"]:
            report(f"draft.topology.parts[{i}].id", "Attachment is not permitted by this family.")
        if part["id"] in seen_parts or part["id"] in draft["topology"]["prohibited"]:
            report(f"draft.topology.parts[{i}].id", "Duplicate or explicitly prohibited attachment.", "conflict")
        seen_parts.add(part["id"])
    seen_tasks = set()
    for i, task in enumerate(draft["visualMoment"]):
        base = f"draft.visualMoment[{i}]"
        if task["view"] not in {"DR", "UL"}:
            report(base + ".view", "Only native DR/UL tasks are supported; flipped views are derived.")
        if task["coreTransform"] not in contract["statePolicy"]["allowedCoreTransforms"]:
            report(base + ".coreTransform", "Core pose transform is not permitted by the family.", "conflict")
        if any(x not in contract["statePolicy"]["allowedPartChanges"] for x in task["partChanges"]):
            report(base + ".partChanges", "Part variation is not permitted by the family.", "conflict")
        key = (task["view"], task["state"])
        if key in seen_tasks:
            report(base, "Only one representative moment per native view/state is supported.")
        seen_tasks.add(key)
    for collection in ["variants", "drawingRules"]:
        ids = [item["id"] for item in contract.get(collection, [])]
        if len(set(ids)) != len(ids):
            report(f"contract.{collection}", "IDs must be unique.", "conflict")
    for i, rule in enumerate(contract["drawingRules"]):
        if rule["id"] in {"technical-targets", "identity", "pose", "palette"}:
            report(f"contract.drawingRules[{i}].id", "Rule ID is reserved for a built-in acceptance case; choose a distinct family rule ID.", "conflict")
        if rule["method"] not in REVIEW_METHODS:
            report(f"contract.drawingRules[{i}].method", "Supported review methods are human and alpha-bounds; unknown automation cannot be promised.")
        elif rule["method"] == "alpha-bounds" and rule["instruction"] != ALPHA_INSTRUCTION:
            report(f"contract.drawingRules[{i}].instruction", f"alpha-bounds proves only: {ALPHA_INSTRUCTION} Route other instructions to human review.")
    for i, ref in enumerate(draft["references"]):
        if any(segment in {"", ".", ".."} for segment in ref["path"].split("/")):
            report(f"draft.references[{i}].path", "Use a portable relative path without traversal.", "invalid")
        if set(ref["borrow"]) & set(ref["forbid"]):
            report(f"draft.references[{i}]", "The same content cannot be both borrowed and forbidden.", "conflict")
        if "identity" in ref["roles"] and "identity" in ref["forbid"]:
            report(f"draft.references[{i}].roles", "Identity role conflicts with forbidden identity borrowing.", "conflict")
    targets, _ = effective_values(contract, draft)
    sw, sh = targets["sourceSize"]
    if targets["anchorX"] >= sw or targets["groundY"] >= sh:
        report("draft.targets", "Inherited/declared anchor and ground must be inside the source canvas.", "conflict")
    if debug_geometry:
        if draft["silhouetteClass"] not in {"capsule", "ball"}:
            report("draft.silhouetteClass", "Debug-layout renderer supports only capsule/ball; visual exploration does not require it.")
        if not contract.get("variants"):
            report("contract.variants", "Explicit debug-layout rendering requires numeric variants.", "missing-decision")
        for i, part in enumerate(draft["topology"]["parts"]):
            for field in ("anchor", "size"):
                if field not in part:
                    report(f"draft.topology.parts[{i}].{field}", "Explicit debug-layout rendering requires numeric part geometry.", "missing-decision")
    if debug_geometry and not result:
        for i, variant in enumerate(contract["variants"]):
            params = geometry(variant, draft["silhouetteClass"], targets, draft["topology"])
            for bounds in [params["coreBounds"], *(p["bounds"] for p in params["parts"])]:
                if bounds[0] < 0 or bounds[1] < 0 or bounds[2] > sw - 1 or bounds[3] > sh - 1 or round(bounds[2]) <= round(bounds[0]) or round(bounds[3]) <= round(bounds[1]):
                    report(f"contract.variants[{i}]", "Core/attachment blockout exceeds the canvas or rounds to zero area; revise geometry, anchor or source size.", "conflict")
                    break
    return result
