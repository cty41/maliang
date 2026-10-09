# MaLiang

**Turn visual intent into auditable game art.**

MaLiang is a small, provider-neutral Python toolkit for deterministic game-art
workflow records. The distribution is **`maliang-game-art`**, the import package
is **`maliang_art`**, and the command is **`maliang-art`**.

Version 0.1 focuses on safe records rather than asset generation: canonical JSON
identities, collision-safe immutable publication, path containment, synthetic
pose-proof rendering, artifact bindings, review-policy validation, and neutral
invocation/delivery/failure envelopes.

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
maliang-art flow show-default-template
maliang-art flow validate path/to/policy.yaml
maliang-art flow transitions path/to/policy.yaml --state draft
```

Pose canvases are record-defined; previews default to half the canvas dimensions
or accept `--preview-size WIDTHxHEIGHT`. Board and preview allocations are
bounded to prevent oversized valid records from exhausting memory.
`pose select-option` requires an explicit reviewer but never assumes a particular
person. Every unselected option needs one reason. Existing output bytes are
immutable: repeating identical work succeeds, while different content at the
same path fails.

## Offline design CLI (source checkout)

The new design entry is not part of the v0.1.0 tag above. In a checkout containing
it, install with `python -m pip install .` and provide the explicit JSON records
defined by `schemas/v1/art-family-contract.schema.json` and
`schemas/v1/sprite-slice-draft.schema.json`:

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
There is no network/backend invocation, automatic human approval, candidate
adoption, or production CLI; generation and exact-image human decisions remain
separate project steps.

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

## Safety and scope

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
