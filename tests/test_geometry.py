"""Bounded geometry slice: measure, transform, compare, review board.

Synthetic tiny PNGs + masks prove the S5 split: core metrics ignore tail/wing
pixels outside the semantic mask, while the full alpha outline tracks them.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image

from maliang_art.geometry import (
    GeometryError,
    MissingMaskError,
    compare_core,
    fit_uniform,
    measure_alpha_bbox,
    measure_core,
    measure_ground,
    render_review_board,
)

CORE = (255, 0, 0, 255)
BODY = (200, 40, 40, 255)
TAIL = (40, 40, 200, 255)


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=False, compress_level=9)
    return buffer.getvalue()


def blank(width: int = 16, height: int = 16) -> Image.Image:
    return Image.new("RGBA", (width, height), (0, 0, 0, 0))


def paint_body(image: Image.Image, mask: Image.Image | None, box=(4, 6, 8, 12)) -> None:
    """Paint a solid body rect (x0, y0, x1, y1) exclusive on x1/y1."""
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        for x in range(x0, x1):
            image.putpixel((x, y), BODY)
            if mask is not None:
                mask.putpixel((x, y), CORE)


def paint_tail(image: Image.Image, box=(8, 8, 13, 10)) -> None:
    """Paint a tail/wing that stays OUTSIDE the core mask."""
    x0, y0, x1, y1 = box
    for y in range(y0, y1):
        for x in range(x0, x1):
            image.putpixel((x, y), TAIL)


def pair(with_tail: bool, size: int = 16) -> tuple[bytes, bytes]:
    image = blank(size, size)
    mask = blank(size, size)
    paint_body(image, mask)
    if with_tail:
        paint_tail(image)
    return png_bytes(image), png_bytes(mask)


# --- measure -----------------------------------------------------------------


def test_tail_outside_core_mask_does_not_change_core_metrics():
    image_a, mask = pair(with_tail=False)
    image_b, _ = pair(with_tail=True)

    core_a = measure_core(image_a, mask)
    core_b = measure_core(image_b, mask)

    assert core_a.bbox == core_b.bbox
    assert core_a.width == core_b.width == 4
    assert core_a.height == core_b.height == 6
    assert core_a.center == core_b.center
    assert core_a.section_widths == core_b.section_widths


def test_tail_outside_core_mask_does_change_alpha_bbox():
    image_a, _ = pair(with_tail=False)
    image_b, _ = pair(with_tail=True)

    alpha_a = measure_alpha_bbox(image_a)
    alpha_b = measure_alpha_bbox(image_b)

    assert alpha_a.bbox != alpha_b.bbox
    assert alpha_b.width > alpha_a.width
    assert alpha_b.bbox.max_x > alpha_a.bbox.max_x


def test_measure_alpha_bbox_reports_outline_metrics():
    image, _ = pair(with_tail=False)
    outline = measure_alpha_bbox(image)
    assert outline.bbox.min_x == 4
    assert outline.bbox.min_y == 6
    assert outline.bbox.max_x == 7
    assert outline.bbox.max_y == 11
    assert outline.width == 4
    assert outline.height == 6
    assert outline.center == (6.0, 9.0)


def test_measure_core_section_widths_are_top_mid_bottom_thirds():
    image, mask = pair(with_tail=False)
    core = measure_core(image, mask)
    # Body is 4 wide across the full height, so each third is 4 wide.
    assert core.section_widths == (4, 4, 4)

    stepped = blank(16, 16)
    stepped_mask = blank(16, 16)
    # top third 6 wide, mid 4 wide, bottom 2 wide within y=6..12
    for y in range(6, 8):
        for x in range(4, 10):
            stepped.putpixel((x, y), BODY)
            stepped_mask.putpixel((x, y), CORE)
    for y in range(8, 10):
        for x in range(5, 9):
            stepped.putpixel((x, y), BODY)
            stepped_mask.putpixel((x, y), CORE)
    for y in range(10, 12):
        for x in range(6, 8):
            stepped.putpixel((x, y), BODY)
            stepped_mask.putpixel((x, y), CORE)

    stepped_core = measure_core(png_bytes(stepped), png_bytes(stepped_mask))
    assert stepped_core.section_widths[0] == 6
    assert stepped_core.section_widths[1] == 4
    assert stepped_core.section_widths[2] == 2


def test_measure_core_requires_same_size_semantic_mask():
    image, mask = pair(with_tail=False)
    small = png_bytes(blank(8, 8))
    with pytest.raises(GeometryError, match="same size|size"):
        measure_core(image, small)

    with pytest.raises(MissingMaskError):
        measure_core(image, None)  # type: ignore[arg-type]

    with pytest.raises(MissingMaskError):
        measure_core(image, b"")


def test_measure_core_never_infers_core_from_alpha_alone():
    """A full-alpha image with no red core in the mask must not report core."""
    image = png_bytes(Image.new("RGBA", (16, 16), BODY))
    empty_mask = png_bytes(blank(16, 16))
    with pytest.raises(GeometryError, match="core"):
        measure_core(image, empty_mask)


def test_measure_ground_reports_lowest_pixel_and_declared_contacts():
    image, _ = pair(with_tail=False)
    ground = measure_ground(image)
    assert ground.lowest_nontransparent_y == 11
    assert ground.contact_points is None
    assert ground.status == "pending"

    declared = measure_ground(image, contact_points=[(4, 11), (7, 11)])
    assert declared.lowest_nontransparent_y == 11
    assert declared.contact_points == ((4, 11), (7, 11))
    assert declared.status == "declared"


# --- transform ---------------------------------------------------------------


def test_fit_uniform_scales_core_to_target_height_and_baseline():
    image, mask = pair(with_tail=False)
    result = fit_uniform(
        image,
        mask,
        canvas=(32, 32),
        baseline_y=30,
        target_height=12,
        anchor_x=16,
    )
    assert result.scale == pytest.approx(2.0)
    assert result.mask_bytes is not None
    assert result.transform_record["scale"] == pytest.approx(2.0)
    assert result.transform_record["offset"]["x"] == result.offset_x
    assert result.transform_record["offset"]["y"] == result.offset_y

    assert result.source_core is not None
    assert result.target_core is not None
    assert result.source_core.height == 6
    assert result.target_core.height == 12
    # Bottom of the core lands on the declared baseline.
    assert result.target_core.bbox.max_y == 30
    # Source measurements are preserved on the result.
    assert result.source_alpha.height == 6
    assert result.source_core.bbox == result.source_core.bbox

    src_box = result.transform_record["sourceCoreBbox"]
    dst_box = result.transform_record["targetCoreBbox"]
    assert src_box is not None and dst_box is not None
    assert dst_box["maxY"] == 30


def test_fit_uniform_requires_mask_for_core_anchoring_and_never_fakes_core():
    image, _ = pair(with_tail=False)
    result = fit_uniform(
        image,
        None,
        canvas=(32, 32),
        baseline_y=30,
        target_height=12,
        anchor_x=16,
    )
    assert result.source_core is None
    assert result.target_core is None
    assert result.transform_record["sourceCoreBbox"] is None
    assert result.transform_record["targetCoreBbox"] is None
    # Alpha outline is used for fitting when no mask is supplied.
    assert result.source_alpha.height == 6
    assert result.target_alpha.height == 12
    assert result.target_alpha.bbox.max_y == 30


def test_fit_uniform_rejects_non_uniform_scale():
    image, mask = pair(with_tail=False)
    with pytest.raises(GeometryError, match="non-uniform"):
        fit_uniform(image, mask, canvas=(32, 32), baseline_y=20, scale=(2.0, 1.0))
    with pytest.raises(GeometryError, match="non-uniform"):
        fit_uniform(image, mask, canvas=(32, 32), baseline_y=20, scale=(1.0, 2.0))
    # Uniform pair is accepted.
    ok = fit_uniform(image, mask, canvas=(32, 32), baseline_y=20, scale=(2.0, 2.0), anchor_x=16)
    assert ok.scale == pytest.approx(2.0)


def test_fit_uniform_rejects_overflow_without_silent_crop():
    image, mask = pair(with_tail=False)
    with pytest.raises(GeometryError, match="overflow|outside|fit"):
        fit_uniform(image, mask, canvas=(10, 10), baseline_y=30, target_height=12, anchor_x=5)
    # Scaling that fits width/height but places content outside the canvas.
    with pytest.raises(GeometryError, match="overflow|outside|fit"):
        fit_uniform(image, mask, canvas=(16, 16), baseline_y=100, target_height=6, anchor_x=8)


def test_fit_uniform_applies_uniform_scale_and_integer_translation_only():
    image, mask = pair(with_tail=False)
    result = fit_uniform(
        image,
        mask,
        canvas=(32, 32),
        baseline_y=30,
        target_height=12,
        anchor_x=16,
    )
    assert isinstance(result.scale, float)
    assert isinstance(result.offset_x, int) and isinstance(result.offset_y, int)
    # Identity scale keeps source measurements and only translates.
    moved = fit_uniform(
        image,
        mask,
        canvas=(32, 32),
        baseline_y=30,
        target_height=6,
        anchor_x=16,
    )
    assert moved.scale == pytest.approx(1.0)
    # Identity scale preserves core size; only the integer translation changes.
    assert moved.source_core.width == moved.target_core.width
    assert moved.source_core.height == moved.target_core.height


def test_fit_uniform_requires_baseline_y():
    image, mask = pair(with_tail=False)
    with pytest.raises(GeometryError, match="baseline_y"):
        fit_uniform(image, mask, canvas=(32, 32))


def test_fit_uniform_transforms_contact_points_with_same_scale_offset():
    from maliang_art.geometry import fit_uniform as fu
    image, mask = pair(with_tail=False)
    contacts = [(10, 20)]
    result = fu(
        image,
        mask,
        canvas=(32, 32),
        baseline_y=30,
        target_height=12,
        anchor_x=16,
        contact_points=contacts,
    )
    assert result.source_ground is not None
    assert result.source_ground.contact_points == ((10, 20),)
    assert result.target_ground is not None
    assert result.target_ground.contact_points is not None
    # scale=2.0, offset=(offset_x, offset_y): target = round(src*scale) + offset
    tc = result.target_ground.contact_points[0]
    assert tc == (round(10 * 2.0) + result.offset_x, round(20 * 2.0) + result.offset_y)


def test_compare_core_tilted_variant_not_rejected_by_aabb():
    """A lean/spread-wing variant changes alpha bbox but core dimensions stay within tolerance.

    E5 requires: 'tilt does not cause full-image AABB mis-rejection'. compare_core
    uses core dimensions only, so a tilted candidate with unchanged core passes
    even though its alpha bbox grew.
    """
    from maliang_art.geometry import compare_core, measure_core

    # Base: 10x10 core in a 10x10 image.
    base_img = Image.new("RGBA", (10, 10), (200, 100, 50, 255))
    base_mask = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    for y in range(10):
        for x in range(10):
            base_mask.putpixel((x, y), (255, 0, 0, 255))
    base_measure = measure_core(
        png_bytes(base_img), png_bytes(base_mask), (255, 0, 0, 255),
    )

    # Leaned/spread variant: same 10x10 core, but extra wing pixels extend alpha bbox to 20 wide.
    lean_img = Image.new("RGBA", (20, 10), (0, 0, 0, 0))
    lean_mask = Image.new("RGBA", (20, 10), (0, 0, 0, 0))
    for y in range(10):
        for x in range(10, 20):
            lean_img.putpixel((x, y), (200, 100, 50, 255))  # wing extends alpha
    for y in range(10):
        for x in range(10):
            lean_img.putpixel((x, y), (200, 100, 50, 255))
            lean_mask.putpixel((x, y), (255, 0, 0, 255))
    lean_measure = measure_core(
        png_bytes(lean_img), png_bytes(lean_mask), (255, 0, 0, 255),
    )

    # Core dimensions identical, so comparison passes at tolerance 0.
    result = compare_core(base_measure, lean_measure, tolerance=0)
    assert result["passed"] is True
    # Alpha bbox DID change (sanity: the lean variant really is wider overall).
    from maliang_art.geometry import measure_alpha_bbox
    base_alpha = measure_alpha_bbox(png_bytes(base_img))
    lean_alpha = measure_alpha_bbox(png_bytes(lean_img))
    assert lean_alpha.bbox.width > base_alpha.bbox.width


# --- compare -----------------------------------------------------------------


def _core_from_pair(image: bytes, mask: bytes):
    return measure_core(image, mask)


def test_compare_core_uses_caller_tolerance_not_hardcoded_122():
    image_a, mask_a = pair(with_tail=False)

    # Body 6 wide vs 4 wide → delta 2 on width and section widths.
    img_b = blank()
    mask_b_img = blank()
    paint_body(img_b, mask_b_img, box=(4, 6, 10, 12))
    image_b, mask_b = png_bytes(img_b), png_bytes(mask_b_img)

    a = _core_from_pair(image_a, mask_a)
    b = _core_from_pair(image_b, mask_b)

    strict = compare_core(a, b, 0)
    medium = compare_core(a, b, 1)
    loose = compare_core(a, b, 2)
    huge = compare_core(a, b, 122)

    assert not strict["passed"]
    assert not medium["passed"]
    assert loose["passed"]
    assert huge["passed"]

    # Per-dimension detail is present and uses the caller's tolerance.
    width_info = strict["dimensions"]["width"]
    assert width_info["a"] == 4
    assert width_info["b"] == 6
    assert width_info["delta"] == 2
    assert width_info["tolerance"] == 0
    assert width_info["passed"] is False

    assert loose["dimensions"]["width"]["tolerance"] == 2
    assert loose["dimensions"]["width"]["passed"] is True
    # Height is unchanged and passes even at tolerance 0.
    assert strict["dimensions"]["height"]["passed"] is True


def test_compare_core_per_dimension_tolerance_mapping():
    image_a, mask_a = pair(with_tail=False)
    img_b = blank()
    mask_b_img = blank()
    paint_body(img_b, mask_b_img, box=(4, 6, 10, 12))
    b = measure_core(png_bytes(img_b), png_bytes(mask_b_img))
    a = measure_core(image_a, mask_a)

    result = compare_core(
        a,
        b,
        {
            "width": 0,
            "height": 0,
            "centerX": 5,
            "centerY": 0,
            "sectionTopWidth": 0,
            "sectionMidWidth": 0,
            "sectionBottomWidth": 0,
        },
    )
    assert not result["passed"]
    assert result["dimensions"]["width"]["passed"] is False
    assert result["dimensions"]["height"]["passed"] is True
    assert result["dimensions"]["centerX"]["passed"] is True


# --- review board ------------------------------------------------------------


def test_review_board_returns_deterministic_png_bytes():
    image_a, _ = pair(with_tail=False)
    image_b, _ = pair(with_tail=True)
    candidates = [
        {"image_bytes": image_a, "label": "DR"},
        {"image_bytes": image_b, "label": "UL"},
    ]
    first = render_review_board(candidates, cell_size=32, columns=2)
    second = render_review_board(candidates, cell_size=32, columns=2)
    assert first == second
    assert first.startswith(b"\x89PNG\r\n\x1a\n")
    assert Image.open(io.BytesIO(first)).size[0] == 64


def test_review_board_changes_when_layout_or_labels_change():
    image_a, _ = pair(with_tail=False)
    image_b, _ = pair(with_tail=True)
    base = [{"image_bytes": image_a, "label": "DR"}, {"image_bytes": image_b, "label": "UL"}]
    relabeled = [{"image_bytes": image_a, "label": "UL"}, {"image_bytes": image_b, "label": "DR"}]
    a = render_review_board(base, cell_size=32, columns=2)
    b = render_review_board(relabeled, cell_size=32, columns=2)
    c = render_review_board(base, cell_size=32, columns=1)
    assert a != b
    assert a != c


def test_review_board_is_pure_no_filesystem_side_effects(tmp_path):
    image_a, _ = pair(with_tail=False)
    before = set(tmp_path.iterdir())
    render_review_board([{"image_bytes": image_a, "label": "A"}], cell_size=16, columns=1)
    assert set(tmp_path.iterdir()) == before
