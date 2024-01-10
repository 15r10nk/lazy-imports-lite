import ast
import re
import subprocess as sp
from pathlib import Path
from tempfile import TemporaryDirectory

from inline_snapshot import snapshot
from lazy_import_lite._transformer import TransformModuleImports

from ._utils import unparse
import sys

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
        result = sp.run([sys.executable, "script.py"], cwd=dir, capture_output=True)

        def normalize_output(output:bytes):
            text=output.decode()
            text=text.replace(str(dir),"<dir>")
            text=re.sub("at 0x[0-9a-f]*>","at <hex_value>>",text)
            return text

        assert stderr == normalize_output(result.stderr)
        assert stdout == normalize_output(result.stdout)

    with TemporaryDirectory() as d:
        d = Path(d)

        test(d / "original", code)

        transformer = TransformModuleImports()
        tree = ast.parse(code)
        new_tree = ast.fix_missing_locations(transformer.visit(tree))
        new_code = unparse(new_tree)


        if sys.version_info >= (3,9):
            # unparse does not produce the same code for 3.8
            assert new_code == transformed_code

        test(d / "transformed", new_code)


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
        snapshot("""\
import lazy_import_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'a')
b = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'b')
d = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'c')
baz = __lazy_imports_lite__.Import('bar')
f = __lazy_imports_lite__.Import('bar.foo')
bar = __lazy_imports_lite__.Import('bar')
if True:
    from x import y
    import z\
"""),
        snapshot(""),
        snapshot(""),
    )


def test_import_from():
    check_transform(
        """
from bar.foo import a

print(a)

    """,
        snapshot("""\
import lazy_import_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'a')
print(a.v)\
"""),
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
        snapshot("""\
import lazy_import_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f():
    return a.v
print(f())\
"""),
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
        snapshot("""\
import lazy_import_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f():
    a = 5
    return a
print(f())\
"""),
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
        snapshot("""\
import lazy_import_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f():
    global a
    a.v = 5
    return a.v
print(f())\
"""),
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
        snapshot("""\
import lazy_import_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f(a=5):
    return a
print(f())\
"""),
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
        snapshot("""\
import lazy_import_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'a')

def f(b=a.v):
    return b
print(f())\
"""),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_globals():
    check_transform(
        """
from bar.foo import a

for e in sorted(globals().items()):
    if e[0]!="__file__":
        print(*e)

    """,
        snapshot("""\
import lazy_import_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__name__, 'bar.foo', 'a')
for e in sorted(globals().items()):
    if e[0] != '__file__':
        print(*e)\
"""),
        snapshot("""\
__annotations__ {}
__builtins__ <module 'builtins' (built-in)>
__cached__ None
__doc__ None
__loader__ <_frozen_importlib_external.SourceFileLoader object at <hex_value>>
__name__ __main__
__package__ None
__spec__ None
a bar.foo.a
"""),
        snapshot(""),
    )



