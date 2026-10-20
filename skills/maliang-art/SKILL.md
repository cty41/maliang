---
name: maliang-art
description: "Use when the user explicitly asks to use MaLiang / 马良 to prepare, make, edit, or review game-art assets. Validate and freeze a brief, coordinate authorized host image tools, and gate adoption on exact-candidate technical and real human review. Do not use for developing MaLiang, general art discussion, or unrelated image requests."
---

# Make game art with MaLiang

## Important

This is a usage skill, not development guidance or an image tool. MaLiang provides
deterministic local preparation and review records; the host provides image
generation/editing, image display, and authorization. Never infer those capabilities
from this skill, a provider preference, a subscription, or a login.

## Quick Reference

| Need | Entry point |
| --- | --- |
| Quick start | `README.md` (English) / `README.zh-CN.md` (中文) in the configured checkout |
| Detailed usage and version choices | `docs/usage.md` (English) / `docs/usage.zh-CN.md` (中文) |
| Agent setup checklist | `docs/agent-setup.md` (English) / `docs/agent-setup.zh-CN.md` (中文) |
| Executable workflow and receipt/decision formats | `examples/art-pilot/docs/runbook.en.md` (English) / `examples/art-pilot/docs/runbook.md` (中文) |
| Offline synthetic demonstration and sample scope | `examples/art-pilot/README.en.md` (English) / `examples/art-pilot/README.md` (中文) |
| Validate / compile a brief | `python -m maliang_art design validate` / `design compile` |
| Freeze / bind / review / adopt | `python -I examples/art-pilot/scripts/production.py --project work/art-pilot` plus the runbook subcommand |

These are repository-root paths, not paths relative to this installed skill.

## When to use

- “Use MaLiang to explore a new game character” → capture intent, compile and prepare
  a generation brief, then use an authorized host tool if available.
- “用马良修改这张角色图，保持身份” → preserve the source and references, prepare an
  edit with a precise parent and instruction, then review the new candidate.
- “Review this MaLiang candidate for adoption” → display the exact image, check its
  technical results, obtain a real human decision, and apply the adoption gates.

Do not trigger for “fix MaLiang's compiler”: use the checkout's development guidance
instead, with no generation. Ordinary art discussion and unrelated image requests
also do not activate this workflow.

## Workflow

### 1. Locate the checkout and environment

Require an explicit **MaLiang project root**: the absolute source-checkout path
provided by the user or configured in the host's project context. If missing, ask
for it; do not guess from the skill installation directory or current directory.
Verify that root contains `pyproject.toml`, `src/maliang_art`, and the runbook above.
Read its README installation/version guidance and the runbook before operating.
Set the command working directory to that verified root using the host's supported
working-directory mechanism. No environment-variable name is assumed.

Separately agree the **asset project root**, passed explicitly as `--project`
**before** the sample subcommand. The examples below use the ignored
`work/art-pilot` under the checkout; they require user-prepared inputs there and
are templates, not a claim those files exist. Source, receipt, image, and decision
paths for the sample are relative to that asset project root. Never overwrite
source images, existing attempts, or approved records; use new output paths/IDs.

Use the project's selected Python environment with current source installed.
`design` and `flow` are current-source features, not the v0.1.0 release tag.
Check the available interface without contacting an image service:

```text
python -m maliang_art design validate --help
python -m maliang_art design compile --help
python -I examples/art-pilot/scripts/production.py --help
```

If imports or commands are missing, stop and follow the README environment setup
with permission; do not inject source paths to disguise an incompatible install.
The wheel does not contain the sample or this skill. The sdist omits the skill and
runbook; use a source checkout for these repository-relative resources.

### 2. Capture intent and choose a real execution path

Gather target asset, views/states, canvas/output constraints, identity invariants,
allowed changes, family contract, Draft, backend parameters, reference roles and
borrowing limits, output location, and the human reviewer. Do not invent missing
art decisions. From-scratch exploration may have **empty references**: recommend
style references where useful, but require neither an existing character image
nor a model sheet. Geometry blockout is not a mandatory design stage.

Inspect the tools actually exposed in this host and their argument schemas:
can they generate, edit, attach actual image bytes/files in order, preserve the
full prompt and parameters, return an output artifact, and display that artifact?
Confirm permission before any external call. An image path in prompt text is not
an image attachment. If required image inputs cannot be submitted, **stop at
preparation**, report the missing capability, and do not switch to text-only.

The automated Codex provider bridge is **planned, not implemented**. A manually
tested MiMo-to-Codex route is a separate host operation, not a MaLiang command or
a guarantee of availability here. Verify this session's actual tools and permissions.
Never read subscription tokens or use an API fallback to bypass unavailable host
tools. Unknown model, billing, or reference-delivery facts remain `unknown` or
explicitly `attested`; never promote assertions into observed evidence.

### 3. Validate, compile, and freeze

Use the runbook as the sole detailed command/record reference. For the agreed
asset project, the initial local sequence is:

```text
python -m maliang_art design validate --contract work/art-pilot/family-contract.json --draft work/art-pilot/draft.json
python -m maliang_art design compile --contract work/art-pilot/family-contract.json --draft work/art-pilot/draft.json --output-dir work/art-pilot/packet
python -I examples/art-pilot/scripts/production.py --project work/art-pilot prepare --attempt bird-001 --contract family-contract.json --draft draft.json --design packet/design.json --parameters backend-params.json --provider actual-provider --model unknown --character bird
python -I examples/art-pilot/scripts/production.py --project work/art-pilot acceptance --contract family-contract.json --draft draft.json --design packet/design.json
```

`--character` pins the character to one provider and model for its whole
lifecycle; never switch hosts mid-character. With `cursor-desktop`, always use
`cursor-packet` output as the GenerateImage call (do not transcribe the prompt),
then `cursor-complete --output` or `cursor-fail --message`.
Replace `actual-provider` with the selected real provider before preparing; an
unavailable executor remains a blocker, not permission to manufacture a provider.
Validation success is exit 0 with `valid: true`; failures require correcting the
inputs, not weakening acceptance. Compilation publishes immutable `design.json`
and prints a manifest. Do not enable debug geometry for generation references.
Prepare checks the compiled packet against the contract/Draft and freezes the
prompt, task, parameters, ordered inputs and hashes. Review this frozen request
before invoking any host tool.

For editing, keep source bytes and identity unchanged except for the requested
changes. Use a new edit-specific contract/Draft/packet and attempt, with
`--parent` naming the exact existing candidate and `--instruction` naming the
change. The parent is the first `edit-source`, followed by the ordered references.
If the source is not yet a candidate, use the runbook's honest `import` path with
actual provenance first; do not pretend an import was generated by MaLiang.

### 4. Execute externally and match the result

Only after capability and authorization checks, submit the **entire frozen
request**, including actual image inputs, through the real host tool. Retain its
actual execution record. Follow the runbook's `complete` format: exact
`preparedEventId`, full `invocation`, successful outcome, actual `artifactSha256`,
and truthful `executionEvidence`. A hand-written receipt alone proves no call.

Reject a mismatched result: wrong request, missing/reordered references, changed
parameters, or wrong output hash must not be bound as success. Stop and investigate;
use a new attempt for a changed request. Record actual failures with `fail` and
use honest `import` for externally supplied art. Never fabricate receipts, model
names, successful tool calls, or retroactive approvals.

### 5. Display, inspect, and wait for human review

Run `technical` for the exact candidate, then show its image and artifact path
with its attempt/event/hash binding using the host's real display capability.
If the host cannot display it, provide the path and wait for the human to inspect
it elsewhere; do not claim to have shown it. Technical checks do not establish
style, identity, projection, pose, or visual quality.

Ask the real reviewer to choose adopt, reject, or pending and decide every required
human item. Record only their actual decision through `review`, following the
runbook's decision-file schema. An agent cannot be the human reviewer or invent
human pass entries. “I like it” is a preference, not complete adoption evidence.
Without explicit, exact-candidate human approval, **do not adopt**; retain pending
or rejected status. Synthetic human fixtures are test data, never real approval.

Use `adopt` only with the exact candidate's human-review event and all required
automatic-result events. Missing, failed, pending, unsupported, stale, or mismatched
evidence blocks adoption. A retained candidate need not be regenerated. Report
artifact paths, candidate identity, checks, observed versus attested facts, human
decision, and remaining blockers; do not imply publication or uploading.

## Installation and discovery

`skills/maliang-art` in the source repository is the single maintained source.
Do not auto-install it or write a global skill directory. On an explicit install
request, verify the target host's current import/discovery rules, then hand over
this whole folder (including locales) using its supported mechanism. Configure the
MaLiang project root separately. Merely copying files does not prove discovery.
MiMo has project/global skill scan roots; this repository distribution directory
is not itself a promise of automatic loading. Other hosts' discovery and actual
activation remain unverified until tested there. Static documentation tests do
not constitute a real host activation test.

## Checklist

- [ ] Explicit checkout and asset roots; compatible installed commands.
- [ ] Intent/reference responsibilities captured; original edit source preserved.
- [ ] Actual host capability and authorization verified; frozen request matched.
- [ ] Exact artifact displayed or human inspection explicitly pending.
- [ ] Technical checks and real human decisions kept separate; no bypassed gates.
- [ ] No credential fallback, fake receipt, automatic installation, or publication.
