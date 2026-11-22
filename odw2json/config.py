"""Ładowanie konfiguracji: ustawienia globalne, typy dokumentów, słowniki, wzorce, .env."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

APP_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = Path(os.environ.get("ODW_CONFIG", APP_ROOT / "config"))


def app_path(p: str | Path | None) -> Path | None:
    """Ścieżka z configu: względna → względem katalogu aplikacji."""
    if p in (None, ""):
        return None
    p = Path(p)
    return p if p.is_absolute() else APP_ROOT / p


def load_env(path: Path | None = None) -> None:
    """Minimalny parser .env (KLUCZ=wartość); nie nadpisuje zmiennych już ustawionych w środowisku."""
    path = path or APP_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


@lru_cache(maxsize=1)
def settings() -> dict:
    return yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text(encoding="utf-8"))


@dataclass
class DocType:
    name: str
    title: str
    description: str
    dir: Path
    raw: dict
    schema: dict = field(default_factory=dict)

    @property
    def classification(self) -> dict:
        return self.raw.get("classification", {})

    @property
    def pages(self) -> int:
        """Ile stron dokumentu czytamy przy ekstrakcji."""
        return int(self.raw.get("pages", settings()["text"]["max_pages"]))

    def prompt(self, name: str) -> str:
        return (self.dir / "prompts" / name).read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def doc_types() -> dict[str, DocType]:
    """Wszystkie typy z config/types/<typ>/ (kolejność alfabetyczna = deterministyczna).
    ODW_EXCLUDE_TYPES=typ1,typ2 wyłącza typy (testy: dokument nieznanego typu → {})."""
    excluded = {x for x in os.environ.get("ODW_EXCLUDE_TYPES", "").split(",") if x}
    out = {}
    for d in sorted((CONFIG_DIR / "types").iterdir()):
        ty = d / "type.yaml"
        if not d.is_dir() or not ty.exists() or d.name in excluded:
            continue
        raw = yaml.safe_load(ty.read_text(encoding="utf-8"))
        sc = d / "schema.json"
        schema = json.loads(sc.read_text(encoding="utf-8")) if sc.exists() else {}
        name = raw.get("name", d.name)
        out[name] = DocType(name=name, title=raw.get("title", name), description=raw.get("description", ""),
                            dir=d, raw=raw, schema=schema)
    return out


@lru_cache(maxsize=None)
def dictionary(name: str) -> dict:
    return json.loads((CONFIG_DIR / "dictionaries" / f"{name}.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def patterns() -> dict[str, str]:
    """Wspólna biblioteka nazwanych wzorców wartości (@nazwa)."""
    p = CONFIG_DIR / "patterns.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}
