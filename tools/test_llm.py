"""Testy klienta LLM bez zewnętrznej sieci: przełączanie na dostawcę zapasowego, cooldown, cache.

Dwa lokalne serwery HTTP udają dostawców (OpenAI Chat Completions). Uruchomienie:
    python -m tools.test_llm
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from odw2json import llm  # noqa: E402


class Fake:
    """Udawany dostawca: `status` = kod HTTP odpowiedzi (200 → poprawny JSON z nazwą dostawcy)."""

    def __init__(self, name: str):
        self.name, self.status, self.hits, self.bodies = name, 200, 0, []
        fake = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                fake.hits += 1
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.bodies.append(body)
                if fake.status != 200:
                    self.send_response(fake.status)
                    self.end_headers()
                    self.wfile.write(b'{"error": "fake"}')
                    return
                content = json.dumps({"kto": fake.name, "model": body["model"]})
                out = json.dumps({"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 1}})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(out.encode())

            def log_message(self, *a):
                pass

        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/v1"
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()


def _free_port_url() -> str:
    """Adres, pod którym nikt nie słucha (błąd połączenia)."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return f"http://127.0.0.1:{port}/v1"


def main() -> int:
    a, b = Fake("glowny"), Fake("zapas")
    cache = Path(tempfile.mkdtemp(prefix="odw_llm_test_"))
    cfg = {"llm": {"enabled": "auto", "cooldown": 600, "temperature": 0, "max_tokens": 50, "json_mode": True,
                   "timeout": 5, "retries": 1, "cache_dir": None,
                   "providers": [{"name": "glowny", "api_base_env": "T_A_URL", "api_key_env": "T_A_KEY", "model_env": "T_A_MODEL"},
                                 {"name": "zapas", "api_base_env": "T_B_URL", "api_key_env": "T_B_KEY", "model_env": "T_B_MODEL"}]}}
    os.environ.update({"T_A_URL": a.url, "T_A_KEY": "k", "T_A_MODEL": "model-a",
                       "T_B_URL": b.url, "T_B_KEY": "k", "T_B_MODEL": "model-b"})
    llm.settings = lambda: cfg  # type: ignore[assignment]
    llm.load_env = lambda *a, **k: None  # type: ignore[assignment]
    llm.time.sleep = lambda s: None  # ponowienia bez czekania
    llm.sys.stderr = open(os.devnull, "w")  # komunikaty o przełączeniu nie zaśmiecają wyniku

    ok = fail = 0
    n = [0]

    def msg():
        n[0] += 1  # każde wywołanie z inną treścią — bez trafień w cache
        return [{"role": "user", "content": f"test {n[0]}"}]

    def check(name: str, cond: bool, info=""):
        nonlocal ok, fail
        ok += cond
        fail += not cond
        print(f"  {'OK  ' if cond else 'FAIL'} {name}" + (f" — {info}" if info and not cond else ""))

    def reset(sa=200, sb=200):
        llm._down_until.clear()
        a.status, b.status, a.hits, b.hits = sa, sb, 0, 0

    print("== klient LLM: dostawca zapasowy ==")
    check("lista dostawców", llm.providers() == ["glowny (model-a)", "zapas (model-b)"], llm.providers())
    check("model_name = główny", llm.model_name() == "model-a")

    reset()
    ans, meta = llm.chat_json(msg())
    check("główny działa → odpowiada główny", ans["kto"] == "glowny" and meta["provider"] == "glowny" and not meta["fallback"]
          and b.hits == 0, (ans, meta, b.hits))

    reset(sa=429)
    ans, meta = llm.chat_json(msg())
    check("429 po ponowieniach → zapasowy", ans["kto"] == "zapas" and meta["fallback"] and meta["model"] == "model-b"
          and a.hits == 2, (ans, meta, a.hits))
    a_hits = a.hits
    ans, meta = llm.chat_json(msg())
    check("cooldown: kolejne wywołanie od razu do zapasowego", ans["kto"] == "zapas" and a.hits == a_hits, a.hits)
    llm._down_until["glowny"] = 0  # koniec cooldownu
    a.status = 200
    ans, meta = llm.chat_json(msg())
    check("po cooldownie wraca do głównego", ans["kto"] == "glowny", ans)

    reset(sa=401)
    ans, meta = llm.chat_json(msg())
    check("401 (klucz) → zapasowy bez ponowień", ans["kto"] == "zapas" and a.hits == 1, a.hits)

    reset(sa=402)
    ans, _ = llm.chat_json(msg())
    check("402 (limit/płatność) → zapasowy", ans["kto"] == "zapas")

    reset(sa=503)
    ans, _ = llm.chat_json(msg())
    check("503 → zapasowy", ans["kto"] == "zapas")

    reset(sa=400)
    ans, _ = llm.chat_json(msg())
    check("400 (zapytanie) → najpierw bez response_format, potem zapasowy; główny bez cooldownu",
          ans["kto"] == "zapas" and "response_format" not in a.bodies[-1] and llm._down_until.get("glowny", 0) == 0,
          (a.hits, llm._down_until))

    reset()
    os.environ["T_A_URL"] = _free_port_url()
    ans, _ = llm.chat_json(msg())
    check("błąd połączenia → zapasowy", ans["kto"] == "zapas")
    os.environ["T_A_URL"] = a.url

    reset(sa=500, sb=500)
    try:
        llm.chat_json(msg())
        check("obaj niedostępni → LLMUnavailable", False, "brak wyjątku")
    except llm.LLMUnavailable as e:
        check("obaj niedostępni → LLMUnavailable z błędami obu", "glowny" in str(e) and "zapas" in str(e), str(e)[:200])
    # wszyscy w cooldownie → mimo to próba (np. limit odnowiony)
    a.status = 200
    ans, _ = llm.chat_json(msg())
    check("wszyscy w cooldownie → próba mimo to", ans["kto"] == "glowny", ans)

    # cache: odpowiedź zapasowego z cache jest używana, gdy główny działa (bez wywołań sieciowych)
    cfg["llm"]["cache_dir"] = str(cache)
    reset(sa=429)
    m = msg()
    llm.chat_json(m)  # zapisuje do cache pod modelem zapasowym
    reset()
    ans, meta = llm.chat_json(m)
    check("cache zapasowego trafia bez sieci", meta["cached"] and ans["kto"] == "zapas" and a.hits == 0 and b.hits == 0,
          (meta, a.hits, b.hits))
    cfg["llm"]["cache_dir"] = None

    # tylko jeden dostawca skonfigurowany (brak zmiennych zapasowego) → działa jak dotąd
    for k in ("T_B_URL", "T_B_KEY", "T_B_MODEL"):
        os.environ.pop(k)
    reset(sa=429)
    check("bez zmiennych zapasowego: jeden dostawca", llm.providers() == ["glowny (model-a)"])
    try:
        llm.chat_json(msg())
        check("jeden dostawca niedostępny → LLMUnavailable", False)
    except llm.LLMUnavailable:
        check("jeden dostawca niedostępny → LLMUnavailable", True)

    shutil.rmtree(cache, ignore_errors=True)
    print(f"\n{ok} OK, {fail} FAIL")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
