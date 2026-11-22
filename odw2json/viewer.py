"""Podgląd wyników: dokument z input/ (PDF albo obraz skanu) obok wyniku z output/ (JSON).

    python -m odw2json view input/sprawa/odwolanie.pdf      # otwiera przeglądarkę
    python -m odw2json view input                           # lista wszystkich dokumentów

Lokalny serwer HTTP (biblioteka standardowa) z jedną stroną: po lewej dokument (wbudowany podgląd PDF
przeglądarki), po prawej JSON z output/<ta sama ścieżka>.json, pod nim szczegóły decyzji z trace/
(typ, uzasadnienie klasyfikacji, strony z OCR). Lista dokumentów z input/ ze statusem wyniku,
przechodzenie strzałkami ←/→. Dostęp tylko z losowym tokenem w adresie; pliki serwowane wyłącznie z input/.
"""

from __future__ import annotations

import html
import json
import mimetypes
import secrets
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import pymupdf

from .config import app_path, doc_types, settings
from .pipeline import find_inputs

_PAGE = Path(__file__).with_name("viewer.html")
_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
_MUPDF = threading.Lock()  # PyMuPDF nie jest bezpieczny wątkowo, a serwer obsługuje żądania równolegle


class Library:
    """Dokumenty z input/ i ich wyniki z output/ (oraz ślady z trace/)."""

    def __init__(self, input_dir: Path, output_dir: Path, trace_dir: Path | None):
        self.input_dir, self.output_dir, self.trace_dir = input_dir.resolve(), output_dir.resolve(), trace_dir

    def files(self) -> list[str]:
        return [f.relative_to(self.input_dir).as_posix() for f in find_inputs(self.input_dir)]

    def resolve(self, rel: str) -> Path | None:
        """Plik z input/ o ścieżce względnej rel — None, gdy nie istnieje albo wychodzi poza input/."""
        p = (self.input_dir / rel).resolve()
        try:
            p.relative_to(self.input_dir)
        except ValueError:
            return None
        return p if p.is_file() else None

    def output_path(self, rel: str) -> Path:
        return self.output_dir / Path(rel).with_suffix(".json")

    def status(self, rel: str) -> dict:
        """Stan wyniku: missing | invalid | empty ({}) | typ dokumentu."""
        out = self.output_path(rel)
        if not out.is_file():
            return {"state": "missing", "label": "brak wyniku"}
        try:
            obj = json.loads(out.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return {"state": "invalid", "label": "niepoprawny JSON", "error": str(e)}
        if obj == {}:
            return {"state": "empty", "label": "{} — inny dokument", "json": obj}
        for name, dt in doc_types().items():
            if isinstance(obj, dict) and set(obj) == set(dt.schema.get("properties", {})):
                return {"state": "typed", "type": name, "label": dt.title, "json": obj}
        return {"state": "other", "label": "nieznany układ JSON", "json": obj}

    def trace(self, rel: str) -> dict | None:
        if not self.trace_dir:
            return None
        p = self.trace_dir / Path(rel).with_suffix(".trace.json")
        if not p.is_file():
            return None
        try:
            t = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None
        cl = t.get("classification") or {}
        llm = cl.get("llm") or {}
        txt = t.get("text") or {}
        return {
            "type": cl.get("type"), "path": cl.get("path"), "reason": cl.get("reason"),
            "llm": {k: llm.get(k) for k in ("rodzaj_dokumentu", "typ", "pewnosc", "uzasadnienie", "dowody", "provider", "model")} if llm else None,
            "pages_total": txt.get("pages_total"), "pages_read": txt.get("pages_read"), "ocr_pages": txt.get("ocr_pages"),
            "mean_conf": txt.get("mean_conf"), "text_checks": txt.get("text_checks") or {},
            "seconds": t.get("seconds"), "error": t.get("error"),
        }

    @staticmethod
    def page_count(p: Path | None) -> int:
        if not p:
            return 0
        try:
            with _MUPDF, pymupdf.open(p) as d:
                return d.page_count
        except Exception:  # noqa: BLE001 — uszkodzony plik: podgląd stron niedostępny
            return 0

    def doc(self, rel: str) -> dict:
        files = self.files()
        i = files.index(rel) if rel in files else -1
        p = self.resolve(rel)
        ext = p.suffix.lower() if p else ""
        st = self.status(rel)
        return {
            "rel": rel, "name": Path(rel).name, "exists": p is not None, "pages": self.page_count(p),
            "kind": "pdf" if ext == ".pdf" else "image" if ext in _IMAGE_EXT else "other",
            "output_rel": self.output_path(rel).relative_to(self.output_dir).as_posix(),
            "status": st, "trace": self.trace(rel),
            "prev": files[i - 1] if i > 0 else None, "next": files[i + 1] if 0 <= i < len(files) - 1 else None,
            "index": i + 1, "count": len(files),
        }

    def listing(self) -> list[dict]:
        out = []
        for rel in self.files():
            st = self.status(rel)
            out.append({"rel": rel, "state": st["state"], "label": st["label"]})
        return out


def _handler(lib: Library, token: str, start: str | None):
    page = _PAGE.read_text(encoding="utf-8")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):  # cicho — to narzędzie interaktywne
            pass

        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            if "Cache-Control" not in (extra or {}):
                self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            cookie = self.headers.get("Cookie", "")
            if q.get("t") != token and f"odw_t={token}" not in cookie:
                self._send(HTTPStatus.FORBIDDEN, "Brak dostępu — otwórz adres z tokenem wypisany przez komendę view.".encode(),
                           "text/plain; charset=utf-8")
                return
            if u.path == "/":
                rel = q.get("doc") or start
                files = lib.files()
                if rel is None and files:
                    rel = files[0]
                data = {"token": token, "doc": lib.doc(rel) if rel else None, "list": lib.listing(),
                        "input_dir": str(lib.input_dir), "output_dir": str(lib.output_dir)}
                body = page.replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
                body = body.replace("__TITLE__", html.escape(Path(rel).name if rel else "Odwołania2JSON"))
                self._send(HTTPStatus.OK, body.encode("utf-8"), "text/html; charset=utf-8",
                           {"Set-Cookie": f"odw_t={token}; Path=/; HttpOnly; SameSite=Strict"})
                return
            if u.path == "/page":  # strona dokumentu jako PNG (działa w każdej przeglądarce, też dla obrazów skanów)
                p = lib.resolve(q.get("doc", ""))
                try:
                    n = int(q.get("n", "1"))
                    zoom = min(max(float(q.get("z", "1.6")), 0.5), 3.0)
                    if p is None or n < 1:
                        raise ValueError("brak pliku albo zły numer strony")
                    with _MUPDF, pymupdf.open(p) as d:
                        png = d[n - 1].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("png")
                except Exception:  # noqa: BLE001 — brak pliku, zły numer strony, uszkodzony PDF
                    self._send(HTTPStatus.NOT_FOUND, b"brak strony", "text/plain; charset=utf-8")
                    return
                self._send(HTTPStatus.OK, png, "image/png", {"Cache-Control": "private, max-age=300"})
                return
            if u.path == "/file":
                p = lib.resolve(q.get("doc", ""))
                if not p:
                    self._send(HTTPStatus.NOT_FOUND, b"brak pliku", "text/plain; charset=utf-8")
                    return
                ctype = "application/pdf" if p.suffix.lower() == ".pdf" else (mimetypes.guess_type(p.name)[0] or "application/octet-stream")
                self._send(HTTPStatus.OK, p.read_bytes(), ctype,
                           {"Content-Disposition": f"inline; filename*=UTF-8''{quote(p.name)}"})
                return
            self._send(HTTPStatus.NOT_FOUND, b"nie ma takiej strony", "text/plain; charset=utf-8")

    return H


def make_server(input_dir: Path, output_dir: Path, start: str | None, host: str = "127.0.0.1", port: int = 8000,
                trace_dir: Path | None = None) -> tuple[ThreadingHTTPServer, str]:
    lib = Library(input_dir, output_dir, trace_dir)
    token = secrets.token_urlsafe(12)
    srv = ThreadingHTTPServer((host, port), _handler(lib, token, start))
    return srv, token


def run_viewer(path: str, input_dir: str = "input", output_dir: str = "output", host: str = "127.0.0.1",
               port: int = 8000, open_browser: bool = True, url_host: str | None = None, url_port: int | None = None) -> int:
    inp, out = Path(input_dir).resolve(), Path(output_dir).resolve()
    if not inp.is_dir():
        print(f"brak katalogu wejściowego {inp}")
        return 2
    target = Path(path).resolve()
    if not target.exists():
        print(f"nie ma takiego pliku ani katalogu: {path}")
        return 2
    try:
        rel = target.relative_to(inp).as_posix()
    except ValueError:
        print(f"{path} nie leży w katalogu wejściowym {inp} (inny katalog: --input)")
        return 2
    lib = Library(inp, out, app_path(settings()["output"].get("trace_dir", "trace")))
    start = None if target.is_dir() else rel
    if start:
        st = lib.status(start)
        if st["state"] == "missing":
            print(f"UWAGA: brak wyniku dla {rel} — nie ma pliku {lib.output_path(start)} "
                  "(dokument nie był jeszcze przetworzony: uruchom komendę z RUN.md). Podgląd pokaże sam dokument.")
        elif st["state"] == "invalid":
            print(f"UWAGA: wynik {lib.output_path(start)} nie jest poprawnym JSON-em: {st.get('error')}")
        else:
            print(f"{rel} → {lib.output_path(start).relative_to(out).as_posix()}: {st['label']}")
    srv, token = make_server(inp, out, start, host, port, lib.trace_dir)
    shown_host = url_host or ("localhost" if host in ("0.0.0.0", "127.0.0.1", "") else host)
    url = f"http://{shown_host}:{url_port or srv.server_address[1]}/?t={token}"
    print(f"Podgląd: {url}\n(Ctrl+C kończy)", flush=True)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0
