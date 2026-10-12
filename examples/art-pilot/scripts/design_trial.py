"""Run the design dry-run for a character and print missing decisions in plain language."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from maliang_art.authoring import validate_design
from maliang_art.core import contained_path

PILOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run design validation and list missing decisions")
    parser.add_argument("--character", required=True)
    parser.add_argument("--project", default=str(PILOT))
    parser.add_argument("--draft", help="project-relative draft JSON; defaults to the character's draft-example.json")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    root = contained_path(project / "characters", args.character)
    contract_path = root / "family-contract.json"
    draft_path = contained_path(project, args.draft) if args.draft else root / "draft-example.json"
    if not contract_path.is_file():
        raise SystemExit(f"missing {contract_path}")
    if not draft_path.is_file():
        raise SystemExit(f"missing {draft_path}")

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    draft = json.loads(draft_path.read_text(encoding="utf-8"))
    diagnostics = validate_design(contract, draft)

    if not diagnostics:
        print(f"design is complete for {args.character}; ready to compile")
        return 0

    print(f"design dry-run: {args.character}")
    print(f"  contract: {contract.get('familyId', '?')}")
    print(f"  missing / blocked decisions ({len(diagnostics)}):\n")
    for d in diagnostics:
        label = {"missing-decision": "MISSING", "unsupported": "UNSUPPORTED",
                 "conflict": "CONFLICT", "invalid": "INVALID"}.get(d.code, d.code.upper())
        print(f"  [{label}] {d.path}")
        print(f"           {d.message}")
    print()
    print("Human decision checklist:")
    print("  1. Identity features — which 3-5 marks must be visible at 150px (e.g. hooked-beak, malar-mark)")
    print("  2. Identity priority — what to read first at small size")
    print("  3. Visual moment — what the idle pose is doing (e.g. 'alert upright, level gaze, wings tight')")
    print("  4. Style reference image — pick one or more (optional but recommended)")
    print("  5. Palette confirmation — main/secondary/outline/accent colors")
    print("  6. Display context — target sizes and who to compare against")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
