from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import pytest
from PIL import Image

from maliang_art.core import CollisionError
from maliang_art.pose import PoseProofError, load_draft, render_board, render_preview, save_png, select_option, validate_card, validate_draft, write_card


def test_validate_and_render_dimensions(draft):
    assert validate_draft(draft) is draft
    assert render_board(draft).size == (600, 410)
    assert render_preview(draft["options"][0], draft["canvas"]).size == (128, 128)


def test_canvas_and_preview_are_not_fixed_to_256_or_128(draft):
    draft["canvas"] = [512, 256]
    validate_draft(draft)
    assert render_board(draft).size == (1112, 410)
    assert render_preview(draft["options"][0], draft["canvas"]).size == (256, 128)
    assert render_preview(draft["options"][0], draft["canvas"], (180, 90)).size == (180, 90)


def test_board_uses_one_to_one_scale_and_bounds_large_canvases(draft):
    board = render_board(draft)
    assert board.getpixel((118, 242)) == (255, 106, 0, 255)

    draft["canvas"] = [8192, 8192]
    bounded = render_board(draft)
    assert bounded.width <= 2048
    assert bounded.height <= 2048
    assert bounded.width * bounded.height <= 2048 * 2048


def test_preview_rejects_oversized_allocation_before_pillow(draft, monkeypatch):
    def unexpected_allocation(*args, **kwargs):
        raise AssertionError("Pillow allocation should not be attempted")

    monkeypatch.setattr("maliang_art.pose.Image.new", unexpected_allocation)
    with pytest.raises(PoseProofError, match="render size exceeds"):
        render_preview(draft["options"][0], [8192, 8192], [4096, 1025])


def test_render_is_deterministic(draft):
    first = render_board(draft).tobytes()
    second = render_board(copy.deepcopy(draft)).tobytes()
    assert hashlib.sha256(first).digest() == hashlib.sha256(second).digest()

@pytest.mark.parametrize("direction", ["down-right", "up-left", "down-left", "up-right", "non-directional"])
def test_all_directions(direction, draft):
    draft["direction"] = direction
    validate_draft(draft)

@pytest.mark.parametrize("mutator", [
    lambda d: d.update(extra=True),
    lambda d: d.update(schemaVersion=2),
    lambda d: d.update(canvas=[8, 128]),
    lambda d: d.update(direction="left"),
    lambda d: d.update(options=[]),
    lambda d: d["options"][1].update(optionId="a"),
    lambda d: d["options"][0]["head"].update(radius=True),
    lambda d: d["options"][0]["head"].update(center=[256, 0]),
    lambda d: d["options"][0].update(segments=[]),
    lambda d: d["options"][0].update(equipmentAxis=[[0, 0]]),
])
def test_malformed_drafts_rejected(mutator, draft):
    mutator(draft)
    with pytest.raises(PoseProofError): validate_draft(draft)


def test_historical_evidence_can_verify_bytes_through_pose_validators(draft, tmp_path):
    artifact = tmp_path / "evidence.bin"
    artifact.write_bytes(b"evidence")
    draft["historicalEvidence"] = {
        "path": "evidence.bin",
        "sha256": hashlib.sha256(b"evidence").hexdigest(),
    }
    assert validate_draft(draft, root=tmp_path, verify=True) is draft

    card = select_option(
        draft, "a", "reviewer", "reason", {"b": "reason"},
        "2026-01-02T03:04:05Z",
    )
    assert validate_card(card, root=tmp_path, verify=True) is card

    artifact.write_bytes(b"tampered")
    with pytest.raises(PoseProofError, match="historicalEvidence is invalid"):
        validate_draft(draft, root=tmp_path, verify=True)
    with pytest.raises(PoseProofError, match="historicalEvidence is invalid"):
        validate_card(card, root=tmp_path, verify=True)


def test_explicit_null_historical_evidence_is_rejected(draft):
    draft["historicalEvidence"] = None
    with pytest.raises(PoseProofError, match="historicalEvidence"):
        validate_draft(draft)

    draft.pop("historicalEvidence")
    card = select_option(
        draft, "a", "reviewer", "reason", {"b": "reason"},
        "2026-01-02T03:04:05Z",
    )
    card["historicalEvidence"] = None
    with pytest.raises(PoseProofError, match="historicalEvidence"):
        validate_card(card)


def test_select_option_accepts_general_reviewer_and_is_stable(draft):
    kwargs = dict(option_id="a", reviewer="art-director", reason="Best silhouette", rejected_reasons={"b": "Closed shape"}, selected_at="2026-01-02T03:04:05Z")
    first = select_option(draft, **kwargs)
    second = select_option(copy.deepcopy(draft), **kwargs)
    assert first == second
    assert first["selection"]["reviewer"] == "art-director"
    validate_card(first)

@pytest.mark.parametrize("changes", [
    {"reviewer": ""}, {"reason": ""}, {"option_id": "missing"}, {"rejected_reasons": {}},
    {"rejected_reasons": {"b": ""}}, {"selected_at": "2026-01-02"},
])
def test_invalid_selection_rejected(changes, draft):
    kwargs = dict(option_id="a", reviewer="reviewer", reason="reason", rejected_reasons={"b": "reason"}, selected_at="2026-01-02T03:04:05+00:00")
    kwargs.update(changes)
    with pytest.raises(PoseProofError): select_option(draft, **kwargs)


def test_card_tamper_is_detected(draft):
    card = select_option(draft, "a", "reviewer", "reason", {"b": "reason"}, "2026-01-02T03:04:05Z")
    card["selection"]["reason"] = "tampered"
    with pytest.raises(PoseProofError): validate_card(card)


def test_card_immutable_writer(draft, tmp_path):
    card = select_option(draft, "a", "reviewer", "reason", {"b": "reason"}, "2026-01-02T03:04:05Z")
    path = write_card(card, tmp_path / "card.json")
    write_card(card, path)
    changed = copy.deepcopy(card); changed["selection"]["reason"] = "different"
    # Recompute a valid card before testing byte collision.
    changed = select_option(draft, "a", "reviewer", "different", {"b": "reason"}, "2026-01-02T03:04:05Z")
    with pytest.raises(CollisionError): write_card(changed, path)


def test_png_publication_is_immutable(tmp_path):
    path = save_png(Image.new("RGBA", (2, 2), "red"), tmp_path / "image.png")
    save_png(Image.new("RGBA", (2, 2), "red"), path)
    with pytest.raises(CollisionError): save_png(Image.new("RGBA", (2, 2), "blue"), path)


def test_load_draft_rejects_bad_json(tmp_path):
    path = tmp_path / "bad.json"; path.write_text("{", encoding="utf-8")
    with pytest.raises(PoseProofError): load_draft(path)


def test_v01_poet_card_bytes_are_unchanged():
    path = (
        Path(__file__).resolve().parents[1]
        / "examples/poet-cast/store/Tools/artworks/poet_five_red_chow/pose-proofs/poet_cast_dr_sheathed_focus_v1.json"
    )
    content = path.read_bytes()
    assert len(content) == 1735
    assert hashlib.sha256(content).hexdigest() == "51865e9d7f171fa781ff64a34f7f7cdd31a42479a9b1864ce62dda5fa446dadd"
