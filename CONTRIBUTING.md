# Contributing

MaLiang welcomes focused issues and pull requests. Read [SECURITY.md](SECURITY.md)
before changing path containment, immutable publication, or record binding.

## Development environment

Use Python 3.10 or newer. From the repository root:

```console
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` on Windows PowerShell or
`source .venv/bin/activate` on Unix, then install the current checkout:

```console
python -m pip install ".[test]"
python -m pip install reuse
```

Installing dependencies may access the configured package index. Reuse an
already prepared environment for offline work; do not install or build in a
shared environment while another contributor is validating it.

## Changes and verification

Keep the core provider-neutral and deterministic. Add synthetic tests for every
behavior change; never contribute proprietary or production game assets as
fixtures. Preserve immutable-record compatibility: add a versioned schema
instead of silently changing an existing schema. Do not generate images or
invent human approval to make a test pass.

Run focused tests first, then this complete sequence before opening a pull
request. Plain `python -m pytest` only discovers `tests`, not the sample suite.

```console
python -m pytest tests examples/art-pilot/tests -q
python -m reuse lint
python -m build
python examples/art-pilot/scripts/smoke_wheel.py --wheel dist/maliang_game_art-0.1.0-py3-none-any.whl
git diff --check
```

Use the actual newly built wheel filename if the version changes. Build creates
an sdist and then a wheel from it; the smoke check installs that wheel in a
separate temporary environment and verifies package resources and CLI help.
It may download dependencies; add `--wheelhouse <existing-dependency-directory>`
to the smoke command for offline installation. Build isolation also requires
available build dependencies. Report unavailable checks and platform-specific
skips rather than calling them passes. No separate lint/typecheck configuration
is currently defined; REUSE checks licensing, not Python typing or style.

See [art-pilot](examples/art-pilot/README.md) for sample and distribution
boundaries. Code is MIT licensed; attributed tutorial and curated example
images use the licenses declared in `REUSE.toml` and their asset manifests.
Do not commit, push, publish, or change release tags without explicit approval.
