"""Guard the explicit pilot distribution boundary; builds verify archive contents."""
from fnmatch import fnmatch
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


ROOT = Path(__file__).resolve().parents[1]
CONFIG = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_art_pilot_sdist_boundary():
    target = CONFIG["tool"]["hatch"]["build"]["targets"]["sdist"]
    exclusions = target["exclude"]
    assert set(path for path in target["include"] if path.startswith("examples/")) == {
        "examples/synthetic", "examples/art-pilot/scripts", "examples/art-pilot/tests",
        "examples/art-pilot/README.md",
    }
    for path in ("characters/falcon-idle/raw/codex-idle.png", "characters/shared/poet-idle-dr-style.png",
                 "production/artifacts/example/source.bin", "maliang.lock.json", "policy.yaml",
                 "docs/archive.md", "scripts/__pycache__/production.cpython-314.pyc"):
        assert any(fnmatch("examples/art-pilot/" + path, pattern) for pattern in exclusions), path
    for path in ("scripts/production.py", "scripts/smoke_wheel.py", "scripts/lock_environment.py",
                 "tests/test_production_cli.py", "tests/test_lock_environment.py", "README.md"):
        assert not any(fnmatch("examples/art-pilot/" + path, pattern) for pattern in exclusions), path


def test_wheel_does_not_include_pilot():
    target = CONFIG["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert target["packages"] == ["src/maliang_art"]
    assert not any("examples" in source or "examples" in destination
                   for source, destination in target.get("force-include", {}).items())
