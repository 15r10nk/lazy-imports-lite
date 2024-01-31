<!-- -8<- [start:Header] -->


![ci](https://github.com/15r10nk/lazy-imports-lite/actions/workflows/ci.yml/badge.svg?branch=main)
[![Docs](https://img.shields.io/badge/docs-mkdocs-green)](https://15r10nk.github.io/lazy-imports-lite/)
[![pypi version](https://img.shields.io/pypi/v/lazy-imports-lite.svg)](https://pypi.org/project/lazy-imports-lite/)
![Python Versions](https://img.shields.io/pypi/pyversions/lazy-imports-lite)
![PyPI - Downloads](https://img.shields.io/pypi/dw/lazy-imports-lite)
[![coverage](https://img.shields.io/badge/coverage-100%25-blue)](https://15r10nk.github.io/lazy-imports-lite/contributing/#coverage)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/15r10nk)](https://github.com/sponsors/15r10nk)

<!-- -8<- [end:Header] -->

**lazy-imports-lite** changes the semantics of python imports and defers the import until it is used the first time.

It is also important to note that this project is not affiliated in any way with the original PEP.
I liked the idea of lazy-imports and wanted to use them for my projects without having to change my code.
I hope that this project makes it possible to collect knowledge about


> [!IMPORTANT]
> **lazy-imports-lite** is still in early development and may contain bugs.
> Make sure that to test your code carefully before you use it.

## Installation


You can install "lazy-imports-lite" via [pip](https://pypi.org/project/pip/):

``` bash
pip install lazy-imports-lite
```


## Key Features

- lazy imports almost like [PEP 690](https://peps.python.org/pep-0690)
- no code changes required
- can be enabled per module (by keyword in the package)

How is it different to PEP 690?

- It has not the same performance like the implementation from the pep. Every access to parts of imported modules is transformed to an attribute access `x` -> `x.v`.
- Exceptions during deferred import are converted to `LazyImportError`


## Usage

- add `lazy-imports-lite` to your project dependencies.
- add lazy-imports-lite-enabled to the keywords of your project.
  ```
    #pyproject.toml
    [project]
    keywords=["lazy-imports-lite-enabled"]
  ```

This enables lazy imports for all top level imports in your modules in your project.
One way to verify if it is enabled is to check which loader is used.

``` pycon
>>> import test_pck
>>> print(type(test_pck.__spec__.loader))
<class 'lazy_imports_lite._loader.LazyLoader'>
```

## Implementation

`lazy-imports-lite` works by rewriting the AST at runtime before the code is compiled.

The following code:
``` python
from foo import bar


def f():
    print(bar())
    print(bar())
```

is internally transformed to:

``` python
import lazy_imports_lite._hooks as __lazy_imports_lite__

globals = __lazy_imports_lite__.make_globals(lambda g=globals: g())
bar = __lazy_imports_lite__.ImportFrom(__package__, "foo", "bar")


def f():
    print(bar.v())
    print(bar.v())
```

This transformation should be never visible to you (the original source location is preserved) but it is good to know if something does not work as expected.

You can view a preview of this transformation with `lazy-imports-lite preview <filename>`, if you want to know how your code would be changed.


<!-- -8<- [start:Feedback] -->
## Issues

If you encounter any problems, please [report an issue](https://github.com/15r10nk/lazy-imports-lite/issues) along with a detailed description.
<!-- -8<- [end:Feedback] -->

## License

Distributed under the terms of the [MIT](http://opensource.org/licenses/MIT) license, "lazy-imports-lite" is free and open source software.
