# Agent and LLM setup

[English](agent-setup.md) | [简体中文](agent-setup.zh-CN.md) | [Quick start](../README.md)

**MaLiang has no model-service or API-key configuration.** Configure your text
model, image generation/editing tools, and login in the host you choose. There is
no MaLiang model field or credentials file to fill in. Do not copy keys or
subscription tokens into MaLiang records or prompts.

No skill installation or auto-discovery is needed; you point the Agent at files.

## Checklist

1. **Install current source** as in the [quick start](../README.md#quick-start).
2. **Give the Agent the absolute checkout path** and ask it to read that checkout's
   `skills/maliang-art/SKILL.md` and the [runbook](../examples/art-pilot/docs/runbook.en.md).
   Confirm `pyproject.toml`, `src/maliang_art`, and the runbook exist there. Do not
   infer the checkout from the skill's install location or the Agent's working directory.
3. **Identify the Python interpreter** with current MaLiang installed. With the
   environment active, run from the checkout (no image service is called):

```powershell
python -c "import sys; print(sys.executable)"
python -m maliang_art design validate --help
python -m maliang_art design compile --help
python -I examples/art-pilot/scripts/production.py --help
```

4. **Tell the Agent to use that interpreter** with the checkout as its working
   directory; shell activation may not carry into another host process. If needed,
   call the absolute interpreter path with PowerShell's `&` operator. If imports or
   commands fail, fix the installation with permission; do not inject source paths
   to disguise an incompatible environment.
5. **Agree a separate asset project root**, for example a fresh folder under the
   ignored `work/art-pilot/`. It is not the MaLiang source root, even when nested
   inside it. Pass it as `--project` before the sample subcommand; sample input
   paths resolve relative to it. Use new output paths rather than overwriting source art.
6. **Inspect the host's actual tools and argument schemas**: can it generate/edit,
   attach real image files or bytes in order, preserve prompts/parameters, return an
   output artifact, and display it? A model name, login, subscription, or image path
   in text proves none of these. If required image input/output is missing, stop at
   preparation and report the gap; do not silently replace an image edit with text-only work.
7. **Review the frozen request, then authorize execution separately.** Generation is
   a host operation, not a MaLiang call; there is no automatic Codex provider bridge.
   Bind only the actual result and execution evidence, run technical checks on that
   exact candidate, show it to a person, and wait for a real human decision. Neither
   an Agent nor a synthetic fixture can supply approval or bypass adoption.

## A first request

“Read the skill in my MaLiang checkout, confirm the checkout/interpreter/asset root,
and help prepare my character brief. Check the available image tools and stop for my
review before any generation.” Supply your real paths and art goals; do not assume
the Agent knows them.

## Optional skill installation

Only if you want it, check your host's current import/discovery mechanism, then use
it for `skills/maliang-art` (including its locales). Configure the checkout separately
and verify activation in the host. Copying a folder is not proof of discovery; these
instructions do not auto-install anything or claim a host activation test has passed.
