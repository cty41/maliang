# Art Pilot

[English](README.en.md) | [简体中文](README.md)

Visual exploration examples and production-gate regression coverage in the MaLiang repository. Library code, scripts, and documentation use MIT; user-owned curated images use CC-BY-4.0, with sources and attribution in the asset manifests. Image display, user preference, technical checks, and formal production adoption are separate facts; none substitutes for another.

## Execution boundaries

These operating instructions cover Windows PowerShell only; the local usage-validation environment is Windows 11 x64. Prepare an environment following the [development setup](../../CONTRIBUTING.md#development-environment), then run commands from the repository root with the Python environment where the current MaLiang checkout is installed:

```powershell
python -m pip install ".[test]"
python -m pytest tests examples/art-pilot/tests
```

CI is configured for GitHub-hosted Windows Server x64 (`windows-2025`), not Windows 11. Local success does not prove hosted CI success, and an unpushed workflow change has no new hosted-run result. This scope does not remove portable script branches or invalidate historical cross-platform CI results.

No sample-specific `.venv`, external source directory, Codex login, or image service is required. Do not substitute `PYTHONPATH`, an editable install, or `sys.path` injection for isolated-install verification. An existing prepared environment can run the tests without reinstalling.

Synthetic regressions create PNGs, mock receipts, and human-decision fixtures in temporary directories. They cover frozen inputs, complete acceptance requirements, two versions, edits/derivations, imports/failures, mismatched old evidence, rejection of missing technical/human items, and adoption projections. Test approvals are not production approval.

## Current entry points and gates

- `scripts/production.py`: prepare → **actual external execution** → complete / fail; also import, derive, technical, review, and adopt.
- prepare, import, and acceptance require authoritative `--contract --draft --design` inputs. They recompile and compare execution fields; removing or editing packet fields cannot bypass requirements.
- Requests freeze the full prompt, task, parameters, input-image hashes and order, and the original contract / Draft bytes. There is no bypass through hand-entered `--required-*` or `--decide approve`.
- Unknown acceptance methods, duplicate IDs, and missing identity items are errors. Technical results cannot replace human judgments of style, identity, or pose.
- Events and artifacts cannot be overwritten; evidence for an old candidate cannot be used for a new one. Adoption updates only the current projection.
- The public sample does not provide the old `record_generation.py`, `run_flow.py`, or `review_check.py`. Regression checks verify that the actual entry points reject old approval shortcuts; they do not execute nonexistent files.

Agents must not claim to be human or fabricate real approval evidence. Neither the library nor the scripts implement a Codex provider execution bridge yet.

## Curated images and history

The shared style reference is `characters/shared/poet-idle-dr-style.png`; the selected peregrine falcon is `characters/falcon-idle/raw/codex-idle.png`. Consult the asset manifests for the crested goshawk and for each image's hash, compression settings, and attribution. These are repository showcase materials, not prerequisites for offline regression tests.

Old V03 receipts cannot prove that image references were actually submitted or that the actual prompt matched the frozen packet; do not reuse them as production evidence for current assets. V04 and external Codex trials describe only evidenced inputs, outputs, and user feedback; do not fabricate an execution chain. Quantized derivatives have new bytes and hashes and cannot inherit the original image's immutable approval / delivery.

## Distribution and installation verification

The wheel excludes art-pilot. The sdist retains the Chinese `README.md`, scripts, and synthetic tests; it excludes this English README, real characters, production records, machine-local locks, policy, and historical docs. Thus neither the real-image showcase nor the runbook is available in the sdist. Real-asset integrity checks belong to repository verification, not distribution-install prerequisites.

Maintainers build with `python -m build` (by default, an sdist first, then a wheel from that sdist). Then use the actual artifact path:

```powershell
python examples/art-pilot/scripts/smoke_wheel.py --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl
```

The smoke check uses the current `sys.executable` to create a temporary isolated environment, installs the specified wheel and dependencies, imports with `-I` from a temporary directory, verifies all package-resource hashes, schemas, and templates, runs CLI help, and finally removes the environment. For offline use, add `--wheelhouse <existing-dependency-wheel-directory>`; without it, pip may download dependencies from the configured index.

Machine-local locks are not distributed with the public sample. Generate your own when exact source/wheel verification is needed; the author's installation paths are not a public lock. The repository [runbook](docs/runbook.en.md), paired with its Chinese version, is the authoritative production workflow and evidence-boundary reference.
