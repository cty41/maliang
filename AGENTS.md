# Developing MaLiang

These instructions apply to modifying this repository, not to making game art.
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
- Never automatically generate images, manufacture human approval, copy
  credentials/private artwork, commit, push, publish, or move release tags.
  Each requires appropriate explicit authorization; preserve unrelated changes.

For using MaLiang to prepare and review art instead of developing it, start with
[the art-pilot sample](examples/art-pilot/README.md) and its
[runbook](examples/art-pilot/docs/runbook.md).
