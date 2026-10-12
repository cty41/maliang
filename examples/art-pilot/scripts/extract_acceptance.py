"""Extract the packet-driven required acceptance manifest."""
import runpy
import sys
from pathlib import Path

import argparse

parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
parser.add_argument("--project")
args, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *(["--project", args.project] if args.project is not None else []),
            "acceptance", *remaining]
runpy.run_path(str(Path(__file__).with_name("production.py")), run_name="__main__")
