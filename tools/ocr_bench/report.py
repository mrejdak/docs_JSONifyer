"""Zbiorczy raport reports/ocr/summary.md z plików CSV (compare + survival).

Konfiguracje porównujemy na WSPÓLNYCH stronach (siatka liczona na podzbiorze, najlepsze na całości).
Ręcznie pisane wnioski: reports/ocr/wnioski.md (dołączane na początku raportu, jeśli istnieje).
"""

from __future__ import annotations

import statistics as st
from collections import Counter, defaultdict

from .common import OUT, load_manifest, read_csv

LEVELS = ["L0", "L1", "L2", "L3"]


def md_table(header: list[str], rows: list[list]) -> str:
    def fmt(v):
        if isinstance(v, float):
            return f"{v:.4f}" if abs(v) < 1 else f"{v:.2f}"
        return str(v).replace("|", "\\|").replace("\n", " ")

    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(fmt(v) for v in r) + " |" for r in rows]
    return "\n".join(out)


def pct(x: float) -> str:
    return f"{100 * x:.2f}%"


def _f(r, k):
    v = r.get(k, "")
    return float(v) if v not in ("", None) else None


def build_report() -> None:
    parts: list[str] = ["# Benchmark OCR — raport (krok 1)\n",
                        "Generowany przez `python -m tools.ocr_bench report`. Opis metod: `docs/01_ocr_tesseract.md`.\n"]
    wn = OUT / "wnioski.md"
    if wn.exists():
        parts.append(wn.read_text(encoding="utf-8") + "\n")

    # ---------------------------------------------------------------- dane
    docs = load_manifest()
    c = Counter((d.set, d.label) for d in docs)
    pages = Counter()
    for d in docs:
        pages[(d.set, d.label)] += d.pages
    parts.append("## 1. Dane\n")
    parts.append(md_table(["zestaw", "typ (z nazwy)", "dokumenty", "strony"],
                          [[s, lab, c[(s, lab)], pages[(s, lab)]] for s, lab in sorted(c)]) + "\n")

    per_page = read_csv(OUT / "per_page.csv")
    errors = read_csv(OUT / "errors.csv")
    dels: dict = defaultdict(lambda: [0, 0])  # (config, doc, page) -> [pominięte tokeny, w polach GT]
    for e in errors:
        if e["kind"] == "del":
            k = (e["config"], e["doc_id"], e["page"])
            dels[k][0] += 1
            dels[k][1] += bool(e["in_field"])
    best_s = None
    if per_page:
        # ------------------------------------------------------------ ranking na S
        clean = [r for r in per_page if r["degrade"] == "none" and r["preproc"] == "none"]
        by_cfg: dict = defaultdict(dict)
        for r in clean:
            by_cfg[r["config"]][(r["doc_id"], r["page"])] = r
        common = set.intersection(*(set(v) for v in by_cfg.values())) if by_cfg else set()
        rank = []
        for cfg, pg in by_cfg.items():
            rows = [pg[k] for k in common]
            if not rows:
                continue
            cer = [_f(r, "cer") for r in rows]
            chars = sum(int(r["ref_chars"]) for r in rows)
            errs = sum(int(r["char_errors"]) for r in rows)
            secs = [_f(r, "ocr_seconds") for r in rows if _f(r, "ocr_seconds") is not None]
            d_all = sum(dels[(cfg, r["doc_id"], r["page"])][0] for r in rows)
            d_fld = sum(dels[(cfg, r["doc_id"], r["page"])][1] for r in rows)
            rank.append([cfg, len(rows), errs / chars, st.mean(cer), st.median(cer),
                         st.mean(_f(r, "cer_lenient") for r in rows), st.mean(_f(r, "cer_native") for r in rows),
                         st.mean(_f(r, "wer") for r in rows), d_all, d_fld, st.median(secs) if secs else ""])
        rank.sort(key=lambda x: x[2])
        best_s = rank[0][0] if rank else None
        parts.append("## 2. Ranking konfiguracji — zestaw S (idealne rendery), wspólne strony\n")
        parts.append("CER mikro = suma błędów znakowych / suma znaków referencji. CER łagodny = bez wielkości liter i ogonków. "
                     "CER natywny = kolejność linii Tesseracta zamiast wierszy wizualnych (różnica ⇒ problem układu). "
                     "Pominięte = tokeny referencji, których OCR w ogóle nie zwrócił (np. zgubione linie pod kropkami do podpisu); "
                     "„w polach” = należące do wartości pól GT. Czas: patrz §7 (pomiar pod obciążeniem równoległym).\n")
        parts.append(md_table(["konfiguracja", "strony", "CER mikro", "CER śr.", "CER mediana", "CER łagodny", "CER natywny", "WER",
                               "pominięte", "pominięte w polach", "s/stronę"], rank) + "\n")

        # ------------------------------------------------------------ per typ, konfiguracje z pełnym pokryciem
        parts.append("## 3. CER per typ dokumentu i strona (wszystkie strony danej konfiguracji)\n")
        rows_t = []
        for cfg, pg in sorted(by_cfg.items(), key=lambda kv: -len(kv[1])):
            if len(pg) <= len(common) and cfg != best_s:
                continue
            groups = defaultdict(list)
            for r in pg.values():
                groups[r["label"]].append(r)
                groups["strony 1–2" if int(r["page"]) <= 2 else "strony 3+"].append(r)
            for g, rs in sorted(groups.items()):
                ch = sum(int(r["ref_chars"]) for r in rs)
                er = sum(int(r["char_errors"]) for r in rs)
                rows_t.append([cfg, g, len(rs), er / ch if ch else 0, st.mean(_f(r, "wer") for r in rs)])
        parts.append(md_table(["konfiguracja", "grupa", "strony", "CER mikro", "WER śr."], rows_t) + "\n")

        # ------------------------------------------------------------ D
        deg = [r for r in per_page if r["degrade"] != "none" or r["preproc"] != "none"]
        if deg:
            parts.append("## 4. Zestaw D (syntetycznie zdegradowane rendery) i preprocessing\n")
            g = defaultdict(list)
            for r in deg:
                g[r["config"]].append(r)
            rows_d = []
            for cfg, rs in g.items():
                ch = sum(int(r["ref_chars"]) for r in rs)
                er = sum(int(r["char_errors"]) for r in rs)
                rows_d.append([cfg, len(rs), er / ch if ch else 0, st.mean(_f(r, "wer") for r in rs)])
            rows_d.sort(key=lambda x: x[0])
            parts.append(md_table(["konfiguracja", "strony", "CER mikro", "WER śr."], rows_d) + "\n")

    # ---------------------------------------------------------------- survival
    parts.append("## 5. Przeżywalność wartości pól GT (A7/B1)\n")
    parts.append("L0 dokładnie · L1 łagodnie (wielkość liter/ogonki/spacje) · L2 rozmyto (≤1 edycja do 12 zn., ≤10% dłuższe) · L3 brak. "
                 "Na S/D mianownik = pola, których zapis jest w tekście referencyjnym. "
                 "**Porównuj tylko wiersze o tej samej liczbie pól** (siatka liczona na podzbiorze 10 spraw = 296 pól, "
                 "kandydaci na całym S = 1780 pól).\n")
    best_k = None
    for set_ in ("S", "K"):
        summ = read_csv(OUT / f"survival_summary_{set_}.csv")
        if not summ:
            continue
        allrows = [r for r in summ if r["field_class"] == "WSZYSTKIE" and r.get("layout", "rows") == "rows"]
        allrows.sort(key=lambda r: (r["set"], -float(r["L0+L1"]), -float(r["L0"])))
        lay = {(r["set"], r["config"]): r for r in summ if r["field_class"] == "WSZYSTKIE" and r.get("layout") == "native"}
        parts.append(f"### Zestaw {set_}{' + D' if set_ == 'S' else ''} — wszystkie pola (tekst w wierszach wizualnych; w nawiasie: kolejność natywna Tesseracta)\n")
        parts.append(md_table(["zestaw", "konfiguracja", "pola", "L0", "L0+L1", "L0+L1+L2", "L3", "L0+L1 natywnie"],
                              [[r["set"], r["config"], r["n"], pct(float(r["L0"])), pct(float(r["L0+L1"])),
                                pct(float(r["L0+L1+L2"])), pct(float(r["L3"])),
                                pct(float(lay[(r["set"], r["config"])]["L0+L1"])) if (r["set"], r["config"]) in lay else ""]
                               for r in allrows]) + "\n")
        top = [r for r in allrows if r["set"] == set_][:1]
        if top:
            bc = top[0]["config"]
            if set_ == "K":
                best_k = bc
            cls_rows = [r for r in summ if r["config"] == bc and r["set"] == set_ and r["field_class"] != "WSZYSTKIE"
                        and r.get("layout", "rows") == "rows"]
            parts.append(f"Najlepsza konfiguracja na {set_}: `{bc}` — per klasa pola:\n")
            parts.append(md_table(["klasa pola", "pola", "L0", "L1", "L2", "L3"],
                                  [[r["field_class"], r["n"], pct(float(r["L0"])), pct(float(r["L1"])), pct(float(r["L2"])), pct(float(r["L3"]))]
                                   for r in sorted(cls_rows, key=lambda r: float(r["L0"]))]) + "\n")
        det = [r for r in read_csv(OUT / f"survival_{set_}.csv") if r.get("layout", "rows") == "rows"]
        miss = [r for r in det if top and r["config"] == top[0]["config"] and r["level"] in ("L2", "L3")]
        if miss:
            parts.append(f"Pola L2/L3 w `{top[0]['config']}` (max 40):\n")
            parts.append(md_table(["dokument", "pole", "wartość GT", "poziom", "dyst.", "najbliższe okno OCR (squash)"],
                                  [[r["doc_id"], r["path"], r["value"], r["level"], r["distance"], r["window"]] for r in miss[:40]]) + "\n")

    nir = read_csv(OUT / "fields_not_in_ref.csv")
    if nir:
        cc = Counter(r["path"].split("[")[0] + "." + r["path"].split(".")[-1] for r in nir)
        parts.append("### Pola GT, których zapisu nie ma w tekście referencyjnym (wejście do audytu z kroku 3)\n")
        parts.append(md_table(["pole", "liczba"], [[k, v] for k, v in cc.most_common()]) + "\n")
        parts.append(md_table(["dokument", "pole", "wartość GT"], [[r["doc_id"], r["path"], r["value"]] for r in nir[:25]]) + "\n")

    # ---------------------------------------------------------------- błędy dla najlepszej konfiguracji S
    if errors and best_s:
        er = [e for e in errors if e["config"] == best_s]
        parts.append(f"## 6. Błędy OCR — `{best_s}` (zestaw S)\n")
        parts.append(f"Operacji błędu: {len(er)}.\n")
        et = Counter(t for e in er for t in e["error_type"].split("|"))
        tt = Counter(e["token_type"] for e in er)
        parts.append(md_table(["typ błędu", "liczba"], et.most_common()) + "\n")
        parts.append(md_table(["typ tokenu", "liczba"], tt.most_common()) + "\n")
        fk = Counter(e["in_field"] or "(poza polami GT)" for e in er)
        parts.append(md_table(["pole GT", "błędów"], fk.most_common(25)) + "\n")
        lab = Counter(e["label"] for e in er)
        parts.append(md_table(["typ dokumentu", "błędów"], lab.most_common()) + "\n")
        conf = [r for r in read_csv(OUT / "char_confusion.csv") if r["config"] == best_s][:30]
        parts.append("Najczęstsze pomyłki znaków (ref → ocr):\n")
        parts.append(md_table(["ref", "ocr", "liczba"], [[r["ref"], r["ocr"], r["count"]] for r in conf]) + "\n")
        bad = Counter(e["ref"] for e in er if e["ref"])
        parts.append("Najczęściej psute tokeny referencji:\n")
        parts.append(md_table(["token", "liczba"], bad.most_common(30)) + "\n")
        parts.append("Przykłady (max 40, priorytet: błędy w polach GT):\n")
        ex = sorted(er, key=lambda e: (e["in_field"] == "", e["doc_id"]))[:40]
        parts.append(md_table(["dokument", "str.", "rodzaj", "ref", "ocr", "typ", "pole", "conf"],
                              [[e["doc_id"], e["page"], e["kind"], e["ref"], e["ocr"], e["error_type"], e["in_field"], e["conf"]] for e in ex]) + "\n")

        cb = [r for r in read_csv(OUT / "conf_bins.csv") if r["config"] == best_s]
        if cb:
            parts.append("### Confidence a błędy (A8)\n")
            parts.append(md_table(["klasa tokenu", "przedział conf", "tokeny", "błędne", "odsetek błędnych"],
                                  [[r["token_class"], r["bin"], r["n_tokens"], r["n_wrong"], r["error_rate"]] for r in cb]) + "\n")
        hm = [r for r in read_csv(OUT / "heatmap.csv") if r["config"] == best_s]
        if hm:
            grid = {(int(r["gx"]), int(r["gy"])): (int(r["n_tokens"]), int(r["n_err"])) for r in hm}
            lines = ["```", "odsetek błędnych tokenów referencji [%] na siatce 10×10 strony (wiersz = wysokość, kolumna = szerokość)"]
            for gy in range(10):
                cells = []
                for gx in range(10):
                    n, e = grid.get((gx, gy), (0, 0))
                    cells.append(f"{100 * e / n:5.1f}" if n else "    .")
                lines.append(" ".join(cells))
            lines.append("```")
            parts.append("### Położenie błędów na stronie\n" + "\n".join(lines) + "\n")

    # ---------------------------------------------------------------- czas
    if per_page:
        tcfg = defaultdict(list)
        for r in per_page:
            if r["ocr_seconds"]:
                tcfg[r["config"]].append(float(r["ocr_seconds"]))
        tm = read_csv(OUT / "timing.csv")
        if tm:
            g = defaultdict(list)
            for r in tm:
                g[(r["config"], r["mode"], r["set"])].append(float(r["ocr_s"]))
            parts.append("## 7a. Czas OCR — czysty pomiar sekwencyjny (`timing`)\n")
            parts.append("omp1 = 1 wątek Tesseracta (tryb wsadowy), ompN = domyślna liczba wątków. Bez renderu PDF.\n")
            parts.append(md_table(["konfiguracja", "wątki", "zestaw", "stron", "mediana s/str.", "max s/str."],
                                  [[c, m, s, len(v), st.median(v), max(v)] for (c, m, s), v in sorted(g.items())]) + "\n")
        parts.append("## 7. Czas OCR zapisany przy przebiegach (pod obciążeniem równoległym — tylko orientacyjnie)\n")
        parts.append(md_table(["konfiguracja", "stron", "mediana s/str.", "p95 s/str."],
                              [[k, len(v), st.median(v), sorted(v)[int(0.95 * (len(v) - 1))]] for k, v in sorted(tcfg.items())]) + "\n")

    parts.append("## 8. Wybór automatyczny\n")
    parts.append(f"- najniższy CER na S (wspólne strony): `{best_s}`\n- najwyższa przeżywalność L0+L1 na skanach K: `{best_k}`\n")
    out = OUT / "summary.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"zapisano {out}")
