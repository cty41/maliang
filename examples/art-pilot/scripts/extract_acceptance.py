"""Extract the packet-driven required acceptance manifest."""
import runpy
import sys
from pathlib import Path

sys.argv.insert(1, "acceptance")
runpy.run_path(str(Path(__file__).with_name("production.py")), run_name="__main__")
