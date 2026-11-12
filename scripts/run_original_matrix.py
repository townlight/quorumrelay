"""Run the exact unchanged original local-parser validator with a compatibility alias.

The aliases are test-only. No reference-product runtime is installed or imported.
"""
import argparse
import runpy
import sys
import types
from pathlib import Path

from civic_data_connectors import compat

parser = argparse.ArgumentParser()
parser.add_argument("runner", type=Path)
options = parser.parse_args()
parent = types.ModuleType("townlight_runtime")
parent.__path__ = []
sys.modules["townlight_runtime"] = parent
sys.modules["townlight_runtime.meeting_imports"] = compat
sys.argv = [str(options.runner), "--local-parser-only"]
runpy.run_path(str(options.runner), run_name="__main__")
