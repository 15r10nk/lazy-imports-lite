import timeit
from collections import namedtuple


def blub(a):
    pass


def normal_import():
    return namedtuple


def local_import():
    from collections import namedtuple

    return namedtuple


class lazy_object:
    def __getattr__(self, k):
        if k == "v":
            from collections import namedtuple

            self.v = namedtuple
            return namedtuple


g1 = lazy_object()


def lazy_import():
    return g1.v


class lazy_object_slots:
    __slots__ = ("v",)

    def __getattr__(self, k):
        if k == "v":
            from collections import namedtuple

            self.v = namedtuple
            return namedtuple


g2 = lazy_object_slots()


def lazy_import_slots():
    return g2.v


def g3():
    global g3
    from collections import namedtuple

    def g3():
        return namedtuple

    return namedtuple


def function_import():
    return g3()


def g4():
    global g4
    from collections import namedtuple

    def g4(v=namedtuple):
        return v

    return namedtuple


def function_import_param():
    return g4()


def return_none():
    return None


results = []
for f in (
    local_import,
    lazy_import,
    lazy_import_slots,
    normal_import,
    function_import,
    function_import_param,
    return_none,
):
    results.append((timeit.timeit(f), f.__name__))

results.sort()

for time, name in results:
    print(f"{name:>25} {time}")
