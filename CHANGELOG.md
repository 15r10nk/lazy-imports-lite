## v0.1.1 (2024-02-12)

### Fix

- skip modules with exec/eval

## v0.1.0 (2024-02-11)

### Feat

- support for namespace packages
- added `lazy-imports-lite preview` command
- allow setattr for lazy module attributes
- raise LazyImportError if an error is raised during the lazy importing of a module
- disable lazy-imports with LAZY_IMPORTS_LITE_DISABLE
- loader works for simple examples
- implemented import & import as
- globals returns the imported modules
- globals returns the imported modules

### Fix

- support packages with different names than the project
- fixed windows support
- use __package__ to find modules
- fixed some issues
- hide LazyObjects from modules

### Refactor

- scan distributions at startup
- renamed v to _lazy_value
