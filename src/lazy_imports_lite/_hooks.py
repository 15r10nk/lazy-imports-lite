import importlib
from collections import defaultdict


class LazyObject:
    __slots__ = ("v",)


class ImportFrom(LazyObject):
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
        else:
            assert False


pending_imports = defaultdict(list)
imported_modules = set()


class Import(LazyObject):
    __slots__ = ("module", "v")

    def __init__(self, module):
        self.module = module
        m = self.module.split(".")[0]

        if m in imported_modules:
            importlib.import_module(self.module)
        else:
            pending_imports[m].append(module)

    def __getattr__(self, name):
        if name == "v":
            m = self.module.split(".")[0]
            for pending in pending_imports[m]:
                importlib.import_module(pending)
            result = importlib.import_module(self.module.split(".")[0])
            imported_modules.add(m)
            self.v = result
            return result
        else:
            assert False


class ImportAs(LazyObject):
    __slots__ = ("module", "v")

    def __init__(self, module):
        self.module = module

    def __getattr__(self, name):
        if name == "v":
            module = importlib.import_module(self.module)
            self.v = module
            return module
        else:
            assert False


def make_globals(global_provider):
    def g():
        return {
            k: v.v if isinstance(v, LazyObject) else v
            for k, v in global_provider().items()
            if k not in ("globals", "__lazy_imports_lite__")
        }

    return g
