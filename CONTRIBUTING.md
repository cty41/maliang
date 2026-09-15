# Contributing

MaLiang welcomes focused issues and pull requests.

1. Use Python 3.10 or newer.
2. Create a virtual environment and install `.[test]`.
3. Keep the core provider-neutral and deterministic.
4. Add synthetic tests for every behavior change; never contribute proprietary
   or production game assets as fixtures.
5. Run `python -m pytest` and `python -m build` before opening a pull request.
6. Preserve immutable-record compatibility. Add a versioned schema instead of
   silently changing an existing schema.

Code is contributed under MIT. Files under `examples/poet-cast/` are prepared
for CC BY 4.0 as declared in `REUSE.toml`.
