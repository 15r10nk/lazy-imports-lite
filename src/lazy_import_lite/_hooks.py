import importlib


class ImportFrom:
    __slots__ = ("package", "module", "name", "v")

    def __init__(self, package, module, name):
        self.package = package
        self.module = module
        self.name = name

    def __getattr__(self, name):
        if name == "v":
            module = importlib.import_module(self.module, self.package)
            attr = getattr(module, self.name)
            self.v = attr
            return attr


class Import:
    __slots__ = ("module", "v")

    def __init__(self, module):
        self.module = module

    def __getattr__(self, name):
        if name == "v":
            module = importlib.import_module(self.module)
            self.v = module
            return module


def make_globals(global_provider):
    
    def g():
        return {k:v.v if isinstance(v,(ImportFrom,Import)) else v for k,v in global_provider().items() if k not in ("globals","__lazy_imports_lite__")}

    return g

