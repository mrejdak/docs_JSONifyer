"""Kandydaci wartości pól z regexów (x-candidates w schema.json) — docs/04 E2.

Reguła: {"label": regex, "value": "@wzorzec" | regex z grupą v, "window": N, "priority": P}
     albo {"pattern": regex z grupą (?P<v>...), "priority": P}.
Kandydat = surowy fragment tekstu + wartość po normalizatorach pola (x-normalize).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import normalize
from .patterns import compile_pattern


@dataclass
class Candidate:
    raw: str
    value: object
    priority: int
    start: int
    end: int
    rule: int

    def to_dict(self) -> dict:
        return {"raw": self.raw, "value": self.value, "priority": self.priority, "start": self.start, "rule": self.rule}


def _value_rx(v: str) -> re.Pattern:
    if v.startswith("@"):
        return compile_pattern("(?P<v>{{" + v + "}})", tolerant=False)
    return compile_pattern(v, tolerant=False)


def find_candidates(spec: dict, text: str) -> list[Candidate]:
    out: list[Candidate] = []
    norm = spec.get("x-normalize", [])
    for ri, rule in enumerate(spec.get("x-candidates", [])):
        prio = int(rule.get("priority", 1))
        if rule.get("pattern"):
            rx = compile_pattern(rule["pattern"])
            for m in rx.finditer(text):
                g = "v" if "v" in rx.groupindex else 0
                raw = m.group(g)
                if raw:
                    out.append(Candidate(raw, normalize.apply(raw, norm), prio, m.start(g), m.end(g), ri))
        elif rule.get("label") and rule.get("value"):
            lab = compile_pattern(rule["label"])
            val = _value_rx(rule["value"])
            win = int(rule.get("window", 40))
            for m in lab.finditer(text):
                seg = text[m.end() : m.end() + win]
                vm = val.search(seg)
                if vm:
                    g = "v" if "v" in val.groupindex else 0
                    raw = vm.group(g)
                    s = m.end() + vm.start(g)
                    out.append(Candidate(raw, normalize.apply(raw, norm), prio, s, s + len(raw), ri))
    # kolejność: priorytet, potem pozycja w tekście; bez duplikatów wartości
    out.sort(key=lambda c: (c.priority, c.start))
    seen, uniq = set(), []
    for c in out:
        if c.value is None or c.value in seen:
            continue
        seen.add(c.value)
        uniq.append(c)
    return uniq
