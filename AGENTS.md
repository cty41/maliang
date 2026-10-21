# MaLiang for agents

This checkout is the default workspace for both MaLiang users and developers.
Decide which kind of request you have before acting:

- **Using MaLiang** to make, edit, or review game art: read
  [skills/maliang-art/SKILL.md](skills/maliang-art/SKILL.md) first and follow it.
  Put asset projects in a new directory under `work/`, which Git ignores.
- **Changing MaLiang itself**: follow the development rules below.

Both kinds of request share these boundaries: never automatically generate
images, manufacture human approval, copy credentials/private artwork, commit,
push, publish, or move release tags. Each requires appropriate explicit
authorization; preserve unrelated changes.

## Using MaLiang

After the skill, start with
[getting started (English)](docs/getting-started.md) / [入门教程（简体中文）](docs/getting-started.zh-CN.md)
and [the usage reference (English)](docs/usage.md) / [使用参考（简体中文）](docs/usage.zh-CN.md),
then [art-pilot (English)](examples/art-pilot/README.en.md) /
[示例（简体中文）](examples/art-pilot/README.md). The authoritative production
workflow is the paired [runbook (English)](examples/art-pilot/docs/runbook.en.md) /
[运行手册（简体中文）](examples/art-pilot/docs/runbook.md).

## Developing MaLiang

Read [README.md](README.md), [CONTRIBUTING.md](CONTRIBUTING.md) for development
setup and the complete verification sequence, and [SECURITY.md](SECURITY.md)
before changing filesystem, publication, or record boundaries.

- Keep `src/maliang_art` provider-neutral. Core records and validation are
  deterministic; image I/O belongs to explicit adapters/steps. Actual image
  generation belongs to the host or project, not an assumed library capability.
- `schemas/v1` defines record contracts; preserve existing semantics or introduce
  a versioned schema. `examples/art-pilot` owns sample project values and scripts,
  not universal art rules. Tests use synthetic fixtures, not private game assets.
- Inspect implementation, tests, and Git evidence before changing documentation
  or declaring delivery. Plans in `docs/compose/spec` are not proof of behavior;
  offline fixtures are not proof of provider execution or human approval.
- Add failing regression coverage before behavior fixes. Follow CONTRIBUTING's
  full verification before claiming completion; report skipped or unavailable
  checks and coordinate shared-environment builds with other contributors.
