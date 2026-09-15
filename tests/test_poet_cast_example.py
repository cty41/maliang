from __future__ import annotations

import hashlib
import json
from pathlib import Path

from maliang_art.core import contained_path
from maliang_art.pose import select_option, validate_card, validate_draft

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "poet-cast"
CARD_PATH = EXAMPLE / "store" / "Tools" / "artworks" / "poet_five_red_chow" / "pose-proofs" / "poet_cast_dr_sheathed_focus_v1.json"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_poet_cast_manifest_binds_six_licensed_source_files():
    manifest = _json(EXAMPLE / "assets.json")
    assert manifest["schemaVersion"] == 1
    assert manifest["sourceCommit"] == "7898f45b9d7978f1eaae14732df338f440a6a5fa"
    assert manifest["rightsHolder"] == "cty41"
    assert manifest["license"] == "CC-BY-4.0"
    assert len(manifest["assets"]) == 6
    assert len({item["path"] for item in manifest["assets"]}) == 6

    for item in manifest["assets"]:
        path = contained_path(EXAMPLE, item["path"])
        assert path.is_file(), item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        assert item["sourcePath"]
        assert item["role"]

    evidence = _json(EXAMPLE / "license-evidence.json")
    assert evidence["toLicense"] == "CC-BY-4.0"
    assert evidence["reviewer"] == "cty41"
    licensed_hashes = {item["sha256"] for item in evidence["artifacts"]}
    manifest_by_role = {item["role"]: item for item in manifest["assets"]}
    assert licensed_hashes == {
        manifest_by_role["pose-draft"]["sha256"],
        manifest_by_role["selected-action-card"]["sha256"],
    }

    png_binding = manifest["pngLicenseEvidence"]
    png_evidence_path = contained_path(EXAMPLE, png_binding["path"])
    assert hashlib.sha256(png_evidence_path.read_bytes()).hexdigest() == png_binding["sha256"]
    png_evidence = _json(png_evidence_path)
    assert png_evidence["sourceCommit"] == manifest["sourceCommit"]
    assert png_evidence["sourceManifestSha256"] == png_binding["sourceManifestSha256"]
    png_assets = {item["sourcePath"]: item["sha256"] for item in manifest["assets"] if item["path"].endswith(".png")}
    assert {item["path"]: item["sha256"] for item in png_evidence["entries"]} == png_assets
    assert all(item["status"] == "approved" and item["rightsHolder"] == "cty41"
               and item["license"] == "CC-BY-4.0" for item in png_evidence["entries"])


def test_poet_cast_draft_and_card_validate_and_reproduce_selection():
    draft = validate_draft(_json(EXAMPLE / "draft.json"))
    expected = validate_card(_json(CARD_PATH))

    reproduced = select_option(
        draft,
        option_id=expected["selection"]["optionId"],
        reviewer=expected["selection"]["reviewer"],
        reason=expected["selection"]["reason"],
        rejected_reasons={item["optionId"]: item["reason"] for item in expected["selection"]["rejectedOptions"]},
        selected_at=expected["selection"]["selectedAt"],
    )

    assert reproduced == expected
    assert reproduced["poseProofId"] == "pose-proof-88782028d22a7458"
