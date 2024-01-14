import subprocess
import subprocess as sp
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from inline_snapshot import snapshot


def write_files(dir, content):
    for path, text in content.items():
        path = dir / path
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(text)


@contextmanager
def package(name, content):
    with TemporaryDirectory() as d:
        package_dir = Path(d) / name
        package_dir.mkdir()

        write_files(package_dir, content)

        subprocess.run(
            [sys.executable, "-m", "pip", "install", str(package_dir)],
            input=b"y",
            check=True,
        )

        yield

        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", name], input=b"y", check=True
        )


def check_script(package_files, script, *, stdout="", stderr=""):
    with package("test_pck", package_files), TemporaryDirectory() as d:
        d = Path(d)

        (d / "script.py").write_text(script)

        result = sp.run([sys.executable, "script.py"], cwd=str(d), capture_output=True)

        assert result.stdout.decode() == stdout
        assert result.stderr.decode() == stderr


def test_loader():
    check_script(
        {
            "pyproject.toml": """

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name="test-pck"
keywords=["lazy-imports-lite-enabled"]
version="0.0.1"
""",
            "test_pck/__init__.py": """\
from .mx import x
from .my import y

def use_x():
    return x

def use_y():
    return y
""",
            "test_pck/mx.py": """\
print('imported mx')
x=5
""",
            "test_pck/my.py": """\
print('imported my')
y=5
""",
        },
        """\
from test_pck import use_x, use_y
print("y:",use_y())
print("x:",use_x())
""",
        stdout=snapshot(
            """\
imported my
y: 5
imported mx
x: 5
"""
        ),
        stderr=snapshot(""),
    )


def test_lazy_module_attr():
    check_script(
        {
            "pyproject.toml": """

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name="test-pck"
keywords=["lazy-imports-lite-enabled"]
version="0.0.1"
""",
            "test_pck/__init__.py": """\
from .mx import x
from .my import y

""",
            "test_pck/mx.py": """\
print('imported mx')
x=5
""",
            "test_pck/my.py": """\
print('imported my')
y=5
""",
        },
        """\
from test_pck import y
print("y:",y)

from test_pck import x
print("x:",x)
""",
        stdout=snapshot(
            """\
imported my
y: 5
imported mx
x: 5
"""
        ),
        stderr=snapshot(""),
    )
