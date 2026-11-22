"""Nazwane normalizatory wartości (x-normalize w schema.json). Ogólne — bez wiedzy o typach dokumentów.

Każdy: f(value) -> value | None. Nieudana normalizacja → None (pole trafia do walidacji/uzgadniania).
"""

from __future__ import annotations

import re
from datetime import date
from functools import lru_cache

from .config import dictionary

MONTHS = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6, "lipca": 7,
    "sierpnia": 8, "września": 9, "wrzesnia": 9, "października": 10, "pazdziernika": 10, "października": 10,
    "listopada": 11, "grudnia": 12,
}
# Pomyłki OCR litera→cyfra stosowane WYŁĄCZNIE w kontekście cyfrowym (wyniki kroku 1).
OCR_DIGIT_MAP = str.maketrans({"O": "0", "o": "0", "D": "0", "Q": "0", "l": "1", "I": "1", "i": "1", "|": "1", "!": "1",
                               "S": "5", "s": "5", "B": "8", "Z": "2", "z": "2", "G": "6", "b": "6", "g": "9", "q": "9"})


def _s(v) -> str | None:
    if v is None:
        return None
    s = str(v)
    return s if s.strip() else None


def collapse_ws(v):
    s = _s(v)
    return re.sub(r"\s+", " ", s).strip() if s else None


def strip(v):
    s = _s(v)
    return s.strip() if s else None


def strip_trailing_punct(v):
    s = _s(v)
    return s.strip().rstrip(",;:.") if s else None


QUOTES = "\"'„”“«»‚’‘`"
_OPENERS, _CLOSERS = "„«‚", "”»’"


def _enclosing(s: str) -> bool:
    """Czy pierwszy i ostatni znak to para cudzysłowów obejmująca całą wartość („Dostawa X”, "A „B” C"),
    a nie dwie różne pary („ABC” sp. z o.o. „DEF”)."""
    if len(s) < 2 or s[0] not in QUOTES or s[-1] not in QUOTES:
        return False
    for ch in s[1:-1]:
        if ch in _OPENERS:
            return True  # zagnieżdżony cytat otwarty wcześniej niż zamknięty — zewnętrzna para obejmuje całość
        if ch in _CLOSERS or ch == s[0]:
            return False  # pierwszy cudzysłów zamyka się w środku wartości
    return True


def unquote(s: str) -> str:
    """Zdejmuje cudzysłowy obejmujące całą wartość i cudzysłów bez pary na brzegu; zostawia cudzysłowy
    będące częścią nazwy („BIOARCUS” Spółka z o.o.)."""
    s = s.strip()
    while _enclosing(s):
        s = s[1:-1].strip()
    if sum(ch in QUOTES for ch in s) % 2 == 1:  # nieparzysta liczba: cudzysłów bez pary
        if s[:1] in QUOTES and s[:1]:
            s = s[1:].strip()
        elif s[-1:] in QUOTES and s[-1:]:
            s = s[:-1].strip()
    return s


def strip_quotes(v):
    s = _s(v)
    if not s:
        return None
    return unquote(s) or None


def join_lines(v):
    s = _s(v)
    if not s:
        return None
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)  # przeniesienie z dywizem
    return re.sub(r"\s*\n\s*", " ", s)


def digits(v):
    """Same cyfry; litery mylone z cyframi zamieniane tylko, gdy token jest „prawie cyfrowy”."""
    s = _s(v)
    if not s:
        return None
    s = re.sub(r"[\s\-./]", "", s)
    if sum(c.isdigit() for c in s) >= max(1, len(s) - 2):  # co najwyżej 2 nie-cyfry → pomyłki OCR
        s = s.translate(OCR_DIGIT_MAP)
    d = re.sub(r"\D", "", s)
    return d or None


def account(v):
    """Rachunek: bez spacji/myślników, prefiks kraju zachowany, jeśli był (PL…); cyfry z mapą pomyłek OCR."""
    s = _s(v)
    if not s:
        return None
    s = re.sub(r"[\s\-]", "", s.strip())
    prefix, rest = "", s
    m = re.match(r"^([A-Za-z]{2})(?=[0-9OoDQlI|])", s)  # kod kraju, po którym zaczynają się cyfry (także mylone przez OCR)
    if m:
        prefix, rest = m.group(1).upper(), s[2:]
    d = digits(rest)
    return f"{prefix}{d}" if d else None


def amount(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(" ", " ")
    s = re.sub(r"(?i)\s*(pln|zł|zl)\b", "", s).strip().lstrip("-").strip()
    s = s.translate(str.maketrans({"O": "0", "o": "0", "l": "1", "I": "1"}))
    m = re.search(r"\d[\d ., ]*", s)
    if not m:
        return None
    t = m.group(0).strip().replace(" ", "").rstrip(".,")
    dm = re.search(r"[.,](\d{1,2})$", t)  # część dziesiętna: 1–2 cyfry („7500.0”, „34,00”); 3 cyfry = tysiące
    if dm:
        intpart, dec = t[: dm.start()], dm.group(1).ljust(2, "0")
    else:
        intpart, dec = t, "00"
    intpart = re.sub(r"[.,]", "", intpart)
    try:
        return float(f"{int(intpart)}.{dec}")
    except ValueError:
        return None


def date_iso(v):
    s = _s(v)
    if not s:
        return None
    s = s.strip().lower()
    m = re.search(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        m = re.search(r"(\d{1,2})\s?[.\-/]\s?(\d{1,2})\s?[.\-/]\s?(\d{4})", s) or re.search(r"\b(\d{1,2})\s(\d{2})\s(\d{4})\b", s)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            m = re.search(r"(\d{1,2})\s+([a-ząćęłńóśźż]+)\s+(\d{4})", s)
            if not m or m.group(2) not in MONTHS:
                return None
            d, mo, y = int(m.group(1)), MONTHS[m.group(2)], int(m.group(3))
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def bzp(v):
    s = _s(v)
    if not s:
        return None
    m = re.search(r"(\d{4})\s*/\s*BZP\s*([0-9O]{8})(\s*/\s*\d{2})?", s, re.I)
    if not m:
        return None
    num = m.group(2).replace("O", "0")
    return f"{m.group(1)}/BZP{num}" + (re.sub(r"\s", "", m.group(3)) if m.group(3) else "")


def ted(v):
    s = _s(v)
    if not s:
        return None
    m = re.search(r"(\d{4})\s*/\s*S\s*\d{3}\s*-\s*(\d{6})", s)
    if m:
        return f"{m.group(2)}-{m.group(1)}"
    m = re.search(r"(\d{6})\s*-\s*(\d{4})", s)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def to_int(v):
    if v is None or v == "":
        return None
    try:
        return int(str(v).strip())
    except ValueError:
        return None


@lru_cache(maxsize=1)
def _titles_rx() -> re.Pattern:
    t = dictionary("tytuly")
    items = sorted(t.get("titles", []) + t.get("functions", []), key=len, reverse=True)
    alt = "|".join(re.escape(x).replace(r"\ ", r"\s*") for x in items)
    return re.compile(rf"(?i)(?<!\w)(?:{alt})(?!\w)")


def strip_titles(v):
    s = _s(v)
    if not s:
        return None
    s = _titles_rx().sub(" ", s)
    return re.sub(r"\s+", " ", s).strip(" ,;-") or None


def person_nominative(v):
    """Imię i nazwisko w mianowniku. Odmianę (dopełniacz/narzędnik → mianownik) robi LLM w kroku 4;
    tu tylko ujednolicenie zapisu (wielkie litery z OCR/wydruków: 'JAN KOWALSKI' → 'Jan Kowalski')."""
    s = collapse_ws(v)
    if not s:
        return None
    if s.isupper():
        s = " ".join(w.capitalize() if not re.search(r"-", w) else "-".join(p.capitalize() for p in w.split("-")) for w in s.split())
    return s


@lru_cache(maxsize=1)
def _legal_fixes() -> list[tuple[re.Pattern, str]]:
    return [(re.compile(f["pattern"]), f["replace"]) for f in dictionary("formy_prawne").get("ocr_fixes", [])]


def legal_form(v):
    """Korekta typowych błędów OCR w formie prawnej ('Sp. z 0.0.' → 'Sp. z o.o.')."""
    s = _s(v)
    if not s:
        return None
    for rx, rep in _legal_fixes():
        s = rx.sub(rep, s)
    return s


# '@' czytane przez OCR jako symbol (Q, ©, ®, (, (), (a, (Q, (G, (d)
_EMAIL_AT = re.compile(r"^([\w.+\-]+?)(?:@|\(a\)|\(\)|\([aQGd]|[Q©®(])([\w\-]+(?:\.[\w\-]+)*\.[a-z]{2,})$")


def email(v):
    """E-mail; odtwarza '@' zniekształcone przez OCR w symbol (Q, ©, ®, (, (), (a, …). Adres bez żadnego
    śladu '@' → None (zgadywanie miejsca '@' byłoby dopasowaniem do konkretnych adresów)."""
    s = _s(v)
    if not s:
        return None
    s = s.strip().strip(".,;:<>")
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s):
        return s
    m = _EMAIL_AT.match(s)
    if m:
        return f"{m.group(1)}@{m.group(2)}"
    return None


NORMALIZERS = {
    "collapse_ws": collapse_ws, "strip": strip, "strip_trailing_punct": strip_trailing_punct,
    "strip_quotes": strip_quotes, "join_lines": join_lines, "digits": digits, "account": account,
    "amount": amount, "date_iso": date_iso, "bzp": bzp, "ted": ted, "int": to_int,
    "strip_titles": strip_titles, "person_nominative": person_nominative, "legal_form": legal_form,
    "email": email,
}


def apply(value, names: list[str]):
    for n in names or []:
        if value is None:
            return None
        value = NORMALIZERS[n](value)
    return value
