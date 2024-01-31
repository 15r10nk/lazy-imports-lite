import subprocess as sp
import sys

import pytest
from inline_snapshot import snapshot


@pytest.mark.skipif(sys.version_info < (3, 9), reason="3.8 unparses differently")
def test_cli(tmp_path):
    file = tmp_path / "example.py"

    file.write_text(
        """\
from foo import bar


def f():
    print(bar())
    print(bar())
"""
    )
    result = sp.run(["lazy-imports-lite", "preview", str(file)], capture_output=True)
    assert result.returncode == 0
    assert result.stdout.decode() == snapshot(
        """\
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
bar = __lazy_imports_lite__.ImportFrom(__package__, 'foo', 'bar')

def f():
    print(bar.v())
    print(bar.v())
"""
    )


def test_cli_invalid_args():
    result = sp.run(["python", "-m", "lazy_imports_lite"], capture_output=True)
    assert result.returncode == 1
    assert result.stdout.decode() == snapshot(
        """\
Error: Please specify a valid subcommand. Use 'preview --help' for more information.
"""
    )
    assert result.stderr.decode() == snapshot("")
