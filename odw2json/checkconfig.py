"""`python -m odw2json check` — walidacja configu (nowy typ dokumentu dodaje się bez zmian w kodzie,
więc błędy w configu muszą być wykrywane przed uruchomieniem)."""

from __future__ import annotations

import re

from .config import CONFIG_DIR, dictionary, doc_types, patterns, settings
from .normalize import NORMALIZERS
from .patterns import compile_pattern
from .schema import SOURCES, iter_leaves, skeleton, validate


def check() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    st = settings()
    for k in ("text", "ocr", "layout", "classification", "llm", "output"):
        if k not in st:
            errors.append(f"settings.yaml: brak sekcji {k}")
    for i, p in enumerate((st.get("llm") or {}).get("providers") or []):
        for k in ("name", "api_base_env", "api_key_env", "model_env"):
            if not p.get(k):
                errors.append(f"settings.yaml: llm.providers[{i}]: brak {k}")
    from . import llm  # import lokalny: llm ładuje .env
    if not llm.available():
        warns.append("LLM niedostępny (brak skonfigurowanego dostawcy w .env albo ODW_LLM=off) — działa tylko tryb awaryjny regex")
    cl_cfg = st.get("classification", {})
    if cl_cfg.get("mode", "llm_verify") not in ("llm_verify", "regex_only"):
        errors.append(f"settings.yaml: classification.mode = {cl_cfg.get('mode')}")
    prompt = (cl_cfg.get("llm") or {}).get("prompt", "klasyfikacja.md")
    pf = CONFIG_DIR / "prompts" / prompt
    if not pf.exists():
        errors.append(f"brak promptu klasyfikacji prompts/{prompt}")
    else:
        txt = pf.read_text(encoding="utf-8")
        for k in ("=== SYSTEM ===", "=== USER ===", "{{typy}}", "{{tekst}}", "{{format_json}}"):
            if k not in txt:
                errors.append(f"prompts/{prompt}: brak {k}")
    for name, p in patterns().items():
        try:
            re.compile(p)
        except re.error as e:
            errors.append(f"patterns.yaml @{name}: {e}")
    types = doc_types()
    if not types:
        errors.append("brak typów w config/types/")
    for name, dt in types.items():
        where = f"types/{dt.dir.name}"
        cl = dt.classification
        if cl.get("method", "hybrid") not in ("regex", "semantic", "hybrid"):
            errors.append(f"{where}: classification.method = {cl.get('method')}")
        for group in ("signals", "negative_signals"):
            for s in cl.get(group, []):
                if "id" not in s or "pattern" not in s:
                    errors.append(f"{where}: {group}: sygnał bez id/pattern: {s}")
                    continue
                try:
                    compile_pattern(s["pattern"], s.get("ocr_tolerant", cl.get("ocr_tolerant", True)))
                except (re.error, KeyError) as e:
                    errors.append(f"{where}: {group}.{s['id']}: {e}")
        if not dt.description:
            errors.append(f"{where}: brak description (LLM klasyfikuje na podstawie opisów typów)")
        reqs = (cl.get("semantic") or {}).get("requirements") or []
        if not reqs:
            warns.append(f"{where}: brak classification.semantic.requirements (LLM ocenia typ według wymagań)")
        elif not any(r.get("essential", True) for r in reqs):
            warns.append(f"{where}: żadne wymaganie nie jest konieczne (essential) — brak kontroli spójności")
        for r in reqs:
            if not isinstance(r, dict) or not r.get("id") or not r.get("text"):
                errors.append(f"{where}: semantic.requirements: wymaganie bez id/text: {r}")
        if not (cl.get("semantic") or {}).get("not_to_confuse_with"):
            warns.append(f"{where}: brak classification.semantic.not_to_confuse_with (pomaga LLM odróżnić podobne pisma)")
        if not cl.get("signals"):
            warns.append(f"{where}: brak sygnałów regex — typ bez dowodów leksykalnych przyjmowany tylko przy wysokiej pewności LLM")
        sections = dt.raw.get("sections", {}) or {}
        for sname, sec in sections.items():
            for k in ("start", "end"):
                if sec.get(k):
                    try:
                        compile_pattern(sec[k])
                    except (re.error, KeyError) as e:
                        errors.append(f"{where}: sections.{sname}.{k}: {e}")
        calls = dt.raw.get("llm_calls", {}) or {}
        for cname, call in calls.items():
            if call.get("prompt") and not (dt.dir / "prompts" / call["prompt"]).exists():
                errors.append(f"{where}: llm_calls.{cname}: brak pliku prompts/{call['prompt']}")
            tpl = CONFIG_DIR / "prompts" / call.get("template", "ekstrakcja.md")
            if not tpl.exists():
                errors.append(f"{where}: llm_calls.{cname}: brak szablonu prompts/{tpl.name}")
            for k in (call.get("extra") or {}):
                if not str(k).startswith("_"):
                    errors.append(f"{where}: llm_calls.{cname}.extra: klucz {k!r} musi zaczynać się od '_'")
        if not dt.schema:
            errors.append(f"{where}: brak schema.json")
            continue
        leaves = list(iter_leaves(dt.schema))
        keys = {lf.key for lf in leaves}
        for lf in leaves:
            sp, at = lf.spec, f"{where}/schema.json {lf.path}"
            if "type" not in sp:
                errors.append(f"{at}: brak type")
            if not sp.get("description"):
                errors.append(f"{at}: brak description")
            if sp.get("x-source") not in SOURCES:
                errors.append(f"{at}: x-source = {sp.get('x-source')!r} (dozwolone: {sorted(SOURCES)})")
            for n in sp.get("x-normalize", []):
                if n not in NORMALIZERS:
                    errors.append(f"{at}: nieznany normalizator {n}")
            if sp.get("x-validate"):
                try:
                    re.compile(sp["x-validate"])
                except re.error as e:
                    errors.append(f"{at}: x-validate: {e}")
            for c in sp.get("x-candidates", []):
                for k in ("label", "pattern"):
                    if c.get(k):
                        try:
                            compile_pattern(c[k])
                        except (re.error, KeyError) as e:
                            errors.append(f"{at}: x-candidates.{k}: {e}")
                v = c.get("value")
                if v and v.startswith("@") and v[1:] not in patterns():
                    errors.append(f"{at}: nieznany wzorzec {v}")
                elif v and not v.startswith("@"):
                    try:
                        compile_pattern(v)
                    except (re.error, KeyError) as e:
                        errors.append(f"{at}: x-candidates.value: {e}")
            if sp.get("x-dictionary"):
                try:
                    dictionary(sp["x-dictionary"])
                except FileNotFoundError:
                    errors.append(f"{at}: brak słownika dictionaries/{sp['x-dictionary']}.json")
            if sp.get("x-derived-from") and sp["x-derived-from"] not in keys:
                errors.append(f"{at}: x-derived-from wskazuje nieistniejące pole {sp['x-derived-from']}")
            if sp.get("x-section") and sp["x-section"] not in sections:
                errors.append(f"{at}: nieznana sekcja {sp['x-section']}")
            if sp.get("x-llm-call") and sp["x-llm-call"] not in calls:
                errors.append(f"{at}: nieznane wywołanie LLM {sp['x-llm-call']}")
            if sp.get("x-source") != "derived" and not sp.get("x-llm-call"):
                warns.append(f"{at}: pole bez x-llm-call — LLM go nie wypełni (tylko kandydaci regex w trybie awaryjnym)")
            if sp.get("x-evidence"):
                extra = (calls.get(sp.get("x-llm-call")) or {}).get("extra") or {}
                if sp["x-evidence"] not in extra:
                    errors.append(f"{at}: x-evidence {sp['x-evidence']!r} nie jest polem extra wywołania {sp.get('x-llm-call')}")
            if sp.get("x-source") in ("verbatim", "normalized") and not sp.get("x-llm-call") and not sp.get("x-candidates"):
                warns.append(f"{at}: brak źródła wartości (ani x-llm-call, ani x-candidates)")
        sk = skeleton(dt.schema)
        errs = validate(sk, dt.schema)
        if errs:
            errors.append(f"{where}: szkielet z null nie przechodzi walidacji: {errs[:3]}")
    if not (CONFIG_DIR / "dictionaries").exists():
        errors.append("brak config/dictionaries/")
    return errors, warns
