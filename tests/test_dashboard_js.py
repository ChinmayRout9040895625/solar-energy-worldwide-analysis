"""Run the JavaScript suite from pytest so one command covers both languages."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# A glob, not a directory: node 22 treats a bare directory argument as a module
# to execute rather than as a discovery root.
JS_TESTS = "tests/js/*.test.mjs"


def test_node_is_available():
    if shutil.which("node") is None:
        pytest.skip("node not installed — JS chart geometry is unverified here")


def test_javascript_suite_passes():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed — JS chart geometry is unverified here")

    result = subprocess.run(
        [node, "--test", JS_TESTS],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    assert result.returncode == 0, "node --test failed; output above"
