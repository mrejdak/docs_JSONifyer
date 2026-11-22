"""Klient LLM zgodny z OpenAI Chat Completions (stdlib, bez dodatkowych pakietów).

Dostawcy (endpoint, klucz, model) z .env / środowiska — nazwy zmiennych w config/settings.yaml,
`llm.providers`, w kolejności użycia. Gdy wywołanie do dostawcy się nie powiedzie (limit klucza, błąd
serwera, sieć), to samo zapytanie idzie do następnego, a niedziałający dostawca jest pomijany przez
`llm.cooldown` sekund. Działa z każdym serwerem OpenAI-compatible: API w UE albo lokalny vLLM / llama.cpp.
Odpowiedzi cache'owane po hashu (model + wiadomości) — powtarzalność ewaluacji i zerowy koszt powtórek;
cache sprawdzany dla wszystkich dostawców przed wywołaniem sieciowym.

Testy mogą podstawić odpowiedzi bez sieci: set_stub(fn), gdzie fn(messages) -> dict.
Wyłączenie LLM bez zmiany configu: zmienna środowiskowa ODW_LLM=off.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from typing import Callable

from .config import app_path, load_env, settings


class LLMUnavailable(RuntimeError):
    pass


_stub: Callable[[list[dict]], dict] | None = None


def set_stub(fn: Callable[[list[dict]], dict] | None) -> None:
    """Podstawia funkcję zamiast prawdziwego LLM (testy polityk decyzji)."""
    global _stub
    _stub = fn


def _names(v) -> list[str]:
    if not v:
        return []
    return [v] if isinstance(v, str) else list(v)


def _env_first(names) -> str:
    return next((os.environ[e] for e in _names(names) if os.environ.get(e)), "")


def _providers(c: dict) -> list[dict]:
    """Skonfigurowani dostawcy (z ustawionym endpointem, kluczem i modelem), w kolejności z configu.
    Stary format (api_base_env / api_key_env / model_env bezpośrednio w `llm`) = jeden dostawca."""
    specs = c.get("providers") or [{"name": "llm", "api_base_env": c.get("api_base_env"),
                                    "api_key_env": c.get("api_key_env"), "model_env": c.get("model_env")}]
    out = []
    for i, p in enumerate(specs):
        base = _env_first(p.get("api_base_env")).rstrip("/")
        key, model = _env_first(p.get("api_key_env")), _env_first(p.get("model_env"))
        if base and key and model:
            out.append({"name": p.get("name") or f"llm{i + 1}", "base": base, "key": key, "model": model})
    return out


def _cfg() -> dict:
    load_env()
    c = settings()["llm"]
    return {
        "providers": _providers(c),
        "cooldown": float(c.get("cooldown", 600)),
        "enabled": c.get("enabled", "auto"),
        "temperature": c.get("temperature", 0),
        "max_tokens": c.get("max_tokens", 600),
        "timeout": c.get("timeout", 60),
        "retries": c.get("retries", 3),
        "failover_retries": c.get("failover_retries", 1),
        "json_mode": c.get("json_mode", True),
        "cache": app_path(c.get("cache_dir")),
    }


def available() -> bool:
    if os.environ.get("ODW_LLM", "").lower() in ("off", "0", "false"):
        return False
    if _stub is not None:
        return True
    c = _cfg()
    if c["enabled"] is False:
        return False
    return bool(c["providers"])


def model_name() -> str:
    """Model głównego dostawcy (etykiety raportów); pełna lista: providers()."""
    if _stub is not None:
        return "stub"
    p = _cfg()["providers"]
    return p[0]["model"] if p else ""


def providers() -> list[str]:
    """Nazwy i modele skonfigurowanych dostawców (bez kluczy) — do raportów i komendy check."""
    return [f"{p['name']} ({p['model']})" for p in _cfg()["providers"]]


def _repair_truncated(txt: str) -> dict:
    """JSON ucięty limitem tokenów → obcięcie do ostatniego kompletnego elementu i domknięcie nawiasów.
    Dlatego w formatach odpowiedzi pola decyzyjne stoją przed długimi (cytaty, uzasadnienie)."""
    stack, in_str, esc, cuts = [], False, False, []
    for i, ch in enumerate(txt):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
        elif ch == "," and stack:
            cuts.append((i, "".join(reversed(stack))))
    for i, closing in reversed(cuts):
        try:
            return json.loads(txt[:i] + closing)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"nienaprawialny JSON w odpowiedzi: {txt[:200]}")


def _extract_json(txt: str) -> dict:
    txt = txt.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", txt, re.S)
    if m:
        txt = m.group(1)
    start = txt.find("{")
    if start < 0:
        raise ValueError(f"brak JSON w odpowiedzi: {txt[:200]}")
    end = txt.rfind("}")
    if end > start:
        try:
            return json.loads(txt[start : end + 1])
        except json.JSONDecodeError:
            pass
    ans = _repair_truncated(txt[start:])
    ans["_naprawiony"] = True  # odpowiedź ucięta — ślad w trace
    return ans


class _ProviderError(LLMUnavailable):
    """Błąd jednego dostawcy. down=True → dostawca niedostępny (limit, autoryzacja, serwer, sieć) i jest
    pomijany przez cooldown; down=False → problem z tym zapytaniem (np. za długi kontekst)."""

    def __init__(self, msg: str, down: bool):
        super().__init__(msg)
        self.down = down


_down_until: dict[str, float] = {}  # stan per proces: dostawca → do kiedy pomijany


def _post(p: dict, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(
        f"{p['base']}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {p['key']}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _call(p: dict, c: dict, messages: list[dict], retries: int) -> dict:
    """Jedno zapytanie do dostawcy z ponowieniami (429/5xx/sieć: odczekanie 1, 2, 4 s). Gdy jest kolejny
    dostawca, ponowień jest mniej (llm.failover_retries) — szybciej przełączamy, niż czekamy."""
    body = {"model": p["model"], "messages": messages, "temperature": c["temperature"], "max_tokens": c["max_tokens"]}
    if c["json_mode"]:
        body["response_format"] = {"type": "json_object"}
    last = ""
    for attempt in range(int(retries) + 1):
        try:
            return _post(p, body, c["timeout"])
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}"
            if e.code == 400 and "response_format" in body:  # serwer bez trybu JSON → sam prompt wymusza JSON
                body.pop("response_format")
                continue
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 ** attempt)
                continue
            # 400/413/422 — problem z tym zapytaniem; reszta (401/402/403/404/429/5xx) — dostawca niedostępny
            raise _ProviderError(last, down=e.code not in (400, 413, 422)) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, ValueError) as e:
            # sieć, zerwane połączenie, niepełna albo nie-JSON-owa odpowiedź serwera
            last = f"błąd połączenia: {type(e).__name__}: {e}"
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise _ProviderError(last, down=True) from e
    raise _ProviderError(last or "brak odpowiedzi", down=True)


def _cache_key(model: str, messages: list[dict]) -> str:
    return hashlib.sha1(json.dumps({"m": model, "msg": messages}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def chat_json(messages: list[dict]) -> tuple[dict, dict]:
    """Wywołanie zwracające JSON. Zwraca (odpowiedź, meta: model, provider, fallback, cached, raw, usage, seconds).
    Kolejność: cache (wszyscy dostawcy) → dostawcy z configu po kolei, z pominięciem tych w cooldownie."""
    if _stub is not None:
        ans = _stub(messages)
        return ans, {"model": "stub", "provider": "stub", "fallback": False, "cached": False,
                     "raw": json.dumps(ans, ensure_ascii=False), "usage": None, "seconds": 0}
    if not available():
        raise LLMUnavailable("LLM niedostępny: ustaw endpoint, klucz i model dostawcy w .env "
                             "(nazwy zmiennych: config/settings.yaml, llm.providers)")
    c = _cfg()
    provs, cache = c["providers"], c["cache"]
    primary = provs[0]["name"]
    if cache:
        for p in provs:
            f = cache / f"{_cache_key(p['model'], messages)}.json"
            if f.exists():
                raw = f.read_text(encoding="utf-8")
                return _extract_json(raw), {"model": p["model"], "provider": p["name"], "fallback": p["name"] != primary,
                                            "cached": True, "raw": raw, "usage": None, "seconds": 0}

    now = time.time()
    order = [p for p in provs if _down_until.get(p["name"], 0) <= now] or provs  # wszyscy w cooldownie → próbuj wszystkich
    errors = []
    for n, p in enumerate(order):
        t0 = time.perf_counter()
        try:
            data = _call(p, c, messages, c["failover_retries"] if n + 1 < len(order) else c["retries"])
            try:
                raw = data["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, TypeError) as e:
                raise _ProviderError(f"nieoczekiwana odpowiedź: {json.dumps(data)[:200]}", down=False) from e
        except _ProviderError as e:
            errors.append(f"{p['name']}: {e}")
            if e.down:
                _down_until[p["name"]] = time.time() + c["cooldown"]
                nxt = next((q["name"] for q in order if q is not p and _down_until.get(q["name"], 0) <= time.time()), None)
                msg = f"przełączam na {nxt} na {c['cooldown']:.0f} s" if nxt else "brak kolejnego dostawcy"
                print(f"[llm] {p['name']} niedostępny ({str(e)[:120]}); {msg}", file=sys.stderr)
            continue
        ans = _extract_json(raw)  # ValueError → wywołujący traktuje jak brak werdyktu
        if cache:
            cache.mkdir(parents=True, exist_ok=True)
            (cache / f"{_cache_key(p['model'], messages)}.json").write_text(raw, encoding="utf-8")
        return ans, {"model": p["model"], "provider": p["name"], "fallback": p["name"] != primary, "cached": False,
                     "raw": raw, "usage": data.get("usage"), "seconds": round(time.perf_counter() - t0, 2)}
    raise LLMUnavailable("; ".join(errors))
