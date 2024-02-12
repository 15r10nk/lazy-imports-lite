import importlib
from collections import defaultdict


class LazyObject:
    __slots__ = ("_lazy_value",)


class LazyImportError(BaseException):
    def __init__(self, module, package):
        self.module = module
        self.package = package

    def __str__(self):
        if self.package is None:
            return f"Deferred importing of module '{self.module}' caused an error"
        else:
            return f"Deferred importing of module '{self.module}' in '{self.package}' caused an error"


class ImportFrom(LazyObject):
    __slots__ = ("package", "module", "name", "_lazy_value")

    def __init__(self, package, module, name):
        self.package = package
        self.module = module
        self.name = name

    def __getattr__(self, name):
        if name == "_lazy_value":
            module = safe_import(self.module, self.package)
            try:
                attr = getattr(module, self.name)
            except AttributeError:
                attr = safe_import(self.module + "." + self.name, self.package)
            self._lazy_value = attr
            return attr
        else:
            assert False


pending_imports = defaultdict(list)
imported_modules = set()


def safe_import(module, package=None):
    try:
        return importlib.import_module(module, package)
    except LazyImportError:
        raise
    except:
        raise LazyImportError(module, package)


class Import(LazyObject):
    __slots__ = ("module", "_lazy_value")

    def __init__(self, module):
        self.module = module
        m = self.module.split(".")[0]

        if m in imported_modules:
            safe_import(self.module)
        else:
            pending_imports[m].append(module)

    def __getattr__(self, name):
        if name == "_lazy_value":
            m = self.module.split(".")[0]
            for pending in pending_imports[m]:
                safe_import(pending)
            result = safe_import(self.module.split(".")[0])
            imported_modules.add(m)
            self._lazy_value = result
            return result
        else:
            assert False


class ImportAs(LazyObject):
    __slots__ = ("module", "_lazy_value")

    def __init__(self, module):
        self.module = module

    def __getattr__(self, name):
        if name == "_lazy_value":
            module = safe_import(self.module)
            self._lazy_value = module
            return module
        else:
            assert False


def make_globals(global_provider):
    def g():
        return {
            key: value._lazy_value if isinstance(value, LazyObject) else value
            for key, value in dict(global_provider()).items()
            if key not in ("globals", "__lazy_imports_lite__")
        }

    return g
