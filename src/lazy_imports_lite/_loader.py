import ast
import importlib.abc
import importlib.machinery
import importlib.metadata
import os
import sys
import types

from ._hooks import LazyObject
from ._transformer import TransformModuleImports


class LazyModule(types.ModuleType):
    def __getattribute__(self, name):
        v = super().__getattribute__(name)
        if isinstance(v, LazyObject):
            return v.v
        return v


class Loader(importlib.abc.Loader, importlib.machinery.PathFinder):
    def find_spec(self, fullname, path=None, target=None):
        spec = super().find_spec(fullname, path, target)

        if "LAZY_IMPORTS_LITE_DISABLE" in os.environ:
            return None

        if spec is None:
            return None

        if spec.origin is None:
            return None

        name = spec.name.split(".")[0]

        if name != "lazy_imports_lite":
            try:
                metadata = importlib.metadata.metadata(name)
            except importlib.metadata.PackageNotFoundError:
                return None

            if metadata is None:
                return None

            if metadata["Keywords"] is None:
                return None

            keywords = metadata["Keywords"].split(",")
            if "lazy-imports-lite-enabled" in keywords and spec.origin.endswith(".py"):
                spec.loader = self
                return spec

        return None

    def create_module(self, spec):
        return LazyModule(spec.name)

    def exec_module(self, module):
        origin: str = module.__spec__.origin
        with open(origin) as f:
            mod_raw = f.read()
            mod_ast = ast.parse(mod_raw, origin, "exec")
            transformer = TransformModuleImports()
            new_ast = transformer.visit(mod_ast)

            ast.fix_missing_locations(new_ast)
        mod_code = compile(new_ast, origin, "exec")
        exec(mod_code, module.__dict__)


def setup():
    if not any(isinstance(m, Loader) for m in sys.meta_path):
        sys.meta_path.insert(0, Loader())
