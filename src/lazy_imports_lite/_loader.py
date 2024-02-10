import ast
import importlib.abc
import importlib.machinery
import importlib.metadata
import os
import sys
import types
from functools import lru_cache

from ._hooks import LazyObject
from ._transformer import TransformModuleImports


class LazyModule(types.ModuleType):
    def __getattribute__(self, name):
        value = super().__getattribute__(name)
        if isinstance(value, LazyObject):
            return value._lazy_value
        return value

    def __setattr__(self, name, value):
        try:
            current_value = super().__getattribute__(name)
        except:
            super().__setattr__(name, value)
        else:
            if isinstance(current_value, LazyObject):
                current_value._lazy_value = value
            else:
                super().__setattr__(name, value)


@lru_cache
def packages_distributions():
    return importlib.metadata.packages_distributions()


@lru_cache
def is_enabled_by_metadata(name):
    if name == "lazy_imports_lite":
        return False

    package_to_distribution = packages_distributions()

    if name not in package_to_distribution:
        return False

    names = list(set(package_to_distribution[name]))

    assert isinstance(names, list)

    if len(names) != 1:
        return False

    name = names[0]

    try:
        metadata = importlib.metadata.metadata(name)
    except importlib.metadata.PackageNotFoundError:
        return False

    if metadata is None:
        return False  # pragma: no cover

    if metadata["Keywords"] is None:
        return False

    keywords = metadata["Keywords"].split(",")
    if "lazy-imports-lite-enabled" in keywords:
        return True


class LazyLoader(importlib.abc.Loader, importlib.machinery.PathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("encodings."):
            # fix wired windows bug
            return None

        if "LAZY_IMPORTS_LITE_DISABLE" in os.environ:
            return None

        spec = super().find_spec(fullname, path, target)

        if spec is None:
            return None

        if spec.origin is None:
            return None  # pragma: no cover

        name = spec.name.split(".")[0]

        if is_enabled_by_metadata(name) and spec.origin.endswith(".py"):
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
        del module.__dict__["__lazy_imports_lite__"]
        del module.__dict__["globals"]


def setup():
    # prevent some cyclic imports
    pass

    if not any(isinstance(m, LazyLoader) for m in sys.meta_path):
        sys.meta_path.insert(0, LazyLoader())
