from inline_snapshot import snapshot

from .test_transformer import check_transform


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


def test_mutate_globals():
    check_transform(
        """
from bar.foo import a

globals()["x"]="x value"
print(x,a)

globals()["x"]="x2 value"
globals()["a"]="a2 value"

print(x,a)


    """,
        snapshot(
            """\
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
a = __lazy_imports_lite__.ImportFrom(__package__, 'bar.foo', 'a')
globals()['x'] = 'x value'
print(x, a._lazy_value)
globals()['x'] = 'x2 value'
globals()['a'] = 'a2 value'
print(x, a._lazy_value)\
"""
        ),
        snapshot(
            """\
x value bar.foo.a
x2 value a2 value
"""
        ),
        snapshot(""),
    )
