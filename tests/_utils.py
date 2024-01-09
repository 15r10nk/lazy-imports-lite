import sys

if sys.version_info >= (3, 9):
    from ast import unparse
else:
    from astunparse import unparse as _unparse  # type: ignore

    def unparse(node):
        return _unparse(node).strip()
