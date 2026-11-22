"""Audyt GT względem schematów (docs/03_schematy_pol.md §7).

Dla każdej wartości GT ≠ null (dokumenty syntetyczne S i skany K) sprawdza, skąd da się ją wziąć:
  verbatim    — dosłowny podciąg tekstu (po zwinięciu spacji)
  normalized  — fragment tekstu po normalizatorach pola daje wartość GT (kandydaci x-candidates lub wzorce)
  odmiana     — imię/nazwisko występuje w tekście tylko w innej formie (rdzenie tokenów)
  fuzzy       — tylko z błędem ≤ 1–2 znaki (OCR)
  absent      — brak
  inferred    — pole wnioskowane (nie szukamy)
Dodatkowo: skuteczność reguł x-candidates (GT wśród kandydatów / kandydat nr 1), sumy kontrolne NIP/REGON/PESEL,
prefiks PL rachunków (dokument vs GT).

  .venv\\Scripts\\python -m tools.audit_gt     →  reports/audit_gt.md, reports/audit_gt.csv
"""

from __future__ import annotations

import re
import sys
import warnings
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

warnings.filterwarnings("ignore", category=FutureWarning)

from odw2json.config import APP_ROOT  # noqa: E402
from tools.ocr_bench.common import flatten, load_manifest, write_csv  # noqa: E402

OUT = APP_ROOT / "reports"


def _cw(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def nip_ok(d: str) -> bool:
    w = [6, 5, 7, 2, 3, 4, 5, 6, 7]
    return len(d) == 10 and sum(int(a) * b for a, b in zip(d, w)) % 11 == int(d[9])


def regon_ok(d: str) -> bool:
    if len(d) == 9:
        w = [8, 9, 2, 3, 4, 5, 6, 7]
        return sum(int(a) * b for a, b in zip(d, w)) % 11 % 10 == int(d[8])
    if len(d) == 14:
        w = [2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8]
        return sum(int(a) * b for a, b in zip(d, w)) % 11 % 10 == int(d[13])
    return False


def pesel_ok(d: str) -> bool:
    w = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    return len(d) == 11 and (10 - sum(int(a) * b for a, b in zip(d, w)) % 10) % 10 == int(d[10])


def audit_doc(doc_id: str, pdf: str, gt_path: str, label: str, set_: str) -> list[dict]:
    import json

    from rapidfuzz import fuzz

    from odw2json import normalize
    from odw2json.candidates import find_candidates
    from odw2json.config import doc_types
    from odw2json.schema import iter_leaves
    from odw2json.text import DocumentText

    dt = doc_types()[label]
    specs = {lf.key: lf.spec for lf in iter_leaves(dt.schema)}
    gt = json.loads(open(gt_path, encoding="utf-8").read())
    doc = DocumentText(pdf)
    text = doc.text(dt.pages)
    text_cw = _cw(text)
    rows = []
    for path, val in flatten(gt):
        if val is None:
            continue
        key = re.sub(r"\[\d+\]", "", path)
        spec = specs.get(key)
        if spec is None:
            rows.append({"doc_id": doc_id, "set": set_, "label": label, "path": path, "value": val, "result": "brak_w_schemacie"})
            continue
        src = spec.get("x-source")
        r = {"doc_id": doc_id, "set": set_, "label": label, "path": path, "key": key, "value": val, "x_source": src,
             "ocr": doc.any_ocr}
        if src == "derived" or (src == "inferred" and not spec.get("x-candidates")):
            r["result"] = "inferred"
            rows.append(r)
            continue
        norm = spec.get("x-normalize", [])
        is_account = "account" in norm
        gt_norm = normalize.apply(val, norm)
        cmp = (lambda v: re.sub(r"^[A-Z]{2}", "", str(v))) if is_account else (lambda v: v)
        cands = find_candidates(spec, text)
        cvals = [cmp(c.value) for c in cands]
        r["n_candidates"] = len(cands)
        r["gt_in_candidates"] = cmp(gt_norm) in cvals if cands else ""
        r["gt_is_first"] = bool(cands) and cvals[0] == cmp(gt_norm)
        sval = _cw(val)
        if isinstance(val, str) and sval in text_cw:
            r["result"] = "verbatim"
        elif cands and cmp(gt_norm) in cvals:
            r["result"] = "normalized"
        elif isinstance(val, str) and key.endswith("imie_nazwisko"):
            toks = sval.split()
            stems = [t[: max(4, len(t) - 3)].lower() for t in toks]
            low = text_cw.lower()
            r["result"] = "odmiana" if all(s in low for s in stems) else "absent"
        else:
            r["result"] = "absent"
        if r["result"] == "absent" and isinstance(val, (str, int, float)):
            al = fuzz.partial_ratio_alignment(_cw(str(val)).lower(), text_cw.lower())
            win = text_cw[al.dest_start : al.dest_end]
            r["best_window"] = win
            r["similarity"] = round(al.score, 1)
            if al.score >= 90:
                r["result"] = "fuzzy"
        if is_account:
            d = re.sub(r"\D", "", str(val))
            m = re.search(r"(PL)?\s?" + r"\s?".join(d[:6]), text)
            r["pl_in_doc"] = bool(m and m.group(1))
            r["pl_in_gt"] = str(val).startswith("PL")
        if key.endswith(".nip"):
            r["checksum_ok"] = nip_ok(str(val))
        elif key.endswith(".regon"):
            r["checksum_ok"] = regon_ok(str(val))
        elif key.endswith(".pesel"):
            r["checksum_ok"] = pesel_ok(str(val))
        rows.append(r)
    return rows


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    docs = [d for d in load_manifest() if d.gt and d.label in ("odwolanie", "pelnomocnictwo", "przelew")]
    rows: list[dict] = []
    with ProcessPoolExecutor(max_workers=12) as ex:
        for res in ex.map(audit_doc, [d.doc_id for d in docs], [d.pdf for d in docs], [d.gt for d in docs],
                          [d.label for d in docs], [d.set for d in docs]):
            rows.extend(res)
    fields = ["doc_id", "set", "label", "path", "key", "value", "x_source", "result", "n_candidates", "gt_in_candidates",
              "gt_is_first", "best_window", "similarity", "pl_in_doc", "pl_in_gt", "checksum_ok", "ocr"]
    write_csv(OUT / "audit_gt.csv", rows, fields)

    md = ["# Audyt GT względem schematów (krok 3)\n",
          f"Dokumenty z GT: {len(docs)} (S: {sum(d.set == 'S' for d in docs)}, skany K: {sum(d.set == 'K' for d in docs)}), "
          f"wartości ≠ null: {len(rows)}. Tekst: warstwa tekstowa / OCR (konfiguracja z kroku 1), pierwsze `pages` stron typu.\n",
          "Wyniki: `verbatim` = dosłownie w tekście; `normalized` = przez kandydatów i normalizatory pola; `odmiana` = imię/nazwisko "
          "w innej formie; `fuzzy` = z błędem OCR; `absent` = brak; `inferred` = pole wnioskowane.\n"]
    for set_ in ("S", "K"):
        g = defaultdict(Counter)
        cand = defaultdict(lambda: [0, 0, 0])
        for r in rows:
            if r["set"] != set_ or "key" not in r:
                continue
            g[(r["key"], r["x_source"])][r["result"]] += 1
            if r.get("gt_in_candidates") not in (None, ""):
                c = cand[r["key"]]
                c[0] += 1
                c[1] += bool(r["gt_in_candidates"])
                c[2] += bool(r["gt_is_first"])
        md.append(f"## Zestaw {set_}\n")
        md.append("| pole | x-source | n | verbatim | normalized | odmiana | fuzzy | absent | inferred | kandydaci: GT wśród | GT = nr 1 |")
        md.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for (k, src), c in sorted(g.items()):
            n = sum(c.values())
            cc = cand.get(k)
            md.append(f"| {k} | {src} | {n} | {c['verbatim']} | {c['normalized']} | {c['odmiana']} | {c['fuzzy']} | {c['absent']} | "
                      f"{c['inferred']} | {f'{cc[1]}/{cc[0]}' if cc else '—'} | {f'{cc[2]}/{cc[0]}' if cc else '—'} |")
        md.append("")
    # niezgodności x-source
    mism = Counter()
    for r in rows:
        if r.get("x_source") == "verbatim" and r.get("result") == "normalized":
            mism[(r["key"], "verbatim → znajdowane tylko po normalizacji")] += 1
        if r.get("x_source") == "normalized" and r.get("result") == "verbatim" and not r["key"].endswith("imie_nazwisko"):
            mism[(r["key"], "normalized → występuje dosłownie (normalizacja nie zmienia wartości)")] += 1
    md.append("## Zgodność x-source z danymi\n")
    if mism:
        md.append("| pole | obserwacja | liczba |\n|---|---|---|")
        for (k, o), n in mism.most_common():
            md.append(f"| {k} | {o} | {n} |")
    else:
        md.append("Brak niezgodności.")
    md.append("\n## Sumy kontrolne w GT\n\n| pole | poprawne | wszystkie |\n|---|---|---|")
    ck = defaultdict(lambda: [0, 0])
    for r in rows:
        if r.get("checksum_ok") not in (None, ""):
            k = r["key"].split(".")[-1]
            ck[k][0] += bool(r["checksum_ok"])
            ck[k][1] += 1
    for k, (ok, n) in sorted(ck.items()):
        md.append(f"| {k} | {ok} ({100 * ok / n:.0f}%) | {n} |")
    md.append("\n## Prefiks PL rachunków: dokument vs GT\n\n| PL w dokumencie | PL w GT | liczba |\n|---|---|---|")
    pl = Counter((r.get("pl_in_doc"), r.get("pl_in_gt")) for r in rows if r.get("pl_in_doc") not in (None, ""))
    for (a, b), n in sorted(pl.items(), key=lambda kv: str(kv[0])):
        md.append(f"| {a} | {b} | {n} |")
    bad = [r for r in rows if r.get("result") in ("absent", "fuzzy")]
    md.append(f"\n## Wartości absent / fuzzy ({len(bad)})\n")
    if bad:
        md.append("| dokument | pole | wartość GT | wynik | najbliższy fragment | podob. |\n|---|---|---|---|---|---|")
        for r in bad[:80]:
            md.append(f"| {r['doc_id']} | {r['path']} | {str(r['value'])[:60]} | {r['result']} | {str(r.get('best_window', ''))[:70]} | {r.get('similarity', '')} |")
    (OUT / "audit_gt.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"zapisano {OUT / 'audit_gt.md'} ({len(rows)} wartości)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
