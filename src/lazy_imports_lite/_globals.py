from collections.abc import MutableMapping

from ._hooks import LazyObject

used_keys = ("globals", "__lazy_imports_lite__")


class LazyGlobals(MutableMapping):
    def __init__(self, original):
        self.data = original

    def _loaded_data(self):
        return {
            key: value._lazy_value if isinstance(value, LazyObject) else value
            for key, value in dict(self.data()).items()
            if key not in used_keys
        }

    def __len__(self):
        return len(self.data())

    def __getitem__(self, key):
        if key in self.data():
            value = self.data()[key]
            if isinstance(value, LazyObject):
                value = value._lazy_value
            return value
        raise KeyError(key)

    def __setitem__(self, key, item):
        if key in self.data():
            value = self.data()[key]
            if isinstance(value, LazyObject):
                value._lazy_value = item
                return

        self.data()[key] = item

    def __delitem__(self, key):
        del self.data()[key]

    def __iter__(self):
        return (k for k in self.data() if k not in used_keys)

    def keys(self):
        "D.keys() -> a set-like object providing a view on D's keys"
        return {k: 0 for k in self.data().keys() if k not in used_keys}.keys()

    def items(self):
        "D.items() -> a set-like object providing a view on D's items"
        return self._loaded_data().items()

    def values(self):
        "D.values() -> an object providing a view on D's values"
        return self._loaded_data().values()

    def __contains__(self, key):
        return key in self.data() and key not in used_keys

    def __repr__(self):
        return repr(self._loaded_data())

    def __or__(self, other):
        if isinstance(other, LazyGlobals):
            return dict(self._loaded_data() | other._loaded_data())
        if isinstance(other, dict):
            return dict(self._loaded_data() | other)
        return NotImplemented

    def __ror__(self, other):
        if isinstance(other, LazyGlobals):
            return dict(other._loaded_data() | self._loaded_data())
        if isinstance(other, dict):
            return dict(other | self._loaded_data())
        return NotImplemented

    def __ior__(self, other):
        data = self.data()
        if isinstance(other, LazyGlobals):
            data |= other._loaded_data()
        else:
            data |= other
        return self

    def __copy__(self):
        return self._loaded_data()

    def copy(self):
        return self._loaded_data()

    @classmethod
    def fromkeys(cls, iterable, value=None):
        assert False, "LazyGlobals should no be initialized in this way"


def make_globals(global_provider):
    def globals():
        return LazyGlobals(global_provider)

    return globals
