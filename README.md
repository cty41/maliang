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
maliang-art records validate examples/poet-cast/draft.json --schema pose-draft
maliang-art records check path/to/record-tree
maliang-art review validate rule review-rule.json --authority-reviewer art-director
```

Pose canvases are record-defined; previews default to half the canvas dimensions
or accept `--preview-size WIDTHxHEIGHT`. `pose select-option` requires an explicit
reviewer but never assumes a particular person. Every unselected option needs one reason. Existing output bytes are
immutable: repeating identical work succeeds, while different content at the
same path fails.

## Python API

```python
from maliang_art import canonical_bytes, stable_id, write_immutable_json
from maliang_art.records import validate_artifact
from maliang_art.workflow import validate_invocation, validate_delivery, validate_failure
```

The pure review API is available from `maliang_art.review`; structural ports are
in `maliang_art.ports`, with JSON/Pillow adapters in `maliang_art.adapters`.
Versioned JSON Schemas are shipped under `schemas/v1/`.

## Safety and scope

- Paths in records are repository-relative POSIX paths.
- SHA-256 fields bind bytes; they do not establish authorship or licensing.
- Publication uses a temporary file plus a create-if-absent hard link, making
  concurrent identical publishers safe and conflicting publishers fail closed.
- Tests use synthetic fixtures. The separately attributed `examples/poet-cast/`
  tutorial contains six hash-bound source-project files for an auditable sample.

Code is MIT licensed. `examples/poet-cast/` is CC BY 4.0; see its
`ATTRIBUTION.md`, `assets.json`, `REUSE.toml`, and `LICENSES/CC-BY-4.0.txt`.
