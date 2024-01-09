import ast

from inline_snapshot import snapshot
from lazy_import_lite._transformer import TransformModuleImports


def check_transform(code, transformed_code):
    transformer = TransformModuleImports()
    tree = ast.parse(code)
    new_tree = ast.fix_missing_locations(transformer.visit(tree))
    assert ast.unparse(new_tree) == transformed_code


def test_transform_module_imports():
    check_transform(
        """
from blub.bar import a,b,c as d
import bar as baz
import bar.foo as f
import bar
if True:
    from x import y
    import zzz
    """,
        snapshot(
            """\
import lazy_import_from._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'blub.bar', 'a')
b = __lazy_import_lite__.ImportFrom(__name__, 'blub.bar', 'b')
d = __lazy_import_lite__.ImportFrom(__name__, 'blub.bar', 'c')
baz = __lazy_import_lite__.Import('bar')
f = __lazy_import_lite__.Import('bar.foo')
bar = __lazy_import_lite__.Import('bar')
if True:
    from x import y
    import zzz\
"""
        ),
    )


def test_usage():
    check_transform(
        """
from blub.bar import a

print(a.b)

    """,
        snapshot(
            """\
import lazy_import_from._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'blub.bar', 'a')
print(a.v.b)\
"""
        ),
    )


def test_function():
    check_transform(
        """
from blub.bar import a

def f():
    return a

def f():
    a=5
    return a

def f():
    global a
    a=5
    return a

def f(a=5):
    return a

def f(b=a):
    return b

    """,
        snapshot(
            """\
import lazy_import_from._hooks as __lazy_import_lite__
a = __lazy_import_lite__.ImportFrom(__name__, 'blub.bar', 'a')

def f():
    return a.v

def f():
    a = 5
    return a

def f():
    global a
    a.v = 5
    return a.v

def f(a=5):
    return a

def f(b=a.v):
    return b\
"""
        ),
    )
