"""Command-line interface for MaLiang."""
from __future__ import annotations

import argparse
import getpass
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .core import MaLiangError, contained_path, write_immutable_bytes, write_immutable_json
from . import authoring
from .pose import load_draft, parse_rejected, render_board, render_preview, save_png, select_option, write_card
from .records import check_tree, load_json, validate_record
from . import review
from . import statemachine


def _parse_dimensions(value: str) -> tuple[int, int]:
    try:
        width_text, height_text = value.lower().split("x", 1)
        width, height = int(width_text), int(height_text)
    except (ValueError, AttributeError) as exc:
        raise argparse.ArgumentTypeError("size must use WIDTHxHEIGHT") from exc
    if not 1 <= width <= 8192 or not 1 <= height <= 8192:
        raise argparse.ArgumentTypeError("size dimensions must be from 1 through 8192")
    return width, height


def _pose_render(args: argparse.Namespace) -> int:
    draft = load_draft(args.spec)
    save_png(render_board(draft), args.output)
    if args.preview_dir:
        directory = Path(args.preview_dir)
        for option in draft["options"]:
            save_png(render_preview(option, draft["canvas"], args.preview_size), directory / f"{option['optionId']}.png")
    return 0


def _pose_select(args: argparse.Namespace) -> int:
    draft = load_draft(args.spec)
    card = select_option(draft, args.option_id, args.reviewer, args.reason, parse_rejected(args.rejected_reason), args.selected_at)
    write_card(card, args.output_card)
    if args.preview_output:
        save_png(render_preview(card["selectedOption"], card["canvas"], args.preview_size), args.preview_output)
    print(json.dumps(card, ensure_ascii=False, indent=2))
    return 0


def _design_inputs(args: argparse.Namespace) -> tuple[Any, Any, list[authoring.Diagnostic]]:
    values = {}
    diagnostics = []
    for name in ("contract", "draft"):
        try:
            values[name] = load_json(getattr(args, name))
        except MaLiangError as exc:
            diagnostics.append(authoring.Diagnostic(name, "invalid-json", str(exc)))
    if diagnostics:
        return None, None, diagnostics
    contract, draft = values["contract"], values["draft"]
    return contract, draft, authoring.validate_design(contract, draft)


def _design_report(diagnostics: list[authoring.Diagnostic]) -> None:
    print(json.dumps({"valid": not diagnostics, "diagnostics": [
        {"path": item.path, "code": item.code, "message": item.message}
        for item in diagnostics
    ]}, ensure_ascii=False, sort_keys=True))


def _design_validate(args: argparse.Namespace) -> int:
    _, _, diagnostics = _design_inputs(args)
    _design_report(diagnostics)
    return 1 if diagnostics else 0


def _design_compile(args: argparse.Namespace) -> int:
    contract, draft, diagnostics = _design_inputs(args)
    if diagnostics:
        _design_report(diagnostics)
        return 1
    try:
        packet = authoring.compile_design(contract, draft, debug_geometry=args.debug_geometry)
    except authoring.DesignError as exc:
        _design_report(exc.diagnostics)
        return 1
    root = Path(args.output_dir)
    # Preflight every relative path before publishing any member of the packet.
    for relative in ("design.json", *packet.guides):
        contained_path(root, relative)
    for relative, data in packet.guides.items():
        write_immutable_bytes(root, relative, data)
    write_immutable_json(root, "design.json", packet.document)
    print(json.dumps({"designId": packet.document["designId"], "packet": "design.json",
                      "guides": sorted(packet.guides)}, ensure_ascii=False, sort_keys=True))
    return 0


def _records_validate(args: argparse.Namespace) -> int:
    value = load_json(args.path)
    validate_record(value, args.schema, root=args.root, verify=args.verify)
    print(f"valid: {args.path}")
    return 0


def _records_check(args: argparse.Namespace) -> int:
    count, errors = check_tree(args.root, verify=args.verify)
    for error in errors:
        print(error, file=sys.stderr)
    print(f"checked {count} JSON record(s); {len(errors)} error(s)")
    return 1 if errors else 0


def _git_config(key: str) -> str | None:
    try:
        result = subprocess.run(["git", "config", "--get", key], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip()
    return value if result.returncode == 0 and value else None


def _reviewer_identity() -> tuple[str, str]:
    name, email = _git_config("user.name"), _git_config("user.email")
    if name:
        return (f"{name} <{email}>" if email else name), "git-config"
    try:
        user = getpass.getuser()
    except (OSError, KeyError, ImportError) as exc:
        raise MaLiangError("cannot determine reviewer identity from git config or the OS user") from exc
    return user, "os-user"


def _concept_records(root: str) -> list[dict[str, Any]]:
    from .records import infer_schema
    records = []
    for path in sorted(Path(root).rglob("*.json")):
        value = load_json(path)
        try:
            kind = infer_schema(value)
        except MaLiangError:
            continue
        if kind in {"concept-style-guide", "character-concept", "identity-markers"}:
            records.append(validate_record(value, kind))
    return records


def _concept_review(args: argparse.Namespace) -> int:
    from .concept import review_questions, review_sheet
    records = _concept_records(args.records)
    concept = next((r for r in records if r.get("conceptId") == args.concept and "form" in r), None)
    if concept is None:
        raise MaLiangError(f"unknown concept: {args.concept}")
    style = next((r for r in records if r.get("styleId") == concept["styleId"] and "rules" in r), None)
    markers = next((r for r in records if "markersId" in r and args.concept in r["conceptIds"]), None)
    if style is None or markers is None:
        raise MaLiangError("review needs the concept's style guide and identity markers in the same directory")
    if args.format == "questions":
        sys.stdout.write(json.dumps(review_questions(style, concept, markers), ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(review_sheet(style, concept, markers))
    return 0


def _concept_approve(args: argparse.Namespace) -> int:
    from .adapters import PillowImageAdapter
    from .concept import apply_decision
    path = Path(args.path)
    record = load_json(path)
    image = size = None
    if args.image:
        root = Path(args.root) if args.root else path.parent
        image, size = PillowImageAdapter().bind_image(root, args.image)
    reviewer, source = _reviewer_identity()
    at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = apply_decision(record, args.decision, reviewer=reviewer, source=source, at=at,
                            note=args.note, image=image, image_size=size)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(path), "approval": result["approval"]}, ensure_ascii=False))
    return 0


def _intake_start(args: argparse.Namespace) -> int:
    from .intake import validate_catalog, validate_intake
    catalog = validate_catalog(load_json(args.catalog))
    path = Path(args.intake)
    if path.exists():
        raise MaLiangError(f"intake already exists: {path}")
    record = {"schemaVersion": 1, "intakeId": args.intake_id or path.stem, "catalogId": catalog["catalogId"],
              "request": args.request, "answers": []}
    validate_intake(record, catalog)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"intake": str(path)}, ensure_ascii=False))
    return 0


def _intake_next(args: argparse.Namespace) -> int:
    from .intake import next_questions
    print(json.dumps(next_questions(load_json(args.catalog), load_json(args.intake), limit=args.limit),
                     ensure_ascii=False, indent=2))
    return 0


def _intake_answer(args: argparse.Namespace) -> int:
    from .intake import IntakeError, presented_options, validate_intake
    catalog, path = load_json(args.catalog), Path(args.intake)
    record = load_json(path)
    answer: dict[str, Any] = {"dimension": args.dimension}
    if args.option is not None:
        answer["option"] = args.option
    else:
        answer["text"] = args.text
    answer["source"] = args.source or ("catalog-option" if args.option is not None else "user-text")
    if args.confirmation:
        answer["confirmation"] = args.confirmation
    if args.follow_up_of:
        answer["followUpOf"], answer["prompt"] = args.follow_up_of, args.prompt
    if args.presented_json is not None:
        try:
            answer["presented"] = json.loads(args.presented_json)
        except json.JSONDecodeError as exc:
            raise IntakeError(f"--presented-json is not valid JSON: {exc}") from exc
    elif args.follow_up_of:
        answer["presented"] = []
    else:
        answer["presented"] = presented_options(catalog, args.dimension)
    updated = {**record, "answers": [*record["answers"], answer]}
    validate_intake(updated, catalog)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(answer, ensure_ascii=False))
    return 0


def _intake_draft(args: argparse.Namespace) -> int:
    from .intake import draft_from_intake
    print(json.dumps(draft_from_intake(load_json(args.catalog), load_json(args.intake)), ensure_ascii=False, indent=2))
    return 0


def _review_validate(args: argparse.Namespace) -> int:
    value = load_json(args.path)
    authority = review.ReviewAuthority(args.authority_reviewer)
    validators: dict[str, Callable[[Any], Any]] = {
        "rule": review.validate_review_rule,
        "case": lambda record: review.validate_review_case(record, authority=authority),
        "packet": review.validate_model_review_packet,
        "experience": lambda record: review.validate_experience_candidate(record, authority=authority),
        "comparison-arm": review.validate_prompt_only_comparison_arm,
    }
    validators[args.kind](value)
    print(f"valid {args.kind}: {args.path}")
    return 0


def _flow_validate(args: argparse.Namespace) -> int:
    policy = statemachine.load_policy(args.path)
    print(f"valid policy: {policy.name}")
    return 0


def _flow_show_default_template(_args: argparse.Namespace) -> int:
    sys.stdout.write(statemachine.default_template_text())
    return 0


def _flow_transitions(args: argparse.Namespace) -> int:
    policy = statemachine.load_policy(args.path)
    if args.state not in policy.states:
        raise MaLiangError(f"unknown state: {args.state}")
    for transition in policy.transitions:
        if args.state in transition.from_states:
            print(f"{transition.transition_id} -> {transition.to_state}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="maliang-art", description="Deterministic game-art workflow records")
    groups = parser.add_subparsers(dest="group", required=True)

    pose = groups.add_parser("pose", help="render and select pose proofs")
    pose_commands = pose.add_subparsers(dest="command", required=True)
    render = pose_commands.add_parser("render-options", help="render a pose option board")
    render.add_argument("--spec", required=True)
    render.add_argument("--output", required=True)
    render.add_argument("--preview-dir")
    render.add_argument("--preview-size", type=_parse_dimensions, metavar="WIDTHxHEIGHT",
                        help="default: half the canvas dimensions, reduced proportionally (rounded down) to fit the 4,194,304-pixel budget; explicit sizes over the budget are rejected")
    render.set_defaults(handler=_pose_render)
    select = pose_commands.add_parser("select-option", help="publish a selected pose card")
    select.add_argument("--spec", required=True)
    select.add_argument("--option-id", required=True)
    select.add_argument("--output-card", required=True)
    select.add_argument("--reviewer", required=True)
    select.add_argument("--reason", required=True)
    select.add_argument("--rejected-reason", action="append", default=[])
    select.add_argument("--selected-at", required=True)
    select.add_argument("--preview-output")
    select.add_argument("--preview-size", type=_parse_dimensions, metavar="WIDTHxHEIGHT",
                        help="default: half the canvas dimensions, reduced proportionally (rounded down) to fit the 4,194,304-pixel budget; explicit sizes over the budget are rejected")
    select.set_defaults(handler=_pose_select)

    design = groups.add_parser("design", help="validate and compile offline visual execution briefs")
    design_commands = design.add_subparsers(dest="command", required=True)
    for command, handler in (("validate", _design_validate), ("compile", _design_compile)):
        design_command = design_commands.add_parser(command)
        design_command.add_argument("--contract", required=True, help="family contract JSON file")
        design_command.add_argument("--draft", required=True, help="sprite slice draft JSON file")
        if command == "compile":
            design_command.add_argument("--output-dir", required=True, help="publication root for design.json and optional debug guides/")
            design_command.add_argument("--debug-geometry", action="store_true", help="render optional unapproved debug layouts; never generation inputs")
        design_command.set_defaults(handler=handler)

    records = groups.add_parser("records", help="validate portable records")
    record_commands = records.add_subparsers(dest="command", required=True)
    validate = record_commands.add_parser("validate")
    validate.add_argument("path")
    validate.add_argument("--schema", choices=["auto", "artifact", "pose-draft", "pose-card", "invocation", "delivery", "failure",
                                                 "concept-style-guide", "character-concept", "identity-markers", "derived-usage"], default="auto")
    validate.add_argument("--root")
    validate.add_argument("--verify", action="store_true")
    validate.set_defaults(handler=_records_validate)
    check = record_commands.add_parser("check")
    check.add_argument("root")
    check.add_argument("--verify", action="store_true")
    check.set_defaults(handler=_records_check)

    concept = groups.add_parser("concept", help="print concept review sheets and record human decisions")
    concept_commands = concept.add_subparsers(dest="command", required=True)
    concept_review = concept_commands.add_parser("review", help="print the review sheet for one concept")
    concept_review.add_argument("records", help="directory holding the style guide, concept, and identity markers")
    concept_review.add_argument("--concept", required=True)
    concept_review.add_argument("--format", choices=["markdown", "questions"], default="markdown",
                                help="questions prints AskQuestion JSON")
    concept_review.set_defaults(handler=_concept_review)
    concept_approve = concept_commands.add_parser(
        "approve", help="record a decision the human gave explicitly; reviewer comes from git config or the OS user")
    concept_approve.add_argument("path", help="character-concept or derived-usage JSON file")
    concept_approve.add_argument("--decision", required=True, choices=["approved", "rejected"])
    concept_approve.add_argument("--image", help="concept image path relative to --root")
    concept_approve.add_argument("--root", help="project root for --image; defaults to the record's directory")
    concept_approve.add_argument("--note")
    concept_approve.set_defaults(handler=_concept_approve)

    intake = groups.add_parser("intake", help="ask broad art requests as explicit choice questions")
    intake_commands = intake.add_subparsers(dest="command", required=True)
    intake_start = intake_commands.add_parser("start", help="create an empty intake record for a catalog")
    intake_start.add_argument("catalog")
    intake_start.add_argument("intake")
    intake_start.add_argument("--request", required=True, help="the user's original request, verbatim")
    intake_start.add_argument("--intake-id")
    intake_start.set_defaults(handler=_intake_start)
    intake_next = intake_commands.add_parser("next", help="print the next round of questions as AskQuestion JSON")
    intake_next.add_argument("catalog")
    intake_next.add_argument("intake")
    intake_next.add_argument("--limit", type=int, default=3)
    intake_next.set_defaults(handler=_intake_next)
    intake_answer = intake_commands.add_parser("answer", help="record one answer the user explicitly gave")
    intake_answer.add_argument("catalog")
    intake_answer.add_argument("intake")
    intake_answer.add_argument("--dimension", required=True)
    choice = intake_answer.add_mutually_exclusive_group(required=True)
    choice.add_argument("--option")
    choice.add_argument("--text")
    intake_answer.add_argument("--source", choices=["catalog-option", "ai-suggested-option", "user-text", "ai-inferred-confirmed"])
    intake_answer.add_argument("--presented-json", help="options actually shown; defaults to the catalog options")
    intake_answer.add_argument("--confirmation", help="the user's confirming words for ai-inferred-confirmed")
    intake_answer.add_argument("--follow-up-of")
    intake_answer.add_argument("--prompt", help="follow-up question text")
    intake_answer.set_defaults(handler=_intake_answer)
    intake_draft = intake_commands.add_parser("draft", help="print draft style-guide fields and open decisions")
    intake_draft.add_argument("catalog")
    intake_draft.add_argument("intake")
    intake_draft.set_defaults(handler=_intake_draft)

    review_parser = groups.add_parser("review", help="validate review-core records")
    review_commands = review_parser.add_subparsers(dest="command", required=True)
    review_validate = review_commands.add_parser("validate")
    review_validate.add_argument("kind", choices=["rule", "case", "packet", "experience", "comparison-arm"])
    review_validate.add_argument("path")
    review_validate.add_argument("--authority-reviewer", required=True, help="human authority identity for project-bound records")
    review_validate.set_defaults(handler=_review_validate)

    flow = groups.add_parser("flow", help="validate state-machine policies and inspect transitions")
    flow_commands = flow.add_subparsers(dest="command", required=True)
    flow_validate = flow_commands.add_parser("validate")
    flow_validate.add_argument("path")
    flow_validate.set_defaults(handler=_flow_validate)
    flow_template = flow_commands.add_parser("show-default-template")
    flow_template.set_defaults(handler=_flow_show_default_template)
    flow_transitions = flow_commands.add_parser("transitions")
    flow_transitions.add_argument("path")
    flow_transitions.add_argument("--state", required=True)
    flow_transitions.set_defaults(handler=_flow_transitions)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (MaLiangError, review.ReviewValidationError) as exc:
        parser.error(str(exc))
    return 2
