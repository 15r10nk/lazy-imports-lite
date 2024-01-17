import ast
from typing import Any

header = """
import lazy_imports_lite._hooks as __lazy_imports_lite__
globals=__lazy_imports_lite__.make_globals(lambda g=globals:g())
"""
header_ast = ast.parse(header).body


class TransformModuleImports(ast.NodeTransformer):
    def __init__(self):
        self.transformed_imports = []
        self.functions = []
        self.context = []

        self.globals = set()
        self.locals = set()
        self.in_function = False

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        if self.context[-1] != "Module":
            return node

        if node.module == "__future__":
            return node

        new_nodes = []
        for alias in node.names:
            name = alias.asname or alias.name

            module = "." * (node.level) + (node.module or "")
            new_nodes.append(
                ast.Assign(
                    targets=[ast.Name(id=name, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Attribute(
                            value=ast.Name(id="__lazy_imports_lite__", ctx=ast.Load()),
                            attr="ImportFrom",
                            ctx=ast.Load(),
                        ),
                        args=[
                            ast.Name(id="__package__", ctx=ast.Load()),
                            ast.Constant(value=module, kind=None),
                            ast.Constant(alias.name, kind=None),
                        ],
                        keywords=[],
                    ),
                )
            )
            self.transformed_imports.append(name)
        return new_nodes

    def visit_Import(self, node: ast.Import) -> Any:
        if len(self.context) > 1:
            return node

        new_nodes = []
        for alias in node.names:
            if alias.asname:
                name = alias.asname
                new_nodes.append(
                    ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(
                                    id="__lazy_imports_lite__", ctx=ast.Load()
                                ),
                                attr="ImportAs",
                                ctx=ast.Load(),
                            ),
                            args=[ast.Constant(value=alias.name, kind=None)],
                            keywords=[],
                        ),
                    )
                )
                self.transformed_imports.append(name)
            else:
                name = alias.name.split(".")[0]
                new_nodes.append(
                    ast.Assign(
                        targets=[ast.Name(id=name, ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Attribute(
                                value=ast.Name(
                                    id="__lazy_imports_lite__", ctx=ast.Load()
                                ),
                                attr="Import",
                                ctx=ast.Load(),
                            ),
                            args=[ast.Constant(value=alias.name, kind=None)],
                            keywords=[],
                        ),
                    )
                )
                self.transformed_imports.append(name)

        return new_nodes

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        return self.handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        return self.handle_function(node)

    def visit_Lambda(self, node: ast.Lambda) -> Any:
        return self.handle_function(node)

    def handle_function(self, function):
        for field, value in ast.iter_fields(function):
            if field != "body":
                if isinstance(value, list):
                    setattr(function, field, [self.visit(v) for v in value])
                elif isinstance(value, ast.AST):
                    setattr(function, field, self.visit(value))
        self.functions.append(function)

        return function

    def handle_function_body(self, function: ast.FunctionDef):
        args = [
            *function.args.posonlyargs,
            *function.args.args,
            function.args.vararg,
            *function.args.kwonlyargs,
            function.args.kwarg,
        ]

        self.locals = {arg.arg for arg in args if arg is not None}

        self.globals = set()

        self.in_function = True

        if isinstance(function.body, list):
            function.body = [self.visit(b) for b in function.body]
        else:
            function.body = self.visit(function.body)

    def visit_Global(self, node: ast.Global) -> Any:
        self.globals.update(node.names)
        return self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> Any:
        if isinstance(node.ctx, ast.Store) and (
            node.id not in self.globals or not self.in_function
        ):
            self.locals.add(node.id)

        if node.id in self.transformed_imports and node.id not in self.locals:
            old_ctx = node.ctx
            node.ctx = ast.Load()
            return ast.Attribute(value=node, attr="v", ctx=old_ctx)
        else:
            return node

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

        if module.body:
            while is_import_from_future(module.body[pos]):
                pos += 1
        module.body[pos:pos] = header_ast

        self.context = ["FunctionBody"]
        while self.functions:
            f = self.functions.pop()
            self.handle_function_body(f)

        return module

    def generic_visit(self, node: ast.AST) -> ast.AST:
        ctx_len = len(self.context)
        self.context.append(type(node).__name__)
        result = super().generic_visit(node)
        self.context = self.context[:ctx_len]
        return result
