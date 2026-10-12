"""Synthetic-only offline exercise: no provider execution or real human approval."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image

from maliang_art.authoring import compile_design


CLI = Path(__file__).resolve().with_name("production.py")


def write_json(root, name, value):
    (root / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def production(root, *args):
    result = subprocess.run(
        [sys.executable, "-I", str(CLI), "--project", str(root), *args],
        cwd=root, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def event_path(event):
    return f"production/events/{event['eventId']}.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True,
                        help="new synthetic-only directory; existing directories are refused")
    args = parser.parse_args(argv)
    root = args.project.resolve()
    try:
        root.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error("choose a new project directory; existing paths are never overwritten")

    notice = "Synthetic offline fixture; not a real provider execution or production approval."
    write_json(root, "synthetic-demo.json", {
        "synthetic": True, "realProviderExecution": False, "realHumanApproval": False,
        "notice": notice,
    })
    contract = {
        "schemaVersion": 1, "familyId": "synthetic-demo",
        "camera": {"mode": "isometric", "profile": {
            "North": "UL", "South": "DR", "East": "UL+flipX", "West": "DR+flipX"},
            "mirrorAccepted": True},
        "silhouettes": ["bird"], "attachments": ["wing"],
        "drawingRules": [{"id": "style", "instruction": "Synthetic toy-like fixture only",
                          "method": "human", "required": True}],
        "paletteRoles": {"main": "#8899AA", "secondary": "#334455",
                         "outline": "#112233", "accent": "#EECC44"},
        "targets": {"sourceSize": [16, 16], "outputSize": [16, 16],
                    "anchorX": 8, "groundY": 14, "displaySizes": [16, 32],
                    "contextBoard": {"cellSize": [32, 32], "columns": 4}, "tolerance": 2},
        "statePolicy": {"allowedCoreTransforms": ["upright"], "allowedPartChanges": ["folded"]},
    }
    draft = {
        "schemaVersion": 1,
        "identity": {"species": "synthetic bird fixture", "features": ["fixture marker"],
                     "priority": ["fixture marker"], "forbiddenMirror": []},
        "topology": {"core": "synthetic torso", "parts": [{"id": "wing", "description": "folded"}],
                     "prohibited": ["extra wings"]},
        "silhouetteClass": "bird",
        "visualMoment": [{"view": "DR", "state": "Idle", "moment": "synthetic fixture",
                          "coreTransform": "upright", "partChanges": ["folded"]}],
        "paletteRoles": {}, "targets": {}, "references": [],
    }
    write_json(root, "contract.json", contract)
    write_json(root, "draft.json", draft)
    write_json(root, "design.json", compile_design(contract, draft).document)
    write_json(root, "parameters.json", {"size": "16x16", "output_format": "png"})
    attempt = "synthetic-001"
    prepared = production(root, "prepare", "--attempt", attempt,
                          "--contract", "contract.json", "--draft", "draft.json",
                          "--design", "design.json", "--parameters", "parameters.json",
                          "--provider", "offline-synthetic", "--model", "not-a-model")
    image = Image.new("RGBA", (16, 16))
    image.paste((255, 0, 0, 255), (3, 3, 12, 12))
    image.save(root / "synthetic-image.png")
    write_json(root, "synthetic-receipt.json", {
        "preparedEventId": prepared["eventId"], "invocation": prepared["invocation"],
        "outcome": "success",
        "artifactSha256": hashlib.sha256((root / "synthetic-image.png").read_bytes()).hexdigest(),
        "executionEvidence": notice,
    })
    candidate = production(root, "complete", "--attempt", attempt,
                           "--receipt", "synthetic-receipt.json", "--image", "synthetic-image.png")
    technical = production(root, "technical", "--attempt", attempt)
    write_json(root, "synthetic-human.json", {
        "actorType": "human", "reviewer": "synthetic-fixture-human",
        "statement": "Synthetic human decision fixture; not production approval; no person reviewed this image.",
        "candidate": {key: candidate[key] for key in ("eventId", "attemptId", "artifact")},
        "identityChecklist": candidate["identityChecklist"], "decision": "adopt",
        "checklist": {item["id"]: "pass" for item in candidate["requiredAcceptance"]
                      if item["method"] == "human"},
        "decidedAt": datetime.now(timezone.utc).isoformat(),
    })
    review = production(root, "review", "--attempt", attempt,
                        "--decision-file", "synthetic-human.json")
    result_args = [arg for result in technical for arg in ("--result", event_path(result))]
    adoption = production(root, "adopt", "--attempt", attempt, "--asset", "synthetic-demo",
                          "--review", event_path(review), *result_args)
    report = {
        "synthetic": True, "realProviderExecution": False, "realHumanApproval": False,
        "status": "synthetic-adopted", "notice": notice, "project": str(root),
        "artifacts": {"notice": "synthetic-demo.json", "design": "design.json",
                      "image": "synthetic-image.png", "receipt": "synthetic-receipt.json",
                      "humanFixture": "synthetic-human.json", "adoption": event_path(adoption),
                      "projection": "production/current/synthetic-demo.json"},
    }
    write_json(root, "demo-result.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
