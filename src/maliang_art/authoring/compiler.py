"""Deterministic visual execution briefs with optional debug-layout artifacts."""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from PIL import Image

from maliang_art.core import canonical_bytes, stable_id
from .rendering import geometry, render_blockout
from .validation import DesignError, effective_values, validate_design


@dataclass(frozen=True)
class ConstructionPacket:
    document: dict[str, Any]
    guides: dict[str, bytes]

    @property
    def json_bytes(self) -> bytes:
        return canonical_bytes(self.document)


def audit_alpha_bounds(image_bytes: bytes, output_size: list[int]) -> dict[str, Any]:
    """Measure dimensions, nonempty alpha and edge clearance, not art quality."""
    with Image.open(BytesIO(image_bytes)) as source:
        image = source.convert("RGBA")
        bbox = image.getchannel("A").getbbox()
        passed = (list(image.size) == output_size and bbox is not None
                  and bbox[0] > 0 and bbox[1] > 0
                  and bbox[2] < image.width and bbox[3] < image.height)
        return {"status": "pass" if passed else "fail", "size": list(image.size), "alphaBounds": list(bbox) if bbox else None}


def compile_design(contract: dict, draft: dict, *, debug_geometry: bool = False) -> ConstructionPacket:
    diagnostics = validate_design(contract, draft, debug_geometry=debug_geometry)
    if diagnostics:
        raise DesignError(diagnostics)
    contract, draft = copy.deepcopy(contract), copy.deepcopy(draft)
    targets, palette = effective_values(contract, draft)
    guides, options, debug_artifacts = {}, [], []
    image_inputs = copy.deepcopy(draft["references"])
    native_views = sorted({t["view"] for t in draft["visualMoment"]})
    if debug_geometry:
        for variant in contract["variants"]:
            parameters = geometry(variant, draft["silhouetteClass"], targets, draft["topology"])
            option = {"id": variant["id"], "parameters": parameters, "familyParameters": variant,
                      "kind": "debug-layout", "status": "unapproved", "usage": "not-generation-input", "guides": []}
            for view in native_views:
                path = f"guides/{variant['id']}-{view}.png"
                png = render_blockout(parameters, targets["sourceSize"], view)
                digest = hashlib.sha256(png).hexdigest()
                guides[path] = png
                debug_artifacts.append({"path": path, "sha256": digest,
                                        "kind": "debug-layout", "status": "unapproved", "usage": "not-generation-input",
                                        "screenDirectionMarker": view, "option": variant["id"]})
                option["guides"].append(path)
            options.append(option)
    topology = copy.deepcopy(draft["topology"])
    topology["parts"] = [{key: value for key, value in part.items() if key not in {"anchor", "size"}}
                         for part in topology["parts"]]
    acceptance = []
    for rule in contract["drawingRules"]:
        method = rule["method"]
        acceptance.append({"id": rule["id"], "source": f"contract.drawingRules.{rule['id']}",
                           "instruction": rule["instruction"], "method": method, "required": rule["required"],
                           "status": "pending", "failure": "Candidate violates: " + rule["instruction"],
                           "predicate": ("output size matches; nonempty alpha; no opaque pixel touches canvas edge" if method == "alpha-bounds" else "Human must judge this instruction on the exact candidate hash.")})
    acceptance.extend([
        {"id": "technical-targets", "source": "draft.targets+contract.targets", "method": "alpha-bounds", "required": True, "status": "pending", "instruction": "Output dimensions match; alpha is nonempty; no alpha touches canvas edge.", "parameters": {"outputSize": targets["outputSize"]}, "failure": "Wrong output dimensions, empty alpha, or alpha touches canvas edge."},
        {"id": "identity", "source": "draft.identity", "method": "human", "required": True, "status": "pending", "instruction": draft["identity"]["features"], "failure": "Priority identity feature is not recognizable at target display size."},
        {"id": "pose", "source": "draft.visualMoment", "method": "human", "required": True, "status": "pending", "instruction": "Compare explicit moments, core identity and permitted pose projection, not identical whole-image bounding boxes.", "failure": "Pose changes identity or fails to depict the declared moment."},
        {"id": "palette", "source": "draft.paletteRoles+contract.paletteRoles", "method": "human", "required": True, "status": "pending", "instruction": "Review role colors and light/shadow use; no automatic style proof.", "failure": "Colors do not fulfill the declared palette roles."},
    ])
    cells = []
    cell_width, cell_height = targets["contextBoard"]["cellSize"]
    columns = targets["contextBoard"]["columns"]
    states = list(dict.fromkeys(t["state"] for t in draft["visualMoment"]))
    for state in states:
        for direction in ("North", "South", "East", "West"):
            projection = contract["camera"]["profile"][direction]
            index = len(cells)
            cells.append({"state": state, "direction": direction, "projection": projection,
                          "position": [(index % columns) * cell_width, (index // columns) * cell_height],
                          "size": [cell_width, cell_height], "candidate": None,
                          "status": "pending" if (projection.split("+")[0], state) in {(t['view'], t['state']) for t in draft['visualMoment']} else "not-requested"})
    instructions = {
        "priority": ["family camera/topology prohibitions", "identity invariants", "declared moment", "reference role boundaries", "style suggestions"],
        "familyRules": contract["drawingRules"], "identity": draft["identity"], "topology": topology,
        "camera": contract["camera"], "tasks": draft["visualMoment"], "statePolicy": contract["statePolicy"],
        "silhouetteClass": draft["silhouetteClass"], "paletteRoles": palette, "targets": targets, "imageInputs": image_inputs,
    }
    prompt = ("Visual execution brief, not a compliance guarantee. Explore the declared character and visual moment. "
              "Optional debug-layout artifacts are unapproved, not-generation-input; they prove neither species nor DR/UL projection. "
              "Preserve core/attachment identity; pose projection may vary. Do not infer an attack from a state label. "
              "Use images only for their listed roles and borrowing permissions; no implicit cross-character identity transfer. "
              "Declared palette colors are role targets for human review; do not claim automatic aesthetic compliance. "
              "No result images or approvals exist in this packet. No image backend is invoked; submission support must be verified separately.\n"
              + canonical_bytes(instructions).decode("utf-8"))
    document = {
        "schemaVersion": 1, "familyId": contract["familyId"],
        "designId": stable_id("design", {"contract": contract, "draft": draft}),
        "kind": "visual-execution-brief", "options": options, "debugArtifacts": debug_artifacts,
        "tasks": draft["visualMoment"], "camera": contract["camera"],
        "identity": draft["identity"], "topology": topology, "silhouetteClass": draft["silhouetteClass"],
        "identityInvariant": {"shape": topology["core"], "features": draft["identity"]["features"], "attachments": topology["parts"], "poseProjection": "variable", "permittedVariation": contract["statePolicy"]},
        "references": draft["references"], "imageInputs": image_inputs, "prompt": prompt,
        "palettePlan": {"roles": palette, "method": "human", "status": "pending", "lightShadow": "Review role readability in color and grayscale; no inferred lighting colors."},
        "targets": targets, "acceptance": acceptance,
        "contextBoard": {"status": "layout-only", "cells": cells, "displaySizes": targets["displaySizes"]},
        "comparisonPlan": {"nativeViews": native_views, "states": states, "method": "human", "status": "pending", "checks": ["shared core and attachment identity", "declared moment and permitted variation", "color/grayscale at display sizes", "mirror handedness accepted by project"], "coreMeasurement": "unsupported: requires candidate-bound confirmed core masks"},
        "artDecision": {"status": "pending", "candidateSha256": None, "reviewer": None, "decision": None, "requiredEvidence": ["exact candidate hash", "identity checklist", "display previews", "actual human decision"]},
        "capabilities": {"visualGeneration": "external-backend-unverified", "imageReferenceInput": "submission-unverified",
                         "debugRendering": {"supportedShapes": ["capsule", "ball"], "requested": debug_geometry, "usage": "not-generation-input"},
                         "automaticChecks": ["alpha-bounds"], "artApproval": "human-required"},
        "execution": {"status": "not-executed", "backend": None, "parameters": None, "guideSubmission": "not-generation-input", "referenceVerification": "hash declarations only; no reference files read"},
    }
    return ConstructionPacket(document, guides)
