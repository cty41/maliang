# MaLiang usage reference

[English](usage.md) | [简体中文](usage.zh-CN.md) | [Quick start](../README.md)

This is the reference for the library and CLI: versions, commands, output
semantics, and safety. New here? Start with [getting started](getting-started.md)
and [concepts](concepts.md); connect an Agent with [Agent setup](agent-setup.md).
The [art-pilot sample](../examples/art-pilot/README.en.md) and its
[runbook](../examples/art-pilot/docs/runbook.en.md) own the real-project workflow;
the offline exercise is not evidence of provider execution or approval.

## Installation and versions

Use **Python 3.10+**. The distribution is **`maliang-game-art`**, the import package
is **`maliang_art`**, and the command is **`maliang-art`**. The unrelated PyPI project
named `maliang` is not this toolkit. Pillow is supported in the `>=10.4,<13` range.

For current features and repository examples, follow the single source-install
route in the [quick start](../README.md#quick-start). Run this guide's
commands from the repository root with that environment active. Dependency
installation may access the network; design compilation and the demo do not.

The released v0.1.0 tag provides stable JSON encoding and IDs, path containment,
collision-safe immutable publication, synthetic pose-proof rendering, artifact
bindings, review-policy validation, and provider-neutral invocation, delivery,
and failure records. It focuses on safe records, not generating assets.
For deliberately reproducing that older release, its install command is:

```console
python -m pip install "maliang-game-art @ git+https://github.com/cty41/maliang.git@v0.1.0"
```

**Do not use that older install for this guide's current-source walkthrough.**
The `design` and `flow` commands below are current-source features, not part of
v0.1.0; documenting them does not imply a new release. The preview sizing below
also describes current source.

Repository-relative guides and the [Agent skill](../skills/maliang-art/SKILL.md)
need a source checkout. The wheel does not include them; the sdist omits the skill
and runbook. A host decides how to load/install the skill: a link neither installs
it nor grants image-tool access. Design specs record decisions and pending work,
not executable APIs. Use [llms.txt](../llms.txt) for the document map and
[CONTRIBUTING.md](../CONTRIBUTING.md) / [AGENTS.md](../AGENTS.md) for development.

## Agent and LLM setup

**MaLiang has no model-service or API-key configuration.** Models, image tools,
and login belong to your host. The step-by-step checklist (checkout path,
interpreter, asset root, tool inspection, and review gates) is in
[Agent setup](agent-setup.md).

## Offline practice and real projects

After source installation, the [quick start](../README.md#quick-start)
runs `examples/art-pilot/scripts/offline_demo.py` in a new, ignored project under
`work/art-pilot/`. It exits 0 and prints `synthetic-adopted` on success. Existing
directories, even empty ones, are refused; choose a new suffix for another run.
Its synthetic image and human-decision fixture are **not real provider execution
or human approval**.

The installed `maliang-art` / `python -m maliang_art` CLI has **no `production`
subcommand**. The repository sample instead provides:

```console
python -I examples/art-pilot/scripts/production.py --help
```

It supports preparation (`prepare`), completion/failure (`complete`/`fail`),
import, derivation (`derive`), technical review (`technical`), human review
(`review`), and adoption (`adopt`). Global `--project` precedes the subcommand;
input paths are relative to that project root. Follow the
[runbook](../examples/art-pilot/docs/runbook.en.md) for artifacts and real-project
templates rather than treating the synthetic exercise as a production tutorial.
Actual generation/editing remains an external host step. No automatic Codex
provider bridge is delivered, and synthetic human fixtures are not real approval.

## Design validation and compilation

The checked-in sample can be validated and compiled without writing your own JSON:

```console
python -m maliang_art design validate --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json
python -m maliang_art design compile --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json --output-dir work/art-pilot/readme-design
```

Both commands exit 0 on success. Compile prints a manifest containing
`"packet": "design.json"` and `"guides": []`. The output under ignored
`work/art-pilot/` is an execution brief, not a generated or approved character
image. Use a new output directory when changing the inputs.

For your own design, provide explicit JSON records following
[art-family-contract.schema.json](../schemas/v1/art-family-contract.schema.json)
and [sprite-slice-draft.schema.json](../schemas/v1/sprite-slice-draft.schema.json):

```console
maliang-art design validate --contract family.json --draft slice.json
maliang-art design compile --contract family.json --draft slice.json --output-dir work/design-v1
```

`validate` writes JSON `{ "valid": true, "diagnostics": [] }` on success (exit 0).
Invalid/incomplete records, missing files, and malformed JSON produce exit 1 and
JSON diagnostics with `path`, `code`, and `message`; it does not guess missing
art decisions. `compile` uses the same visual validation and publishes `design.json`
with a complete prompt, view/state tasks, inherited target sizes, ordered reference
roles/hashes, pending acceptance requirements, and context-board layout.

By default it renders no images: `imageInputs` contains only declared references
in their original order. Family `variants` and numeric part coordinates are not
required; topology parts can describe species structure with `id` and optional
`description`. Visual shape intentions must be allowed by the family, not by the
debug renderer. The supported camera profile is explicit isometric DR/UL with
project-accepted mirror-derived directions. This prepares an execution brief,
not an approved design.

Palette and artistic judgments remain pending human review; context boards are
layouts, not future candidate images. Reference paths/hashes and borrowing roles
are **declarations only**: this command neither reads/verifies nor copies reference
images. Empty references support from-scratch exploration. Backend parameters and
actual image-input submission remain unverified until bound by an execution
adapter. The design command performs no network/backend invocation, human
approval, or candidate adoption.

### Optional debug geometry

The existing capsule/ball renderer is available only as an optional debug mode:

```console
maliang-art design compile --contract family.json --draft slice.json --output-dir work/debug-v1 --debug-geometry
```

This mode requires explicit numeric variants and part anchor/size pairs, validates
layout bounds, and additionally publishes `guides/*.png`. These artifacts are
labeled **debug-layout**, **unapproved**, **not-generation-input** and never enter
`imageInputs`. Ellipsoid placeholders and screen-direction triangles show code
layout only. They do not prove species, silhouette design, DR/UL projection,
action pose, style, core measurements, or cross-view/state consistency. Their
coordinates do not become generation instructions. No debug layout needs to be
selected or approved before visual exploration.

### Output and reruns

Success prints a JSON file manifest; publication/path errors fail nonzero on
stderr. Identical reruns keep existing bytes; different bytes at an existing
file are rejected. Publication is immutable per file, **not a multi-file
transaction**: an interrupted/failed debug run may leave guides, and an identical
rerun can finish it. Use a new output directory for a changed brief or debug mode.
Unlike the demo, which refuses any existing project directory, compilation can
finish identical work in its existing output directory.

## Pose, records, and review CLI

These commands use record files you supply, except for the checked-in poet-cast
example. The selection command is on one line for use in Windows PowerShell.

```console
maliang-art pose render-options --spec draft.json --output board.png --preview-dir previews --preview-size 160x90
maliang-art pose select-option --spec draft.json --option-id arc-a --output-card card.json --reviewer art-director --reason "Readable silhouette" --rejected-reason "arc-b=Weaker contact" --selected-at 2026-01-01T12:00:00Z
maliang-art records validate draft.json --schema pose-draft
maliang-art records validate invocation.json --schema invocation
maliang-art records validate delivery.json --schema delivery --root . --verify
maliang-art records validate examples/poet-cast/draft.json --schema pose-draft
maliang-art records check path/to/record-tree
maliang-art review validate rule review-rule.json --authority-reviewer art-director
```

Pose canvases are record-defined. In current source, `render_preview` and the CLI
use half the canvas dimensions by default, reduced proportionally (rounded down)
when needed to fit the **4,194,304-pixel budget**. The complete canvas is fitted,
not cropped; a 256×256 canvas still defaults to 128×128. Explicit
`--preview-size WIDTHxHEIGHT` values over that budget are rejected. Board and
preview allocations are bounded to prevent oversized records exhausting memory.

`pose select-option` requires an explicit reviewer but never assumes a particular
person. Every unselected option needs one reason. Existing output bytes are
immutable: repeating identical work succeeds, while different content at the
same path fails.

## Python API

```python
from maliang_art import canonical_bytes, stable_id, write_immutable_json
from maliang_art.records import validate_artifact
from maliang_art.workflow import validate_invocation, validate_delivery, validate_failure
```

The pure review API is available from `maliang_art.review`; structural ports
(interfaces) are in `maliang_art.ports`, with JSON/Pillow adapters in
`maliang_art.adapters`. Versioned JSON Schemas are shipped under `schemas/v1/`.

## State machine

`maliang_art.statemachine` loads a YAML policy describing states, transitions,
optional steps, and project-level policy values, then evaluates transitions in
memory. `StateMachine.apply` returns a transition record and **does not publish
it to disk**; built-in image steps may still write or overwrite the image paths
they are given. If a later step fails, earlier image writes are not rolled back.
The shipped default template is `draft → review → done/rejected`, with an empty
approver list that projects must fill in.

```console
maliang-art flow show-default-template
maliang-art flow validate path/to/policy.yaml
maliang-art flow transitions path/to/policy.yaml --state draft
```

```python
from maliang_art.statemachine import load_policy, StateMachine
```

Projects supply YAML policy and reviewer values; the library does not hard-code
project identity, canvas sizes, or approvers. The policy schema uses the stable
identifier `urn:maliang:schema:state-machine-policy:v1`. Its source is
[state-machine-policy.schema.json](../schemas/v1/state-machine-policy.schema.json),
not a resource in the v0.1.0 tag.

## Safety and scope

Read [SECURITY.md](../SECURITY.md) for the filesystem threat model and private
vulnerability reporting. Use a caller-controlled root protected from untrusted
writers. Portable path checks cannot eliminate races if an attacker can rename
or rewrite directories during I/O. Never put secrets in persistent invocation
`request`, delivery `metadata`, or failure `details`; adapters must redact them.

Art-pilot machine-local locks (`examples/art-pilot/maliang.lock.json`), production
records (`examples/art-pilot/production/`), and scratch outputs (`work/art-pilot/`)
are ignored by Git. Ignore rules do not remove already tracked files and do not
replace a publication/privacy review.

- Paths in records are repository-relative POSIX paths.
- SHA-256 fields bind bytes; they do not establish trust, authorship, or licensing.
- Publication uses a temporary file plus a create-if-absent hard link, making
  concurrent identical publishers safe and conflicting publishers fail closed.
  See the security policy for hard-link rejection, bounded cleanup waits, and
  cases where an error can leave an already-created target in place.
- Behavior tests use synthetic fixtures. A separate integrity/provenance test
  verifies the attributed `examples/poet-cast/` tutorial and its six hash-bound
  source-project files. These checks do not prove real generation or approval.

Code and the Python distribution are MIT licensed. The repository-only
`examples/poet-cast/` tutorial is excluded from the sdist and remains CC BY 4.0;
see its [ATTRIBUTION.md](../examples/poet-cast/ATTRIBUTION.md),
[assets.json](../examples/poet-cast/assets.json), [REUSE.toml](../REUSE.toml), and
[CC-BY-4.0.txt](../LICENSES/CC-BY-4.0.txt). See also
[EXTRACTED_FROM.md](../EXTRACTED_FROM.md) for project origins.
