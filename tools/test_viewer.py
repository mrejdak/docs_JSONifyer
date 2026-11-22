"""Testy podglądu (python -m odw2json view) bez przeglądarki: serwer na losowym porcie, sztuczne input/output.
Uruchomienie:
    python -m tools.test_viewer
"""

from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from odw2json.config import doc_types  # noqa: E402
from odw2json.schema import skeleton  # noqa: E402
from odw2json.viewer import Library, make_server  # noqa: E402


def get(url: str) -> tuple[int, str, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read()


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="odw_viewer_test_"))
    inp, out = root / "input", root / "output"
    (inp / "sprawa").mkdir(parents=True)
    out.mkdir()
    pdf = b"%PDF-1.4\n%atrapa\n"
    for name in ("sprawa/odwolanie.pdf", "inny.pdf", "brak.pdf", "zepsuty.pdf", "skan.png"):
        (inp / name).write_bytes(pdf)
    (out / "sprawa").mkdir()
    typed = skeleton(doc_types()["odwolanie"].schema)
    (out / "sprawa/odwolanie.json").write_text(json.dumps(typed), encoding="utf-8")
    (out / "inny.json").write_text("{}", encoding="utf-8")
    (out / "zepsuty.json").write_text("{nie json", encoding="utf-8")
    (out / "skan.json").write_text("{}", encoding="utf-8")
    (root / "poza.pdf").write_bytes(pdf)

    ok = fail = 0

    def check(name: str, cond: bool, info=""):
        nonlocal ok, fail
        ok += cond
        fail += not cond
        print(f"  {'OK  ' if cond else 'FAIL'} {name}" + (f" — {info}" if info and not cond else ""))

    print("== stan wyników ==")
    lib = Library(inp, out, None)
    st = {rel: lib.status(rel)["state"] for rel in lib.files()}
    check("typy: odwołanie / {} / brak wyniku / zły JSON", st == {"brak.pdf": "missing", "inny.pdf": "empty", "skan.png": "empty",
                                                               "sprawa/odwolanie.pdf": "typed", "zepsuty.pdf": "invalid"}, st)
    check("ścieżka wyniku zachowuje podkatalogi", lib.output_path("sprawa/odwolanie.pdf") == out / "sprawa/odwolanie.json")
    check("plik spoza input/ odrzucony", lib.resolve("../poza.pdf") is None)
    d = lib.doc("inny.pdf")
    check("nawigacja: poprzedni/następny w kolejności listy", d["prev"] == "brak.pdf" and d["next"] == "skan.png", d)

    print("== serwer ==")
    srv, token = make_server(inp, out, "sprawa/odwolanie.pdf", "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    code, _, _ = get(f"{base}/")
    check("bez tokenu → 403", code == 403, code)
    code, ctype, body = get(f"{base}/?t={token}")
    html = body.decode("utf-8")
    check("strona startowa z tokenem → 200 HTML", code == 200 and ctype.startswith("text/html"), (code, ctype))
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    data = json.loads(m.group(1)) if m else {}
    check("dane strony: dokument startowy i jego JSON", data.get("doc", {}).get("rel") == "sprawa/odwolanie.pdf"
          and data["doc"]["status"]["state"] == "typed" and "OdwolanieKIO" in data["doc"]["status"]["json"])
    check("lista wszystkich dokumentów", len(data.get("list", [])) == 5)
    code, _, body = get(f"{base}/?doc=brak.pdf&t={token}")
    m = re.search(r'<script id="data" type="application/json">(.*?)</script>', body.decode("utf-8"), re.S)
    check("dokument bez wyniku → strona z informacją o braku", code == 200 and json.loads(m.group(1))["doc"]["status"]["state"] == "missing")
    code, ctype, body = get(f"{base}/file?doc=sprawa/odwolanie.pdf&t={token}")
    check("PDF serwowany jako application/pdf", code == 200 and ctype == "application/pdf" and body == pdf, (code, ctype))
    code, ctype, _ = get(f"{base}/file?doc=skan.png&t={token}")
    check("obraz serwowany jako image/png", code == 200 and ctype == "image/png", (code, ctype))
    code, _, _ = get(f"{base}/file?doc=../poza.pdf&t={token}")
    check("wyjście poza input/ → 404", code == 404, code)
    code, _, _ = get(f"{base}/file?doc=sprawa/odwolanie.pdf")
    check("plik bez tokenu → 403", code == 403, code)

    # strony renderowane równolegle (przeglądarka pobiera wiele obrazów naraz; PyMuPDF nie jest wątkowo bezpieczny)
    import pymupdf
    d = pymupdf.open()
    for i in range(4):
        d.new_page().insert_text((72, 72), f"Strona {i + 1}", fontsize=20)
    d.save(inp / "wiele_stron.pdf")
    results = []

    def fetch(n: int):
        results.append(get(f"{base}/page?doc=wiele_stron.pdf&n={n}&t={token}"))

    threads = [threading.Thread(target=fetch, args=(n,)) for n in [1, 2, 3, 4] * 3]
    [t.start() for t in threads]
    [t.join() for t in threads]
    check("12 równoległych żądań stron → wszystkie PNG",
          len(results) == 12 and all(c == 200 and b[:8] == b"\x89PNG\r\n\x1a\n" for c, _, b in results),
          [c for c, _, _ in results])
    code, _, _ = get(f"{base}/page?doc=wiele_stron.pdf&n=9&t={token}")
    check("strona spoza zakresu → 404", code == 404, code)
    srv.shutdown()
    srv.server_close()

    shutil.rmtree(root, ignore_errors=True)
    print(f"\n{ok} OK, {fail} FAIL")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
