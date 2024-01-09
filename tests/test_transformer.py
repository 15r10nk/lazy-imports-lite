import ast
import subprocess as sp
from pathlib import Path
from tempfile import TemporaryDirectory

from inline_snapshot import snapshot
from lazy_import_lite._transformer import TransformModuleImports

from ._utils import unparse


def check_transform(code, transformed_code, stdout, stderr):
    content = {
        "bar/__init__.py": """
foo='bar.foo'
baz='bar.baz'
""",
        "bar/foo.py": """
a='bar.foo.a'
b='bar.foo.b'
c='bar.foo.c'
""",
        "x.py": "y='x.y'",
        "z.py": "",
    }

    def test(dir: Path, code: str):
        for path, text in content.items():
            path = dir / path
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_text(text)
        (dir / "script.py").write_text(code)
        result = sp.run(["python", "script.py"], cwd=dir, capture_output=True)

        assert stdout == result.stdout.decode()
        assert stderr == result.stderr.decode()

    with TemporaryDirectory() as d:
        d = Path(d)

        test(d / "original", code)

        transformer = TransformModuleImports()
        tree = ast.parse(code)
        new_tree = ast.fix_missing_locations(transformer.visit(tree))
        new_code = unparse(new_tree)

        test(d / "transformed", new_code)

        assert new_code == transformed_code


def test_transform_module_imports():
    check_transform(
        """
from bar.foo import a,b,c as d
import bar as baz
import bar.foo as f
import bar
if True:
    from x import y
    import z
    """,
        snapshot(
            """\
import lazy_import_lite._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'bar.foo', 'a')
b = __lazy_import_lite__.ImportFrom(__name__, 'bar.foo', 'b')
d = __lazy_import_lite__.ImportFrom(__name__, 'bar.foo', 'c')
baz = __lazy_import_lite__.Import('bar')
f = __lazy_import_lite__.Import('bar.foo')
bar = __lazy_import_lite__.Import('bar')
if True:
    from x import y
    import z\
"""
        ),
        snapshot(""),
        snapshot(""),
    )


def test_import_from():
    check_transform(
        """
from bar.foo import a

print(a)

    """,
        snapshot(
            """\
import lazy_import_lite._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'bar.foo', 'a')
print(a.v)\
"""
        ),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_function_lazy():
    check_transform(
        """
from bar.foo import a

def f():
    return a

print(f())
    """,
        snapshot(
            """\
import lazy_import_lite._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f():
    return a.v
print(f())\
"""
        ),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_function_override():
    check_transform(
        """
from bar.foo import a

def f():
    a=5
    return a
print(f())
    """,
        snapshot(
            """\
import lazy_import_lite._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f():
    a = 5
    return a
print(f())\
"""
        ),
        snapshot(
            """\
5
"""
        ),
        snapshot(""),
    )


def test_function_override_global():
    check_transform(
        """
from bar.foo import a

def f():
    global a
    a=5
    return a
print(f())
    """,
        snapshot(
            """\
import lazy_import_lite._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f():
    global a
    a.v = 5
    return a.v
print(f())\
"""
        ),
        snapshot(
            """\
5
"""
        ),
        snapshot(""),
    )


def test_function_arg():
    check_transform(
        """
from bar.foo import a

def f(a=5):
    return a
print(f())
    """,
        snapshot(
            """\
import lazy_import_lite._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f(a=5):
    return a
print(f())\
"""
        ),
        snapshot(
            """\
5
"""
        ),
        snapshot(""),
    )


def test_function_default_arg():
    check_transform(
        """
from bar.foo import a

def f(b=a):
    return b
print(f())
    """,
        snapshot(
            """\
import lazy_import_lite._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f(b=a.v):
    return b
print(f())\
"""
        ),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )
