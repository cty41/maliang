# Getting started

[English](getting-started.md) | [简体中文](getting-started.zh-CN.md) | [Quick start](../README.md)

This tutorial takes about 15 minutes. Nothing here calls an image service.
You will run the offline demo, read what it wrote, then compile a real sample
brief. Unfamiliar words are defined in [concepts](concepts.md).

## 1. Install

Follow the [quick start](../README.md#quick-start) to clone, create `.venv`, and
install current source. Run every command below from the repository root with
that environment active.

## 2. Run the offline demo and read its output

```powershell
python -I examples/art-pilot/scripts/offline_demo.py --project work/art-pilot/tutorial-001
```

It prints a JSON report with `"status": "synthetic-adopted"`. The project folder
is refused if it already exists, so pick a new suffix for each run. Inside
`work/art-pilot/tutorial-001` you will find:

| File | What it is |
| --- | --- |
| `contract.json`, `draft.json`, `parameters.json` | The inputs a person would write |
| `design.json` | The compiled brief |
| `synthetic-image.png` | A tiny color block standing in for a real image |
| `synthetic-receipt.json` | A mock record of the "host" execution |
| `synthetic-human.json` | A fake human decision, test data only |
| `production/events/` | Immutable event records, one per step |
| `production/current/synthetic-demo.json` | The adopted projection |

The demo walked the whole lifecycle with stand-ins. Its report says
`realProviderExecution: false` and `realHumanApproval: false`, which is the point:
it shows the plumbing, not real art.

## 3. Compile a real sample brief

The falcon sample in the repository is a curated contract and draft:

```powershell
python -m maliang_art design validate --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json
python -m maliang_art design compile --contract examples/art-pilot/characters/falcon-idle/family-contract.json --draft examples/art-pilot/characters/falcon-idle/draft-example.json --output-dir work/art-pilot/tutorial-design
```

`validate` prints `"valid": true`; `compile` prints a manifest with
`"packet": "design.json"`. Open `work/art-pilot/tutorial-design/design.json` and
look at these fields first:

- `prompt`: the text instruction a host would send to its image tool.
- `tasks` and `targets`: which views/states to produce and at what size.
- `imageInputs` and `references`: declared reference images, in order.
- `acceptance`: checks still pending before the result can be adopted.

When validation fails, the JSON `diagnostics` give a `path`, `code`, and
`message` for each problem. MaLiang does not guess missing art decisions.

## 4. Make it yours

Copy the two falcon files to a new folder, change the character, views, and
constraints, and rerun `validate` until it passes. The schemas listed in
[concepts](concepts.md#inputs-you-write) describe every field. Compile into a new
output directory each time the inputs change.

## 5. Get a real image

Hand the brief to an Agent whose host has an image tool. [Agent setup](agent-setup.md)
covers what to tell it and what to check. The [production runbook](../examples/art-pilot/docs/runbook.en.md)
covers binding the result, technical checks, human review, and adoption.
