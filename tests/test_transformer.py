import ast
import re
import subprocess as sp
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from inline_snapshot import snapshot
from lazy_imports_lite._transformer import TransformModuleImports
from lazy_imports_lite._utils import unparse


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

        def normalize_output(output: bytes):
            text = output.decode()
            text = text.replace(str(dir), "<dir>")
            text = re.sub("at 0x[0-9a-f]*>", "at <hex_value>>", text)
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
        new_code = new_code.replace("lambda :", "lambda:")

        if sys.version_info >= (3, 9):
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
        snapshot(
            """\
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a')
b = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'b')
d = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'c')
baz = __lazy_imports_lite__.ImportAs('bar')
f = __lazy_imports_lite__.ImportAs('bar.foo')
bar = __lazy_imports_lite__.Import('bar')
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
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a')
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
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a')

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
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a')

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
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a')

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
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a')

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
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a')

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


def test_globals():
    check_transform(
        """
from bar.foo import a

for e in sorted(globals().items()):
    if e[0]!="__file__":
        print(*e)

    """,
        snapshot(
            """\
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a')
for e in sorted(globals().items()):
    if e[0] != '__file__':
        print(*e)\
"""
        ),
        snapshot(
            """\
__annotations__ {}
__builtins__ <module 'builtins' (built-in)>
__cached__ None
__doc__ None
__loader__ <_frozen_importlib_external.SourceFileLoader object at <hex_value>>
__name__ __main__
__package__ None
__spec__ None
a bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_import():
    check_transform(
        """
import bar
print(bar.foo)
import bar.foo

print(bar.foo.a)
    """,
        snapshot(
            """\
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
bar = __lazy_imports_lite__.Import('bar')
print(bar.v.foo)
bar = __lazy_imports_lite__.Import('bar.foo')
print(bar.v.foo.a)\
"""
        ),
        snapshot(
            """\
bar.foo
bar.foo.a
"""
        ),
        snapshot(""),
    )

    check_transform(
        """
import bar.foo
import bar

print(bar.foo.a)
    """,
        snapshot(
            """\
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
bar = __lazy_imports_lite__.Import('bar.foo')
bar = __lazy_imports_lite__.Import('bar')
print(bar.v.foo.a)\
"""
        ),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_import_as():
    check_transform(
        """
import bar.foo as f

print(f.a)
    """,
        snapshot(
            """\
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
f = __lazy_imports_lite__.ImportAs('bar.foo')
print(f.v.a)\
"""
        ),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_lambda():
    check_transform(
        """
import bar.foo as f

print((lambda:f.a)())
    """,
        snapshot(
            """\
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
f = __lazy_imports_lite__.ImportAs('bar.foo')
print((lambda: f.v.a)())\
"""
        ),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_async_function():
    check_transform(
        """
import bar.foo as f

async def foo():
    print(f.a)

import asyncio

asyncio.run(foo())

    """,
        snapshot(
            """\
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
f = __lazy_imports_lite__.ImportAs('bar.foo')

async def foo():
    print(f.v.a)
asyncio = __lazy_imports_lite__.Import('asyncio')
asyncio.v.run(foo())\
"""
        ),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_import_from_future():
    check_transform(
        """
"doc string"
from __future__ import annotations
import bar.foo as f

print(f.a)

    """,
        snapshot(
            '''\
"""doc string"""
from __future__ import annotations
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
f = __lazy_imports_lite__.ImportAs('bar.foo')
print(f.v.a)\
'''
        ),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_transform_default_argument():
    check_transform(
        """
"doc string"
from __future__ import annotations
import bar.foo as f

def foo(a=lambda:f.a):
    print(a())
foo()

    """,
        snapshot(
            '''\
"""doc string"""
from __future__ import annotations
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
f = __lazy_imports_lite__.ImportAs('bar.foo')

def foo(a=lambda: f.v.a):
    print(a())
foo()\
'''
        ),
        snapshot(
            """\
bar.foo.a
"""
        ),
        snapshot(""),
    )


def test_transform_decorators():
    check_transform(
        """
"doc string"
from __future__ import annotations
import bar.foo as f

def deco(thing):
    def w(f):
        print("in w",thing.a)
        return f
    return w


@deco(f)
def foo():
    print("in f",f.a)

print("call")

foo()

    """,
        snapshot(
            '''\
"""doc string"""
from __future__ import annotations
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
f = __lazy_imports_lite__.ImportAs('bar.foo')

def deco(thing):

    def w(f):
        print('in w', thing.a)
        return f
    return w

@deco(f.v)
def foo():
    print('in f', f.v.a)
print('call')
foo()\
'''
        ),
        snapshot(
            """\
in w bar.foo.a
call
in f bar.foo.a
"""
        ),
        snapshot(""),
    )
