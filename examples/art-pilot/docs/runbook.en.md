# Runbook — Frozen requests and exact-candidate gates

[English](runbook.en.md) | [简体中文](runbook.md)

This runbook and its Chinese counterpart are the authoritative production workflow. Run all commands from the MaLiang repository root; `python` means the interpreter in the current environment. No particular drive, username, or external checkout is required. The production commands below are operational templates, not claims of completed real calls. Prepare your own lawful inputs first and use fresh attempt IDs and output paths; do not modify curated images or backfill historical receipts.

## 0. Environment and reproducibility scope

These operating instructions cover Windows PowerShell only; the local usage-validation environment is Windows 11 x64. For first use, create and activate an environment following the [development setup](../../../CONTRIBUTING.md#development-environment).

CI is configured for GitHub-hosted Windows Server x64 (`windows-2025`), not Windows 11. Local success does not prove hosted CI success, and an unpushed workflow change has no new hosted-run result. This scope does not invalidate historical cross-platform CI results.

```powershell
python -m pip install ".[test]"
python -m pytest tests examples/art-pilot/tests
python -m build
python examples/art-pilot/scripts/smoke_wheel.py --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl
```

By default, build creates the wheel from the sdist. The smoke check uses `sys.executable` to create a temporary environment, selects `Scripts/python.exe` on Windows, installs the wheel, and verifies all packaged resources. It neither reads historical local locks nor imports working-tree source. The script retains a portable branch selecting `bin/python` on other platforms; this is an implementation fact, not a Unix operating route provided or validated in this scope. Pass `--wheelhouse <existing-directory>` to prohibit index access. Without it, dependency installation may download from the network; it does not upload anything.

For a persistent sample-specific environment, prepare a dependency wheelhouse first, then run the exact source/wheel verification tool. Paths below are relative to the repository root; `.wheelhouse` is a local directory you prepare:

```powershell
python examples/art-pilot/scripts/lock_environment.py --source-repo . --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse .wheelhouse --dry-run
python examples/art-pilot/scripts/lock_environment.py --source-repo . --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl --wheelhouse .wheelhouse
```

Dry-run only checks and prints; it does not create an environment, install anything, or write a lock. A real run creates the sample's local `.venv` and `maliang.lock.json`; commit neither. The tool reuses an existing environment but still verifies every installed resource; stale wheels are rejected by default. `--record-existing-test-install` can only record differences in an existing test installation, not certify production readiness. The lock records the observed commit/dirty state and actual bytes, not an invented historical build time.

The sdist includes only art-pilot scripts, synthetic tests, and the Chinese `README.md`; it excludes the English README, both runbooks, real images, production history, local locks, and policy. Real-asset hash/source audits belong to repository checks; all behavioral regressions use temporary synthetic fixtures.

## 0.0 Art direction intake (for broad requests)

When the request is a single line such as "a cute animal tactics game", run an intake before writing any draft.

1. The agent restates its understanding in one or two sentences, then runs `python -m maliang_art intake start <catalog> <intake.json> --request "<user's words>"`. The sample catalog is `intake/art-direction-catalog.json`.
2. Repeat `intake next <catalog> <intake.json>`, ask the returned questions with the question tool, and record each reply with `intake answer` until the result is done.
3. A stop option, such as 3D, ends the intake with a reason; do not continue past it.
4. Finish with `intake draft` to get draft style-guide and family-contract fields plus the dimensions still open. Then continue with Section 1, or with the concept track in Section 0.2.

The catalog is project data and can be edited freely. The agent may add suggestions only on dimensions marked suggestable and must label them as AI suggestions; answers prefilled from the user's words need the user's confirmation; the agent never answers for the user.

## 0.1 Run a complete synthetic offline exercise with one command

Prerequisite: install the current source and dependencies as above and use that environment's Python. The exercise itself does not access the network or call an image-generation service, and needs no images, login, or external credentials. Run from the repository root:

```powershell
python -I examples/art-pilot/scripts/offline_demo.py --project work/art-pilot/synthetic-demo-001
```

The script prepares a minimal contract/Draft in a separate Git-ignored project directory, compiles the design, calls prepare through the existing production CLI, creates a 16×16 synthetic color block with Pillow and binds a mock receipt, then runs technical checks, a synthetic human fixture, and adopt. It does not import fixtures from test modules or read or modify curated images. The first successful run exits 0 and prints JSON to stdout: `status` is `synthetic-adopted`, `synthetic` is true, `realProviderExecution` and `realHumanApproval` are both false, and `project` is the actual absolute path.

The output directory contains:

- `contract.json`, `draft.json`, `design.json`, `parameters.json`: inspectable execution inputs; no reference images or debug guides.
- `synthetic-image.png`, `synthetic-receipt.json`, `synthetic-human.json`: explicitly labeled test material, receipt, and human-review fixture.
- `production/attempts/synthetic-001/`, `production/events/`, `production/technical/`: records produced by the existing gates.
- `production/current/synthetic-demo.json`: an adopted projection only within the synthetic project.
- `synthetic-demo.json`, `demo-result.json`: synthetic-boundary declarations and artifact-path inventories.

**This is not real image generation, artistic acceptance, or human approval.** `actorType: human` and pass values only exercise the existing review protocol. The reviewer is explicitly `synthetic-fixture-human`, and the statement explicitly says no person reviewed the image. Do not copy these fixtures into real projects or treat them as real people's decisions. The color block need not satisfy bird-art requirements; pass values for artistic items are mock data, not visual judgments made by the tool.

The target path must not exist, even as an empty directory. A repeated run exits nonzero and does not overwrite existing files. Use a new path such as `work/art-pilot/synthetic-demo-002` for another exercise. An interrupted run may leave partial records; rerun in a new directory rather than deleting or overwriting old evidence. Sections 1–4 below are **real-project operational templates** requiring real inputs, execution evidence, and human decisions. Synthetic approvals above cannot replace them.

## 0.2 Concept art first (optional)

When concept art and in-game assets differ strongly in style, for example ink concept art and capsule sprites, run the concept track first:

1. Write a `concept-style-guide`, then one `character-concept` per form, starting as pending with a null image.
2. Generate concept art only after the user separately authorizes it. Run `python -m maliang_art concept review <records-directory> --concept <id> --format questions` to print three review questions (style checks, multi-select; identity markers, multi-select; conclusion, single-select) and hand them to the question tool. Without a question tool, drop `--format questions` to print the Markdown review sheet and paste it into the conversation verbatim. Identity markers list only those whose `forms` include the current form. A "needs revision" conclusion is recorded as rejected with the unmet items in `--note`. Only after the user answers may the agent run `python -m maliang_art concept approve <concept.json> --decision approved --image <image-path> --root <project-root>`. The reviewer is taken from git user.name and user.email, falling back to the OS login name, and the source is recorded in the `reviewerSource` field. Without an explicit reply from the user, do not run approve.
3. Extract `identity-markers` from the approved concepts and freeze them; every marker states its `capsuleTranslation`. Start with an `art-reading` that binds the source image path and hash: items the host model saw are `host-model-observed`, and only items the user confirmed become `human-confirmed`. Mark the reading confirmed once every identity item is user-confirmed, draft the markers with `reading_to_markers`, and cite the reading in `readingIds`. External references (photos, screenshots of others' work) may only be `style-only` readings: borrow style, never identity.
4. Build the Section 1 draft `identity` from the markers. Do not feed concept art to capsule generation as a reference image.
5. Record portrait busts and promo uses as `derived-usage`; they also need human approval.

Check the records with `python -m maliang_art records check <records-directory>`. The synthetic `characters/concept-demo` example (a sample heron with two forms) honestly stops at "waiting for human concept approval".

## 1. Prepare authoritative inputs

Prepare `family-contract.json`, `draft.json`, and `backend-params.json` in your own project directory. Use the installed library's `python -m maliang_art design compile --help` to inspect compilation arguments, and write a fresh `packet/design.json`. Arbitrary prompt text is not a compiled prompt.

All production source arguments are relative to the `--project` root, not to design.json. Absolute paths and `..` escapes are rejected. The examples use a project root you prepare at `work/art-pilot`; they do not assume that directory or its files already exist.

If using curated examples, the repository reference is `characters/shared/poet-idle-dr-style.png` and the final peregrine falcon is `characters/falcon-idle/raw/codex-idle.png` (relative to `examples/art-pilot`). First verify current derivative hashes against the asset manifests, then copy lawful references into your own project. The Draft must contain actual project-relative paths and current byte hashes, not pre-compression references. Specify each reference's role and what may and may not be borrowed.

## 2. prepare / acceptance

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot prepare --attempt bird-001 --contract family-contract.json --draft draft.json --design packet/design.json --parameters backend-params.json --provider actual-provider --model unknown --character bird
python -I examples/art-pilot/scripts/production.py --project work/art-pilot acceptance --contract family-contract.json --draft draft.json --design packet/design.json
```

prepare recompiles the contract / Draft and checks the prompt, tasks, input order/roles, acceptance, designId, and targets; it freezes input images and authoritative source bytes. Unknown methods, duplicate IDs, and missing identity items are errors. `alpha-bounds` maps to automatic acceptance; human items require decisions by real humans. There is no hand-entered required or approve switch.

Edits still require their own editing-task contract / Draft / design, plus `--parent <exact-parent-attempt>` and `--instruction <specific-change>`. The parent image is the first edit-source, followed by references in their original order. Edit records do not pretend to be original generation.

## 3. External execution and completion

Neither the library nor the scripts automatically call image services. The executor must read `production/attempts/<id>/prepared.json`, actually submit the frozen prompt, parameters, and input images, and retain verifiable tool records. The Codex provider execution bridge remains unimplemented; login is not a prerequisite for offline regressions.

`--character` is required. A character's first prepare writes the immutable `production/host-locks/<character>.json`; every later prepare for that character must use the same `--provider` and `--model`; `--parent` must belong to the same character and generation host; derive inherits the parent's character. There is no force-switch flag: start a new character to change hosts.

### Cursor execution (semi-automatic)

After preparing with `--provider cursor-desktop` (the parameters file may only contain `aspect_ratio`: 1:1, 4:3, 3:4, 16:9, 9:16), run `cursor-packet --attempt <id>` and pass the printed `call` unchanged to Cursor GenerateImage; never retype the prompt. After the user authorizes and the image is generated, run `cursor-complete --attempt <id> --output <tool-reported path>`; on failure run `cursor-fail --attempt <id> --message <reason>`. The receipt is `host-agent-attested`: MaLiang cannot invoke Cursor tools and does not read Cursor transcripts, so model and billing stay unknown.

A successful receipt must contain: `preparedEventId` (unchanged), `invocation` (the complete object, not a string), `outcome: "success"`, the actual `artifactSha256`, and real `executionEvidence`.

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot complete --attempt bird-001 --receipt receipt.json --image output.png
```

For failure, use `fail --attempt bird-001 --category timeout --message <actual-error-summary>`; do not fabricate a successful image from a failed call. complete exactly matches the prepared event, full invocation, and output hash, but a hand-assembled receipt alone does not prove real execution.

For an existing external image, use `import --attempt <new-id> --contract ... --draft ... --design ... --image ... --provenance <actual-source> [--historical]`; do not fabricate an invocation, historical timestamp, or approval. The core may store original bytes as `source.bin`; this does not change the image content, but these production records are not part of the public curated assets or distribution packages.

Old V03 receipts are untrustworthy: image references were not actually submitted, and the actual prompt differed from the frozen packet. They cannot serve as executable templates. V04 / external Codex trials retain only provable facts and user feedback, not a fabricated complete chain. Showcase preferences do not mean a newly compressed derivative satisfies production-adoption requirements.

## 4. Technical checks, human review, and adoption

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot technical --attempt bird-001
python -I examples/art-pilot/scripts/production.py --project work/art-pilot review --attempt bird-001 --decision-file human-decision.json
```

technical decodes the actual image, runs every required automatic predicate, and binds results to the exact candidate. Passing dimensions, nonempty alpha, and bounds checks does not prove artistic quality. derive supports copy / flip-x / matte-resize and binds the parent candidate; it is not native-view image generation or implicit approval of a handedness change.

matte-resize is deterministic post-processing, not regeneration. The parent size must equal the frozen `sourceSize`. It flood-fills from all four canvas edges and makes only edge-connected pixels within tolerance of the key color transparent, so similar interior colors stay opaque. It then scales by `outputSize / sourceSize` with LANCZOS, aligns the subject bottom to `groundY` and its horizontal center to `anchorX`, and writes PNG. The key color defaults to the corner median; set `--key-color #RRGGBB` explicitly if needed; `--tolerance` defaults to 24. An empty matte, a subject touching the source edge, or placement outside the output canvas fails without creating an attempt. It suits flat backgrounds only; complex backgrounds should fail rather than be forced. The derived record keeps every parameter. The derived image is a new candidate and needs its own technical run and real human review; the parent's review cannot be reused.

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot derive --attempt bird-001-sprite --parent bird-001 --operation matte-resize
```

The human decision-file must originate from a real decision: `actorType: "human"`, a real reviewer, the candidate's complete eventId/attemptId/artifact, `identityChecklist: ["identity"]`, a nonempty genuine statement, a real timezone-aware decidedAt, adopt/reject/pending, and pass/fail/pending/unsupported for every required human item. Agents must not fabricate real human pass values to advance the workflow.

Adoption command template (replace angle-bracket placeholders with actual event paths; do not run verbatim):

```powershell
python -I examples/art-pilot/scripts/production.py --project work/art-pilot adopt --attempt bird-001 --asset bird-idle --review production/events/<human-event>.json --result production/events/<automatic-event>.json
```

Each required automatic item needs a `--result`. Missing items, failures, pending/unsupported values, old human reviews, or technical results bound to another candidate are rejected. Once all gates are satisfied, adoption can proceed without regenerating the image. Events cannot be overwritten; the current projection is updated atomically.

## Verification boundaries

Synthetic tests verify behavioral gates, not whether a service received real reference images or whether geometry/visual quality is acceptable; they cannot replace real human adoption. Images are user-owned CC-BY-4.0 assets; the library, code, and documentation use MIT. Authorization to publish, user preference, and formal delivery are recorded separately. None of these commands implies a push, upload, PR, or merge.
