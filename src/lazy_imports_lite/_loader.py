import ast
import importlib.abc
import importlib.machinery
import importlib.metadata
import os
import sys
import types
from typing import Set

from ._transformer import TransformModuleImports


class LazyModule(types.ModuleType):
    def __getattr__(self, name):
        namespace = types.ModuleType.__getattribute__(self, "__dict__")
        builtins = namespace.get("__builtins__")
        if isinstance(builtins, BuiltinWrapper) and name in builtins.lazy_objects:
            return builtins.resolve(name)
        raise AttributeError(name)


enabled_packages: Set[str] = set()


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

    is_namespace = parts and min(len(p) for p in parts) == 2

    if is_namespace:
        return {".".join(p) for p in parts if len(p) == 2}
    else:
        return {".".join(p) for p in parts if len(p) == 1}


class LazyLoader(importlib.abc.Loader, importlib.machinery.PathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith("encodings."):
            # fix wired windows bug
            return None  # pragma: no cover

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

        module.__dict__["__builtins__"] = BuiltinWrapper(
            module.__dict__.get("__builtins__", __builtins__), module.__dict__
        )

        exec(mod_code, module.__dict__)
        del module.__dict__["__lazy_imports_lite__"]
        del module.__dict__["globals"]


class BuiltinWrapper(dict):
    def __init__(self, original_builtins, module_namespace):
        if isinstance(original_builtins, types.ModuleType):
            original_builtins = vars(original_builtins)
        self.lazy_objects = {}
        self.module_namespace = module_namespace
        super().__init__(original_builtins)
        self["__register_lazy_import__"] = self

    def __call__(self, name, lazy_object):
        # An import statement binds its target even if that name was resolved or
        # assigned earlier in the module.
        self.module_namespace.pop(name, None)
        self.lazy_objects[name] = lazy_object

    def resolve(self, name):
        lazy_object = self.lazy_objects.pop(name)
        value = lazy_object()
        self.module_namespace[name] = value
        return value

    def delete(self, name):
        if name in self.module_namespace:
            del self.module_namespace[name]
            self.lazy_objects.pop(name, None)
            return

        if name in self.lazy_objects:
            del self.lazy_objects[name]
            return

        raise NameError(f"name {name!r} is not defined")

    def make_globals(self, global_provider):
        def g():
            for name in list(self.lazy_objects):
                if name in self.module_namespace:
                    self.lazy_objects.pop(name)
                else:
                    self.resolve(name)
            return {
                key: value
                for key, value in global_provider().items()
                if key not in ("globals", "__lazy_imports_lite__")
            }

        return g

    def __missing__(self, name):
        if name in self.lazy_objects:
            return self.resolve(name)
        raise KeyError(name)


def setup():
    scan_distributions()

    if not any(isinstance(m, LazyLoader) for m in sys.meta_path):
        sys.meta_path.insert(0, LazyLoader())
