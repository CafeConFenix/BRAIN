"""
Translations for BRAIN (English and Spanish), standard library only.

Messages are written in English in the code and wrapped with ``t()``. Other
languages are JSON catalogs (every ``brain/locales/<code>/*.json`` file is merged)
that map the English text to its translation. A message with no translation is
shown in English.

Words the program must *understand* (months, units, synonyms...) live in
``brain/locales/vocab_*.py`` and are read with ``vocab()``. Input is understood
in every language at once, whatever language the interface uses.

    t("Added {0} items", 3)
    t("Hello {name}", name="Ana")

The language is global (BRAIN is a single-household app). It is chosen, in this
order, by the ``BRAIN_LANG`` variable, the user's saved choice, and the language
of the operating system; English is the fallback.
"""

import importlib
import json
import locale
import os
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional

LANGUAGES = {"en": "English", "es": "Español"}
DEFAULT = "en"
_FOLDER = Path(__file__).resolve().parent / "locales"

_current: Optional[str] = None
_catalogs: Dict[str, dict] = {}


def _settings_file() -> Path:
    from brain.core.config import Config

    return Path(Config.DATA) / "language.json"


def _normalize(code) -> Optional[str]:
    short = str(code or "").strip().lower().replace("_", "-").split("-")[0]

    return short if short in LANGUAGES else None


def catalog(code: str) -> dict:
    """The translation table of a language (empty for English)."""

    if code not in _catalogs:
        merged = {}

        for file in sorted((_FOLDER / code).glob("*.json")):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue

            if isinstance(data, dict):
                merged.update(data)

        _catalogs[code] = merged

    return _catalogs[code]


def system_language() -> str:
    """Language of the operating system (English if it is not one we have)."""

    if os.name == "nt":
        try:
            import ctypes

            ident = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
            return "es" if ident == 0x0A else DEFAULT
        except Exception:
            pass

    for variable in ("LC_ALL", "LC_MESSAGES", "LANG"):
        found = _normalize(os.environ.get(variable))

        if found:
            return found

    try:
        return _normalize(locale.getlocale()[0]) or DEFAULT
    except Exception:
        return DEFAULT


def saved_language() -> Optional[str]:
    try:
        return _normalize(json.loads(_settings_file().read_text(encoding="utf-8")).get("language"))
    except (OSError, ValueError, AttributeError):
        return None


def resolve() -> str:
    return _normalize(os.environ.get("BRAIN_LANG")) or saved_language() or system_language()


def language() -> str:
    global _current

    if _current is None:
        _current = resolve()

    return _current


def set_language(code, persist: bool = True) -> str:
    """Switch language. With ``persist`` the choice is remembered for the next start."""

    global _current

    chosen = _normalize(code)

    if chosen is None:
        raise ValueError("Unsupported language: {0}. Options: {1}.".format(code, ", ".join(LANGUAGES)))

    _current = chosen

    if persist:
        try:
            file = _settings_file()
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps({"language": chosen}), encoding="utf-8")
        except OSError:
            pass

    return chosen


def reset() -> None:
    """Forget the cached language (it is resolved again on next use)."""

    global _current

    _current = None


def available() -> List[dict]:
    return [{"code": code, "name": name} for code, name in LANGUAGES.items()]


def translate(message: str, code: Optional[str] = None) -> str:
    code = code or language()

    return message if code == DEFAULT else catalog(code).get(message, message)


def t(message: str, *args, **kwargs) -> str:
    """Translate ``message`` into the current language and fill in its placeholders."""

    text = translate(message)

    if not args and not kwargs:
        return text

    try:
        return text.format(*args, **kwargs)
    except (IndexError, KeyError, ValueError):
        try:
            return message.format(*args, **kwargs)
        except (IndexError, KeyError, ValueError):
            return text


def noop(message: str) -> str:
    """Mark a message for the catalogs without translating it yet (translate it later with ``t()``)."""

    return message


def language_name(code: Optional[str] = None) -> str:
    """English name of a language, for instructions to the AI ("Reply in Spanish")."""

    return {"en": "English", "es": "Spanish"}.get(code or language(), "English")


_vocab: Optional[dict] = None


def _load_vocab() -> dict:
    """{language: {name: table}} gathered from every ``brain/locales/vocab_*.py`` (each defines VOCAB)."""

    found: Dict[str, dict] = {}

    for info in pkgutil.iter_modules([str(_FOLDER)]):
        if not info.name.startswith("vocab_"):
            continue

        module = importlib.import_module(f"brain.locales.{info.name}")

        for code, tables in getattr(module, "VOCAB", {}).items():
            found.setdefault(code, {}).update(tables)

    return found


def vocab(name: str, code: Optional[str] = None):
    """
    A table of words the program understands.

    With ``code`` it is that language's table. Without it, the tables of all the
    languages merged (dicts and sets joined, tuples and lists concatenated), so
    the input is understood in any language.
    """

    global _vocab

    if _vocab is None:
        _vocab = _load_vocab()

    tables = [_vocab[c][name] for c in ([code] if code else sorted(_vocab, key=lambda c: c != DEFAULT)) if name in _vocab.get(c, {})]

    if not tables:
        raise KeyError(f"No vocabulary called {name!r}")

    first = tables[0]

    if len(tables) == 1:
        return first

    if isinstance(first, dict):
        merged: dict = {}

        for table in tables:
            for key, value in table.items():
                if key in merged and isinstance(value, (tuple, list)) and isinstance(merged[key], (tuple, list)):
                    merged[key] = tuple(merged[key]) + tuple(v for v in value if v not in merged[key])
                else:
                    merged.setdefault(key, value)

        return merged

    if isinstance(first, (set, frozenset)):
        return set().union(*tables)

    return tuple(item for table in tables for item in table)
