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
            text = text.replace("\r\n", "\n")
            text = text.replace(str(dir), "<dir>")
            text = re.sub("at 0x[0-9a-fA-F]*>", "at <hex_value>>", text)
            text = text.replace(" (built-in)", "")
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

        new_code = f"""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
{new_code}
''',globals())
"""

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
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('a', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a'))
__register_lazy_import__('b', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'b'))
__register_lazy_import__('d', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'c'))
__register_lazy_import__('baz', __lazy_imports_lite__.ImportAs('bar'))
__register_lazy_import__('f', __lazy_imports_lite__.ImportAs('bar.foo'))
__register_lazy_import__('bar', __lazy_imports_lite__.Import('bar'))
if True:
    from x import y
    import z
''',globals())
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
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('a', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a'))
print(a)
''',globals())
"""),
        snapshot("""\
bar.foo.a
"""),
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
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('a', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a'))

def f():
    return a
print(f())
''',globals())
"""),
        snapshot("""\
bar.foo.a
"""),
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
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('a', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a'))

def f():
    a = 5
    return a
print(f())
''',globals())
"""),
        snapshot("""\
5
"""),
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
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('a', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a'))

def f():
    global a
    a = 5
    return a
print(f())
''',globals())
"""),
        snapshot("""\
5
"""),
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
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('a', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a'))

def f(a=5):
    return a
print(f())
''',globals())
"""),
        snapshot("""\
5
"""),
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
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('a', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a'))

def f(b=a):
    return b
print(f())
''',globals())
"""),
        snapshot("""\
bar.foo.a
"""),
        snapshot(""),
    )


def test_globals():
    check_transform(
        """
from bar.foo import a

for e in sorted(globals().items()):
    if e[0] not in ("__file__","__builtins__","__register_lazy_import__"):
        print(*e)

    """,
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('a', __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a'))
for e in sorted(globals().items()):
    if e[0] not in ('__file__', '__builtins__', '__register_lazy_import__'):
        print(*e)
''',globals())
"""),
        snapshot("""\
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


def test_import():
    check_transform(
        """
import bar
print(bar.foo)
import bar.foo

print(bar.foo.a)
    """,
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('bar', __lazy_imports_lite__.Import('bar'))
print(bar.foo)
__register_lazy_import__('bar', __lazy_imports_lite__.Import('bar.foo'))
print(bar.foo.a)
''',globals())
"""),
        snapshot("""\
bar.foo
bar.foo.a
"""),
        snapshot(""),
    )

    check_transform(
        """
import bar.foo
import bar

print(bar.foo.a)
    """,
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('bar', __lazy_imports_lite__.Import('bar.foo'))
__register_lazy_import__('bar', __lazy_imports_lite__.Import('bar'))
print(bar.foo.a)
''',globals())
"""),
        snapshot("""\
bar.foo.a
"""),
        snapshot(""),
    )


def test_import_as():
    check_transform(
        """
import bar.foo as f

print(f.a)
    """,
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('f', __lazy_imports_lite__.ImportAs('bar.foo'))
print(f.a)
''',globals())
"""),
        snapshot("""\
bar.foo.a
"""),
        snapshot(""),
    )


def test_lambda():
    check_transform(
        """
import bar.foo as f

print((lambda:f.a)())
    """,
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('f', __lazy_imports_lite__.ImportAs('bar.foo'))
print((lambda: f.a)())
''',globals())
"""),
        snapshot("""\
bar.foo.a
"""),
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
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('f', __lazy_imports_lite__.ImportAs('bar.foo'))

async def foo():
    print(f.a)
__register_lazy_import__('asyncio', __lazy_imports_lite__.Import('asyncio'))
asyncio.run(foo())
''',globals())
"""),
        snapshot("""\
bar.foo.a
"""),
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
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
\"\"\"doc string\"\"\"
from __future__ import annotations
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('f', __lazy_imports_lite__.ImportAs('bar.foo'))
print(f.a)
''',globals())
"""),
        snapshot("""\
bar.foo.a
"""),
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
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
\"\"\"doc string\"\"\"
from __future__ import annotations
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('f', __lazy_imports_lite__.ImportAs('bar.foo'))

def foo(a=lambda: f.a):
    print(a())
foo()
''',globals())
"""),
        snapshot("""\
bar.foo.a
"""),
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
        snapshot("""\
from lazy_imports_lite._loader import BuiltinWrapper

__builtins__=BuiltinWrapper(__builtins__.__dict__,globals())
__register_lazy_import__=__builtins__
del BuiltinWrapper

exec('''
\"\"\"doc string\"\"\"
from __future__ import annotations
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __register_lazy_import__.make_globals(lambda g=globals: g())
__register_lazy_import__('f', __lazy_imports_lite__.ImportAs('bar.foo'))

def deco(thing):

    def w(f):
        print('in w', thing.a)
        return f
    return w

@deco(f)
def foo():
    print('in f', f.a)
print('call')
foo()
''',globals())
"""),
        snapshot("""\
in w bar.foo.a
call
in f bar.foo.a
"""),
        snapshot(""),
    )
