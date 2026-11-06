# Contributing

Thanks for helping! BRAIN is a local-first home assistant written with the Python standard library only (no pip dependencies in the core). Please keep it that way.

## Setup

```
git clone <your fork>
cd BRAIN
python -m unittest discover -s tests -t .
```

The test suite uses a fake Ollama and a fake Home Assistant, so you do not need either installed.

## Guidelines

- One change per pull request, with tests. All tests must pass.
- Code, comments, identifiers and documentation are in **English**. User-visible text goes through the translation catalogs in `brain/locales/` (English is the reference; `es.json` must have the same keys, a test checks it).
- New tools go in `brain/tools/builtin/` and new modules in `brain/modules/`; both are discovered automatically.
- Windows `.bat` files must use CRLF line endings and `.ps1` files must be ASCII (tests enforce both).

## Adding a language

Copy `brain/locales/en.json` to `<code>.json`, translate the values, and run the tests: the parity test lists the missing keys.
