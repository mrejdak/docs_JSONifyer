"""Kompilacja wzorców z configu: makra i tolerancja na błędy OCR.

- `{{spaced:SŁOWO}}`   → litery z opcjonalną spacją między nimi (rozstrzelony druk nagłówków).
- `{{@nazwa}}`         → wzorzec z biblioteki config/patterns.yaml.
- tolerancja OCR (domyślnie włączona): każda polska litera z ogonkiem poza i wewnątrz klas znaków
  dopuszcza też odpowiednik bez ogonka (ą→[ąa], Ł→[ŁL], …).
"""

from __future__ import annotations

import re
from functools import lru_cache

from .config import patterns as named_patterns

DIACRITICS = {
    "ą": "ąa", "ć": "ćc", "ę": "ęe", "ł": "łl", "ń": "ńn", "ó": "óo", "ś": "śs", "ź": "źzż", "ż": "żzź",
    "Ą": "ĄA", "Ć": "ĆC", "Ę": "ĘE", "Ł": "ŁL", "Ń": "ŃN", "Ó": "ÓO", "Ś": "ŚS", "Ź": "ŹZŻ", "Ż": "ŻZŹ",
}

_MACRO = re.compile(r"\{\{(spaced:[^}]+|@[\w]+)\}\}")


def _spaced(word: str) -> str:
    return r"\s?".join(re.escape(c) for c in word)


def expand_macros(p: str) -> str:
    def rep(m: re.Match) -> str:
        body = m.group(1)
        if body.startswith("spaced:"):
            return _spaced(body[7:])
        name = body[1:]
        lib = named_patterns()
        if name not in lib:
            raise KeyError(f"nieznany wzorzec @{name} (config/patterns.yaml)")
        return f"(?:{lib[name]})"

    return _MACRO.sub(rep, p)


def ocr_tolerant(p: str) -> str:
    out, i, in_class = [], 0, False
    while i < len(p):
        c = p[i]
        if c == "\\" and i + 1 < len(p):
            out.append(p[i : i + 2])
            i += 2
            continue
        if in_class:
            if c == "]":
                in_class = False
            out.append(DIACRITICS.get(c, c))
        else:
            if c == "[":
                in_class = True
                out.append(c)
            elif c in DIACRITICS:
                out.append(f"[{DIACRITICS[c]}]")
            else:
                out.append(c)
        i += 1
    return "".join(out)


@lru_cache(maxsize=4096)
def compile_pattern(p: str, tolerant: bool = True) -> re.Pattern:
    p = expand_macros(p)
    if tolerant:
        p = ocr_tolerant(p)
    return re.compile(p)
