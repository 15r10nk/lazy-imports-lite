import subprocess as sp

from inline_snapshot import snapshot


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
