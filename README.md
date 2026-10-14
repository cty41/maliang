# MaLiang

[English](README.md) | [简体中文](README.zh-CN.md)

**Turn game-art ideas into clear requests, then track results and reviews.**

MaLiang is a small Python toolkit for preparing character-art briefs, checking
records, and tracking which exact image was reviewed and adopted. Use it directly
or ask an Agent to operate it. Your chosen host supplies the LLM and image tools;
MaLiang itself does not call an image-generation service.

## Where it came from

MaLiang was extracted and generalized from the **Tactics artwork tooling**.
Other projects can reuse its pose-proof and artwork-review workflow without
copying the original project's identity and rules. See the [extraction record](EXTRACTED_FROM.md).

## Try it from source

Use **Windows PowerShell, Python 3.10+, and Git**. Local usage has been verified
on **Windows 11 x64**; GitHub CI's `windows-2025` runner is Windows Server x64,
not Windows 11. Install current source: the released **v0.1.0** tag does not
include the current `design` and `flow` commands. Clone/install may need the network.

```powershell
git clone https://github.com/cty41/maliang.git
cd maliang
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install .
```

From the repository root with that environment active, try the offline demo:

```powershell
python -I examples/art-pilot/scripts/offline_demo.py --project work/art-pilot/synthetic-demo-001
```

Success exits with code 0 and prints a JSON report containing `synthetic-adopted`.
The demo creates sample records and a tiny synthetic image under
`work/art-pilot/synthetic-demo-001`; this is **not real provider execution or human
approval**. No contract-writing or image service is needed for this exercise.
**Existing directories are refused**, even empty ones. Choose a new suffix for
another run; do not point this demo at an existing project.

## Connect an Agent or LLM

Configure the model, login, and any image tools in **your host**, not in MaLiang.
Ask the Agent to read `skills/maliang-art/SKILL.md` in your actual checkout;
manual reading does not require automatic skill discovery or installation.
Give it the absolute checkout path, its installed Python interpreter, and a
separate asset project root. Follow the [connection steps](docs/usage.md#agent-and-llm-setup)
to check available tools before making any external request.

For example: “Read the MaLiang skill in my checkout. Help me prepare a peregrine
falcon idle sprite; first confirm my paths and available tools, and stop before
generating images so I can review the request.” Replace this idea with your own.

## Use it for your art

Start with your character, views, poses, and constraints. MaLiang validates and
compiles the brief; an authorized external image tool executes it. Then check the
exact resulting image and obtain a real human review before adoption.
The [usage guide](docs/usage.md) covers design commands, CLI/API reference, and safety;
the [production runbook](examples/art-pilot/docs/runbook.en.md) gives the detailed workflow.
If your host can only prepare text and records, stop at preparation.

## Where are the examples?

- [Art-pilot](examples/art-pilot/README.en.md): offline practice and curated real-image
  examples, including the selected falcon and shared style reference. Showcase
  images and historical feedback are not proof of current production approval.
- [Poet-cast](examples/poet-cast/ATTRIBUTION.md): the attributed source-project tutorial.
- [Document map](llms.txt): additional references. These guides, the runbook, and
  the skill need a source checkout; they are not included in the wheel.

Code/package: [MIT](LICENSE). Poet-cast tutorial: [CC BY 4.0](examples/poet-cast/ATTRIBUTION.md).
Asset licenses: [REUSE.toml](REUSE.toml).
