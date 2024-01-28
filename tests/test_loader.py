import os
import re
import subprocess
import subprocess as sp
import sys
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from inline_snapshot import snapshot

python_version = f"python{sys.version_info[0]}.{sys.version_info[1]}"


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


def check_script(
    package_files, script, *, stdout="", stderr="", normal_stdout="", normal_stderr=""
):
    package_files = {
        "pyproject.toml": """

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name="test-pck"
keywords=["lazy-imports-lite-enabled"]
version="0.0.1"
""",
        **package_files,
    }

    def normalize_output(output: bytes):
        text = output.decode()
        text = text.replace(sys.exec_prefix, "<exec_prefix>")
        text = re.sub("at 0x[0-9a-f]*>", "at <hex_value>>", text)
        text = re.sub("line [0-9]*", "line <n>", text)
        text = text.replace(python_version, "<python_version>")
        text = text.replace(str(script_dir), "<script_dir>")
        if " \n" in text:
            text = text.replace("\n", "⏎\n")
        return text

    with package("test_pck", package_files), TemporaryDirectory() as script_dir:
        print(sys.exec_prefix)
        script_dir = Path(script_dir)

        script_file = script_dir / "script.py"
        script_file.write_text(script)

        normal_result = sp.run(
            [sys.executable, str(script_file)],
            cwd=str(script_dir),
            env={**os.environ, "LAZY_IMPORTS_LITE_DISABLE": "True"},
            capture_output=True,
        )

        result = sp.run(
            [sys.executable, str(script_file)], cwd=str(script_dir), capture_output=True
        )
        n_stdout = normalize_output(normal_result.stdout)
        l_stdout = normalize_output(result.stdout)
        n_stderr = normalize_output(normal_result.stderr)
        l_stderr = normalize_output(result.stderr)

        if n_stdout == l_stdout:
            assert n_stdout == normal_stdout
            assert stdout == "<equal to normal>"
        else:
            assert n_stdout == normal_stdout
            assert l_stdout == stdout

        if n_stderr == l_stderr:
            assert n_stderr == normal_stderr
            assert stderr == "<equal to normal>"
        else:
            assert n_stderr == normal_stderr
            assert l_stderr == stderr


def test_loader():
    check_script(
        {
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
        stderr=snapshot("<equal to normal>"),
        normal_stdout=snapshot(
            """\
imported mx
imported my
y: 5
x: 5
"""
        ),
        normal_stderr=snapshot(""),
    )


def test_loader_keywords():
    check_script(
        {
            "test_pck/__init__.py": """\
from .mx import x
print("imported init")

def use_x():
    return x

""",
            "test_pck/mx.py": """\
print('imported mx')
x=5
""",
        },
        """\
from test_pck import use_x
print("x:",use_x())
""",
        stdout=snapshot(
            """\
imported init
imported mx
x: 5
"""
        ),
        stderr=snapshot("<equal to normal>"),
        normal_stdout=snapshot(
            """\
imported mx
imported init
x: 5
"""
        ),
        normal_stderr=snapshot(""),
    )


def test_lazy_module_attr():
    check_script(
        {
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
        stderr=snapshot("<equal to normal>"),
        normal_stdout=snapshot(
            """\
imported mx
imported my
y: 5
x: 5
"""
        ),
        normal_stderr=snapshot(""),
    )


def test_lazy_module_content():
    check_script(
        {
            "test_pck/__init__.py": """\
from .mx import x
from .my import y

""",
            "test_pck/mx.py": """\
x=5
""",
            "test_pck/my.py": """\
y=5
""",
        },
        """\
import test_pck

print(test_pck)
print(vars(test_pck).keys())
""",
        stdout=snapshot(
            """\
<module 'test_pck' from '<exec_prefix>/lib/<python_version>/site-packages/test_pck/__init__.py'>
dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'x', 'y'])
"""
        ),
        stderr=snapshot("<equal to normal>"),
        normal_stdout=snapshot(
            """\
<module 'test_pck' from '<exec_prefix>/lib/<python_version>/site-packages/test_pck/__init__.py'>
dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'mx', 'x', 'my', 'y'])
"""
        ),
        normal_stderr=snapshot(""),
    )


def test_lazy_module_content_import_from():
    check_script(
        {
            "test_pck/__init__.py": """\
from .mx import x
print("inside",globals().keys())

try:
    print("mx",mx)
except:
    print("no mx")

print("inside",globals().keys())

def later():
    print("later",globals().keys())
""",
            "test_pck/mx.py": """\
x=5
""",
        },
        """\
import test_pck

print("outside",vars(test_pck).keys())

test_pck.later()
""",
        stdout=snapshot(
            """\
inside dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'x'])
mx <module 'test_pck.mx' from '<exec_prefix>/lib/<python_version>/site-packages/test_pck/mx.py'>
inside dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'x', 'mx'])
outside dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'x', 'mx', 'later'])
later dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'x', 'mx', 'later'])
"""
        ),
        stderr=snapshot("<equal to normal>"),
        normal_stdout=snapshot(
            """\
inside dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'mx', 'x'])
mx <module 'test_pck.mx' from '<exec_prefix>/lib/<python_version>/site-packages/test_pck/mx.py'>
inside dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'mx', 'x'])
outside dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'mx', 'x', 'later'])
later dict_keys(['__name__', '__doc__', '__package__', '__loader__', '__spec__', '__path__', '__file__', '__cached__', '__builtins__', 'mx', 'x', 'later'])
"""
        ),
        normal_stderr=snapshot(""),
    )


def test_load_chain_of_modules_with_error():
    check_script(
        {
            "test_pck/__init__.py": """\
from .m import v
""",
            "test_pck/m/__init__.py": """\
from .x import v
""",
            "test_pck/m/x.py": """\
from .y import v
""",
            "test_pck/m/y.py": """\
raise ValueError()
""",
        },
        """\
try:
    from test_pck import v
    print(v)
except BaseException as e:
    while e:
        print(f"{type(e).__name__}: {e}")
        e=e.__cause__ if e.__suppress_context__ else e.__context__
""",
        stdout=snapshot(
            """\
LazyImportError: Deferred importing of module '.y' in 'test_pck.m' caused an error⏎
ValueError: ⏎
"""
        ),
        stderr=snapshot("<equal to normal>"),
        normal_stdout=snapshot(
            """\
ValueError: ⏎
"""
        ),
        normal_stderr=snapshot(""),
    )


def test_lazy_module_import_from_empty_init():
    check_script(
        {
            "test_pck/__init__.py": """\
""",
            "test_pck/ma.py": """\
a=5
""",
            "test_pck/mb.py": """\
from test_pck import ma
a=ma.a
""",
        },
        """\
from test_pck import mb

print(mb.a)
""",
        stdout=snapshot("<equal to normal>"),
        stderr=snapshot("<equal to normal>"),
        normal_stdout=snapshot(
            """\
5
"""
        ),
        normal_stderr=snapshot(""),
    )


def test_lazy_module_setattr():
    check_script(
        {
            "test_pck/__init__.py": """\
from .ma import b

def foo():
    print(b())

""",
            "test_pck/ma.py": """\
def b():
    return 5
""",
        },
        """\
from test_pck import foo
import test_pck

foo()
test_pck.b=lambda:6
foo()

""",
        stdout=snapshot("<equal to normal>"),
        stderr=snapshot("<equal to normal>"),
        normal_stdout=snapshot(
            """\
5
6
"""
        ),
        normal_stderr=snapshot(""),
    )
