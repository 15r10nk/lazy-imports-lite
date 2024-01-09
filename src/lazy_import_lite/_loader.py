import ast
import importlib.abc
import importlib.machinery
import sys

from ._transformer import TransformModuleImports


class Loader(importlib.abc.Loader, importlib.machinery.PathFinder):
    def find_spec(self, fullname, path=None, target=None):
        spec = super().find_spec(fullname, path, target)

        if spec is None:
            return None

        if spec.origin is None:
            return None

        name = spec.name.split(".")[0]
        if name == "inline_snapshot":
            import importlib.metadata

            keywords = importlib.metadata.metadata(name)["Keywords"].split(",")
            if "lazy-imports-lite-enabled" in keywords and spec.origin.endswith(".py"):
                spec.loader = self
                return spec

        return None

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
