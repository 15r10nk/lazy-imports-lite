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


enabled_packages = set()


def scan_distributions():
    global enabled_packages
    for dist in importlib.metadata.distributions():
        metadata = dist.metadata

        if metadata is None:
            continue  # pragma: no cover

        if metadata["Keywords"] is None:
            continue

        keywords = metadata["Keywords"].split(",")
        if "lazy-imports-lite-enabled" in keywords:
            for pkg in _top_level_declared(dist) or _top_level_inferred(dist):
                enabled_packages.add(pkg)


def _top_level_declared(dist):
    return (dist.read_text("top_level.txt") or "").split()


def _top_level_inferred(dist):
    files = dist.files
    if files is None:
        return {}  # pragma: no cover

    parts = {
        f.parts[:-1] if len(f.parts) > 1 else f.with_suffix("").name
        for f in files
        if f.suffix == ".py"
    }

    is_namespace = min(len(p) for p in parts) == 2

    if is_namespace:
        return {".".join(p) for p in parts if len(p) == 2}
    else:
        return {".".join(p) for p in parts if len(p) == 1}


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
        namespace_name = ".".join(spec.name.split(".")[:2])

        if (
            name in enabled_packages or namespace_name in enabled_packages
        ) and spec.origin.endswith(".py"):
            origin: str = spec.origin
            with open(origin) as f:
                mod_raw = f.read()
                mod_ast = ast.parse(mod_raw, origin, "exec")
            for node in ast.walk(mod_ast):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in ("eval", "exec")
                ):
                    return None
            spec.mod_ast = mod_ast
            spec.loader = self
            return spec

        return None

    def create_module(self, spec):
        return LazyModule(spec.name)

    def exec_module(self, module):
        origin: str = module.__spec__.origin

        mod_ast = module.__spec__.mod_ast
        del module.__spec__.mod_ast

        transformer = TransformModuleImports()
        new_ast = transformer.visit(mod_ast)

        ast.fix_missing_locations(new_ast)
        mod_code = compile(new_ast, origin, "exec")
        exec(mod_code, module.__dict__)
        del module.__dict__["__lazy_imports_lite__"]
        del module.__dict__["globals"]


def setup():
    scan_distributions()

    if not any(isinstance(m, LazyLoader) for m in sys.meta_path):
        sys.meta_path.insert(0, LazyLoader())
