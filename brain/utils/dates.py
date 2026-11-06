import unicodedata
from datetime import date, datetime, timedelta
from typing import Optional

from brain import i18n


def _plain(text) -> str:
    """Lowercase without accents, to compare words."""

    normal = unicodedata.normalize("NFD", str(text))

    return "".join(c for c in normal if unicodedata.category(c) != "Mn").strip().lower()


def weekday_names(code: Optional[str] = None) -> tuple:
    """The seven weekday names (Monday first) in the interface language."""

    return i18n.vocab("weekday_names", code or i18n.language())


def month_names(code: Optional[str] = None) -> tuple:
    """The twelve month names in the interface language."""

    return i18n.vocab("month_names", code or i18n.language())


def weekday_index(text) -> Optional[int]:
    """0 (Monday) to 6 (Sunday) for a weekday name or abbreviation in any language, else None."""

    key = _plain(text)

    return i18n.vocab("weekday_aliases").get(key)


def month_number(text) -> Optional[int]:
    """1 to 12 for a month name or abbreviation in any language, else None."""

    return i18n.vocab("month_aliases").get(_plain(text))


def today() -> str:
    """Today's date as YYYY-MM-DD."""

    return date.today().isoformat()


def long_date(day: date) -> str:
    """A date for people, e.g. "Monday, October 5" or "lunes 5 de octubre"."""

    weekday = weekday_names()[day.weekday()]
    month = month_names()[day.month - 1]

    if i18n.language() == "es":
        return f"{weekday} {day.day} de {month}"

    return f"{weekday}, {month} {day.day}"


def valid_hour(value, allow_24: bool = False):
    """'18.30' / '18:30' -> '18:30'. Empty -> None. Raises ValueError if it is not an hour."""

    if value in (None, ""):
        return None

    try:
        hours, minutes = str(value).strip().replace(".", ":").split(":")
        hours, minutes = int(hours), int(minutes)
    except ValueError:
        raise ValueError(i18n.t("The time '{0}' is not valid. Use the format HH:MM, for example 18:30.", value)) from None

    if not (0 <= hours <= (24 if allow_24 else 23) and 0 <= minutes <= 59):
        raise ValueError(i18n.t("The time '{0}' is not valid.", value))

    return f"{hours % 24:02d}:{minutes:02d}"


def now_text() -> str:
    """The current date and time in plain English, for the AI."""

    now = datetime.now()

    return f"{weekday_names('en')[now.weekday()]} {now.date().isoformat()}, {now.strftime('%H:%M')}"


def _relative(text: str) -> Optional[date]:
    words = {
        0: i18n.vocab("today_words"),
        -1: i18n.vocab("yesterday_words"),
        1: i18n.vocab("tomorrow_words"),
    }

    for offset, names in words.items():
        if text in names or _plain(text) in {_plain(n) for n in names}:
            return date.today() + timedelta(days=offset)

    return None


def validate_date(value, default_today=True):
    """
    A valid YYYY-MM-DD date.

    Also accepts DD/MM/YYYY, DD-MM-YYYY, "today", "yesterday", "tomorrow" (and
    their Spanish forms) and "5 october" / "5 de octubre 2026". With no value it
    returns today (or None when ``default_today`` is False).
    """

    if value in (None, ""):
        return today() if default_today else None

    text = str(value).strip().lower()
    day = _relative(text)

    if day:
        return day.isoformat()

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue

    connectors = set(i18n.vocab("date_connectors"))
    parts = [p for p in text.replace(",", " ").split() if p not in connectors]

    if len(parts) in (2, 3) and parts[0].isdigit() and month_number(parts[1]):
        year = int(parts[2]) if len(parts) == 3 and parts[2].isdigit() else date.today().year

        try:
            return date(year, month_number(parts[1]), int(parts[0])).isoformat()
        except ValueError:
            pass

    raise ValueError(i18n.t("The date '{0}' is not valid. Use the format YYYY-MM-DD, for example 2026-08-10.", value))
