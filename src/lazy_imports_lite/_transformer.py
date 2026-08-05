import ast
from typing import Any

header = """
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals=__register_lazy_import__.make_globals(lambda g=globals:g())
"""


class TransformModuleImports(ast.NodeTransformer):
    def __init__(self):
        self.context = []

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if self.context[-1] != "Module":
            return node

        if node.module == "__future__":
            return node

        # The names bound by a star import are only known after evaluating the
        # imported module's __all__ (or inspecting its public attributes).
        if any(alias.name == "*" for alias in node.names):
            return node

        new_nodes = []
        for alias in node.names:
            name = alias.asname or alias.name

            module = "." * (node.level) + (node.module or "")
            new_nodes.append(
                self.gen_import(
                    name,
                    "ImportFrom",
                    [ast.Name(id="__package__", ctx=ast.Load()), module, alias.name],
                )
            )
        return new_nodes

    def gen_import(self, name, import_class, args):
        return ast.Expr(
            ast.Call(
                ast.Name(id="__register_lazy_import__", ctx=ast.Load()),
                args=[
                    ast.Constant(value=name, kind=None),
                    ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="__lazy_imports_lite__", ctx=ast.Load()),
                            attr=import_class,
                            ctx=ast.Load(),
                        ),
                        args=[
                            (
                                value
                                if isinstance(value, ast.AST)
                                else ast.Constant(value=value, kind=None)
                            )
                            for value in args
                        ],
                        keywords=[],
                    ),
                ],
                keywords=[],
            )
        )

    def visit_Import(self, node: ast.Import) -> Any:
        if len(self.context) > 1:
            return node

        new_nodes = []
        for alias in node.names:
            if alias.asname:
                name = alias.asname
                new_nodes.append(self.gen_import(name, "ImportAs", [alias.name]))

            else:
                name = alias.name.split(".")[0]
                new_nodes.append(self.gen_import(name, "Import", [alias.name]))

        return new_nodes

    def visit_Delete(self, node: ast.Delete) -> Any:
        if self.context[-1] != "Module":
            return node

        new_nodes = []
        for target in node.targets:
            if isinstance(target, ast.Name):
                new_nodes.append(
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(
                                    id="__register_lazy_import__", ctx=ast.Load()
                                ),
                                attr="delete",
                                ctx=ast.Load(),
                            ),
                            args=[ast.Constant(value=target.id)],
                            keywords=[],
                        )
                    )
                )
            else:
                new_nodes.append(ast.Delete(targets=[target]))

        return new_nodes

    def visit_Module(self, module: ast.Module) -> Any:
        module = self.generic_visit(module)
        assert len(self.context) == 0

        pos = 0

        def is_import_from_future(node):
            return (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                or isinstance(node, ast.ImportFrom)
                and node.module == "__future__"
            )

        while pos < len(module.body) and is_import_from_future(module.body[pos]):
            pos += 1
        module.body[pos:pos] = ast.parse(header).body

        return module

    def generic_visit(self, node: ast.AST) -> ast.AST:
        ctx_len = len(self.context)
        self.context.append(type(node).__name__)
        result = super().generic_visit(node)
        self.context = self.context[:ctx_len]
        return result
