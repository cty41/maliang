# Extraction record

MaLiang v0.1 was extracted and generalized from the Tactics artwork tooling at
source commit `7898f45b9d7978f1eaae14732df338f440a6a5fa`.

The extraction baseline recorded by the source project was **138 tests** and a
**strict 363-0** validation result. These numbers describe the source baseline;
they are not claims about this repository's current test count.

Extracted behavior:

- deterministic pose-proof draft/card validation and rendering from
  `.agents/skills/pure-run-artwork-pipeline/scripts/pose_proof.py`;
- deterministic artwork-review policy, packet, result, qualification, and
  controlled-operation validation from
  `.agents/skills/pure-run-artwork-pipeline/scripts/artwork_review.py`.

Project-specific branding was removed. Pose selection now requires an explicit,
provider-neutral reviewer instead of hard-coding the source-project identity;
review authority behavior remains compatible with the extracted implementation.

`examples/poet-cast/` contains six byte-for-byte source files from that commit as
an explicitly attributed CC BY 4.0 tutorial. Its `assets.json` records source
paths, roles, and SHA-256 bindings. Automated tests otherwise use synthetic
fixtures.
