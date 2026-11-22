"""Operacje na schema.json (JSON Schema + rozszerzenia x-*): pola, szkielet wyniku, schemat dla LLM, walidacja.

Bez zewnętrznego `jsonschema` — obsługiwany podzbiór: type, enum, required, additionalProperties,
properties, items, minItems, x-max-items, pattern (x-validate), format: date.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from datetime import date

SOURCES = {"verbatim", "normalized", "inferred", "derived"}


@dataclass
class Leaf:
    path: str  # ścieżka bez indeksów, np. Odwolujacy.pelnomocnik.mail; listy jako 'Odwolujacy[]'
    spec: dict

    @property
    def key(self) -> str:
        return self.path.replace("[]", "")


def is_leaf(node: dict) -> bool:
    t = node.get("type")
    ts = t if isinstance(t, list) else [t]
    return not ({"object", "array"} & set(ts))


def iter_leaves(schema: dict, prefix: str = ""):
    if is_leaf(schema):
        yield Leaf(prefix, schema)
        return
    t = schema.get("type")
    if t == "object" or (isinstance(t, list) and "object" in t):
        for k, v in schema.get("properties", {}).items():
            yield from iter_leaves(v, f"{prefix}.{k}" if prefix else k)
    elif t == "array" or (isinstance(t, list) and "array" in t):
        yield from iter_leaves(schema.get("items", {}), f"{prefix}[]")


def skeleton(schema: dict):
    """Wynik z samymi null (listy: minItems elementów) — kolejność kluczy jak w schemacie."""
    if is_leaf(schema):
        return None
    t = schema.get("type")
    if t == "array" or (isinstance(t, list) and "array" in t):
        return [skeleton(schema.get("items", {})) for _ in range(int(schema.get("minItems", 0)))]
    return {k: skeleton(v) for k, v in schema.get("properties", {}).items()}


def strip_x(schema):
    """Czysty JSON Schema (bez kluczy x-*) — np. jako wymagany format odpowiedzi LLM."""
    if isinstance(schema, dict):
        return {k: strip_x(v) for k, v in schema.items() if not k.startswith("x-") and k != "$schema"}
    if isinstance(schema, list):
        return [strip_x(v) for v in schema]
    return copy.deepcopy(schema)


_PY_TYPES = {"string": str, "integer": int, "number": (int, float), "object": dict, "array": list, "boolean": bool}


def _type_ok(v, t) -> bool:
    ts = t if isinstance(t, list) else [t]
    for x in ts:
        if x == "null" and v is None:
            return True
        if x in ("integer",) and isinstance(v, bool):
            continue
        if x in _PY_TYPES and v is not None and isinstance(v, _PY_TYPES[x]):
            if x == "integer" and isinstance(v, float):
                continue
            return True
    return False


def validate(instance, schema: dict, path: str = "$") -> list[str]:
    errs: list[str] = []
    t = schema.get("type")
    if t is not None and not _type_ok(instance, t):
        return [f"{path}: typ {type(instance).__name__}, oczekiwano {t}"]
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} spoza {schema['enum']}")
    if isinstance(instance, str):
        if schema.get("x-validate") and not re.search(schema["x-validate"], instance):
            errs.append(f"{path}: {instance!r} nie spełnia {schema['x-validate']}")
        if schema.get("format") == "date":
            try:
                date.fromisoformat(instance)
            except ValueError:
                errs.append(f"{path}: {instance!r} nie jest datą ISO")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in instance:
                errs.append(f"{path}: brak klucza {k}")
        if schema.get("additionalProperties") is False:
            for k in instance:
                if k not in props:
                    errs.append(f"{path}: nadmiarowy klucz {k}")
        for k, v in instance.items():
            if k in props:
                errs += validate(v, props[k], f"{path}.{k}")
    if isinstance(instance, list):
        if len(instance) < int(schema.get("minItems", 0)):
            errs.append(f"{path}: mniej niż {schema['minItems']} elementów")
        if schema.get("x-max-items") and len(instance) > int(schema["x-max-items"]):
            errs.append(f"{path}: więcej niż {schema['x-max-items']} elementów")
        for i, v in enumerate(instance):
            errs += validate(v, schema.get("items", {}), f"{path}[{i}]")
    return errs
