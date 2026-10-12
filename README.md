# MaLiang

**Turn visual intent into auditable game art.**

MaLiang is a small, provider-neutral Python toolkit for deterministic game-art
workflow records. The distribution is **`maliang-game-art`**, the import package
is **`maliang_art`**, and the command is **`maliang-art`**.

Version 0.1 focuses on safe records rather than asset generation: canonical JSON
identities, collision-safe immutable publication, path containment, synthetic
pose-proof rendering, artifact bindings, review-policy validation, and neutral
invocation/delivery/failure envelopes.

## Start here

- **Use MaLiang:** [art-pilot sample](examples/art-pilot/README.md) and its
  [runbook](examples/art-pilot/docs/runbook.md) cover offline practice, request
  preparation, external execution, and exact-candidate review/adoption.
- **Use it with an Agent:** [maliang-art skill](skills/maliang-art/SKILL.md)
  provides the asset-making workflow; [llms.txt](llms.txt) is a document map.
  Loading or installing a skill depends on the host; these links do not grant
  image-tool access or automatically install anything.
- **Develop MaLiang:** [CONTRIBUTING.md](CONTRIBUTING.md),
  [AGENTS.md](AGENTS.md), and [SECURITY.md](SECURITY.md).

These repository-relative guides and the skill require a source checkout;
wheel installation does not include them, and the sdist omits the skill and
runbook. Design specs record decisions and pending work, not executable APIs.

## Install

```console
python -m pip install "maliang-game-art @ git+https://github.com/cty41/maliang.git@v0.1.0"
```

`maliang-game-art` is the distribution name and is unrelated to the PyPI project
named `maliang`. Pillow is pinned to the supported `>=10.4,<13` range. Python
3.10+ is required.

## CLI

```console
maliang-art pose render-options --spec draft.json --output board.png --preview-dir previews --preview-size 160x90
maliang-art pose select-option --spec draft.json --option-id arc-a \
  --output-card card.json --reviewer art-director --reason "Readable silhouette" \
  --rejected-reason "arc-b=Weaker contact" --selected-at 2026-01-01T12:00:00Z
maliang-art records validate draft.json --schema pose-draft
maliang-art records validate invocation.json --schema invocation
maliang-art records validate delivery.json --schema delivery --root . --verify
maliang-art records validate examples/poet-cast/draft.json --schema pose-draft
maliang-art records check path/to/record-tree
maliang-art review validate rule review-rule.json --authority-reviewer art-director
```

Pose canvases are record-defined. In current source, `render_preview` and the CLI
use half the canvas dimensions by default, reduced proportionally (rounded down)
when needed to fit the 4,194,304-pixel budget. The complete canvas is fitted, not
cropped. Explicit `--preview-size WIDTHxHEIGHT` values over that budget are rejected.
Board and preview allocations are bounded to prevent oversized records exhausting memory.
`pose select-option` requires an explicit reviewer but never assumes a particular
person. Every unselected option needs one reason. Existing output bytes are
immutable: repeating identical work succeeds, while different content at the
same path fails.

## Offline design CLI (source checkout)

The `flow` and `design` commands below are current-source features, not part of
the published v0.1.0 tag above. Install the current source (no new release is implied):

```console
git clone https://github.com/cty41/maliang.git
cd maliang
python -m venv .venv
```

Activate `.venv` with `.venv\Scripts\Activate.ps1` (PowerShell) or
`source .venv/bin/activate` (Unix), then run from the repository root:

```console
python -m pip install .
python -m maliang_art design validate --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json
python -m maliang_art design compile --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json --output-dir work/art-pilot/readme-design
```

Both sample commands exit 0 on success; compile prints a manifest with
`"packet": "design.json"` and `"guides": []`. The output is an execution brief
under ignored `work/art-pilot/`, not a generated or approved character image.
Use a new output directory when changing the inputs.

For your own design, provide the explicit JSON records defined by
`schemas/v1/art-family-contract.schema.json` and `schemas/v1/sprite-slice-draft.schema.json`:

```console
maliang-art design validate --contract family.json --draft slice.json
maliang-art design compile --contract family.json --draft slice.json --output-dir work/design-v1
```

`validate` writes JSON `{ "valid": true, "diagnostics": [] }` on success (exit 0).
Invalid/incomplete records, missing files and malformed JSON produce exit 1 and
JSON diagnostics with `path`, `code`, and `message`; it does not guess missing
art decisions. `compile` uses the same visual validation and publishes `design.json`
with a complete prompt, view/state tasks, inherited targets, ordered reference
roles/hashes, pending acceptance requirements and context-board layout. By default
it renders no images: `imageInputs` contains only the declared references in their
original order. Family `variants` and numeric part coordinates are not required;
topology parts can describe species structure with `id` and optional `description`.
Visual shape intentions must be allowed by the family, not by the debug renderer.
The supported camera profile is explicit isometric DR/UL with project-accepted
mirror-derived directions. This prepares an execution brief, not an approved design.

The existing capsule/ball renderer is available only as an optional debug mode:

```console
maliang-art design compile --contract family.json --draft slice.json --output-dir work/debug-v1 --debug-geometry
```

This mode requires explicit numeric variants and part anchor/size pairs, validates
layout bounds, and additionally publishes `guides/*.png`. Its artifacts are labeled
**debug-layout**, **unapproved**, **not-generation-input** and never enter
`imageInputs`. Ellipsoid placeholders and screen-direction triangles show code
layout only: they do not prove species, silhouette design, DR/UL projection,
action pose, style, core measurements or cross-view/state consistency. Their
coordinates do not become generation instructions. No debug layout needs to be
selected or approved before visual exploration.

Success prints a JSON file manifest; publication/path errors fail nonzero on
stderr. Identical reruns keep existing bytes; different bytes at an existing
file are rejected. Publication is immutable per file, not a multi-file transaction:
an interrupted/failed debug run may leave guides, and an identical rerun can finish
it. Use a new output directory for a changed brief or debug mode.

Palette and artistic judgments remain pending human review; context boards are
layouts, not future candidate images. Reference paths/hashes and borrowing roles
are declarations only: this command neither reads/verifies nor copies reference
images. Empty references support from-scratch exploration. Backend parameters and
image-input submission remain unverified until bound by an execution adapter.
The design command performs no network/backend invocation, human approval, or
candidate adoption. The installed `maliang-art` / `python -m maliang_art` CLI has
no `production` subcommand. The repository sample instead provides
`python -I examples/art-pilot/scripts/production.py --help` for prepare,
complete/fail, import, derive, technical review, human review, and adoption.
Its global `--project` precedes the subcommand; input paths are relative to that
project root. With the source installed, run the complete synthetic offline
exercise from the repository root:

```console
python -I examples/art-pilot/scripts/offline_demo.py --project work/art-pilot/synthetic-demo-001
```

This creates a separate ignored project and prints `synthetic-adopted`, never
real provider execution or human approval. Existing output directories are
refused; choose a new suffix for another run. The [runbook](examples/art-pilot/docs/runbook.md)
explains artifacts and separates this practice loop from real-project templates.
Actual generation/editing remains an external host step: no automatic Codex
provider bridge is delivered, and synthetic human fixtures are not real approval.

## Python API

```python
from maliang_art import canonical_bytes, stable_id, write_immutable_json
from maliang_art.records import validate_artifact
from maliang_art.workflow import validate_invocation, validate_delivery, validate_failure
```

The pure review API is available from `maliang_art.review`; structural ports are
in `maliang_art.ports`, with JSON/Pillow adapters in `maliang_art.adapters`.
Versioned JSON Schemas are shipped under `schemas/v1/`.

## State machine core

`maliang_art.statemachine` loads a YAML policy (states, transitions, optional
steps, project-level policy values) and evaluates transitions in memory.
`StateMachine.apply` returns a transition record and does not publish it to
disk; built-in image steps may still write the image paths they are given.
The shipped default template is `draft → review → done/rejected` with an
empty approver list that projects must fill in.

```console
maliang-art flow show-default-template
maliang-art flow validate path/to/policy.yaml
maliang-art flow transitions path/to/policy.yaml --state draft
```

```python
from maliang_art.statemachine import load_policy, StateMachine
```

Projects supply YAML policy and reviewer values; the library does not hard-code
project identity, canvas sizes, or approvers.

The policy schema uses the stable identifier `urn:maliang:schema:state-machine-policy:v1`;
its source is `schemas/v1/state-machine-policy.schema.json`, not a v0.1.0 tag resource.

## Safety and scope

Art-pilot machine-local locks (`examples/art-pilot/maliang.lock.json`), production
records (`examples/art-pilot/production/`), and scratch outputs (`work/art-pilot/`)
are ignored by Git. Ignore rules do not remove already tracked files and do not
replace a publication/privacy review.

- Paths in records are repository-relative POSIX paths.
- SHA-256 fields bind bytes; they do not establish authorship or licensing.
- Publication uses a temporary file plus a create-if-absent hard link, making
  concurrent identical publishers safe and conflicting publishers fail closed.
- Behavior tests use synthetic fixtures. A separate integrity/provenance test
  verifies the attributed `examples/poet-cast/` tutorial and its six hash-bound
  source-project files.

Code and the Python distribution are MIT licensed. The repository-only
`examples/poet-cast/` tutorial is excluded from the sdist and remains CC BY 4.0;
see its `ATTRIBUTION.md`, `assets.json`, `REUSE.toml`, and
`LICENSES/CC-BY-4.0.txt`.
