"""
AyurMitra — Knowledge Graph v2 builder (Phase 3)
================================================
Deterministic:  python -m app.core.kg_builder
Outputs (Data/processed/):  knowledge_graph_v2.pkl, kg_v2.json, kg_build_report.md
The original 24-node graph is preserved untouched as knowledge_graph.pkl and copied
to knowledge_graph_v1.pkl.

Every edge carries: relation, source_id, locator, review_status, confidence.
review_status vocabulary
  extracted_from_source        – the relation is a row/column of a source file (locator = that row/page)
  auto_matched_by_code         – link between a project concept and a source term by deterministic
                                 string matching (needs expert review)
  grounded_by_code_text        – an old hand-written v1 relation that code found stated in a WHO
                                 description (locator = that term); needs expert review
  project_mapping_unreviewed   – project-written mapping with no source locator (symptom → dosha)
  unverified                   – old v1 relation whose claimed locator did not check out (audit F4)
Wording rule: "traditionally_used_for" / "described_in" — never "treats" / "cures".
"""
from __future__ import annotations

import collections
import json
import pickle
import re
import shutil
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx
import pandas as pd

from app.config import (
    DATA_PROC, KG_PKL, KG_V1_PKL, KG_V2_PKL, KG_V2_JSON, NAMASTE_XLSX, PLANT_TSV, THERAPEUTIC_TSV,
    FORMULATIONS_TSV, TERMINOLOGY_JSON,
)
from app.core.who_extract import extract_who_terms

REPORT_MD = DATA_PROC / "kg_build_report.md"
SRC_WHO, SRC_NAMASTE = "WHO_9789240064935", "NAMASTE_ayu-sat-table-a"
SRC_IMPPAT, SRC_API = "IMPPAT_2.0", "API_SingleHerbalFormulations"
V1_HERBS = {"Ashwagandha", "Triphala", "Tulsi", "Neem", "Brahmi", "Shatavari", "Guggulu", "Amalaki", "Haritaki", "Bibhitaki"}

# ── deterministic transliteration helpers (no regex-module dependency) ───────
_SLP1_IAST = {
    "A": "ā", "I": "ī", "U": "ū", "f": "ṛ", "F": "ṝ", "x": "ḷ", "X": "ḹ", "E": "ai", "O": "au",
    "M": "ṃ", "H": "ḥ", "~": "m̐", "K": "kh", "G": "gh", "N": "ṅ", "C": "ch", "J": "jh", "Y": "ñ",
    "w": "ṭ", "W": "ṭh", "q": "ḍ", "Q": "ḍh", "R": "ṇ", "T": "th", "D": "dh", "P": "ph", "B": "bh",
    "S": "ś", "z": "ṣ", "'": "'",
}


def slp1_to_iast(s: str) -> str:
    return "".join(_SLP1_IAST.get(ch, ch) for ch in (s or ""))


def fold(s: str) -> str:
    """ASCII-fold for matching: strip diacritics, lower, unify common spelling variants."""
    s = re.sub(r"_\d+$", "", (s or "").strip())  # API variant suffix: Āmalakī_1.replace("ṛ", "ri").replace("Ṛ", "ri").replace("ṝ", "ri")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("ṃ", "m").replace("ḥ", "h")
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace("sh", "s").replace("w", "v").replace("aa", "a").replace("ee", "i").replace("oo", "u")
    return s


def fold_word(s: str) -> str:
    """fold + drop Sanskrit nominative endings (-ah, -am, -h, -m) for single words."""
    f = fold(s)
    f = re.sub(r"(h|m|s)$", "", f) if len(f) > 3 else f
    return f


def to_script(iast: str, script: str) -> Optional[str]:
    try:
        from indic_transliteration import sanscript
        target = sanscript.DEVANAGARI if script == "deva" else sanscript.KANNADA
        return sanscript.transliterate(iast, sanscript.IAST, target)
    except Exception:
        return None


# ── builder ──────────────────────────────────────────────────────────────────
class KGBuilder:
    def __init__(self):
        self.g = nx.DiGraph()
        self.log: Dict[str, Any] = collections.OrderedDict()
        self.audit_rows: List[Dict[str, Any]] = []

    def node(self, nid: str, node_type: str, **attrs):
        base = {"node_type": node_type, "label_en": None, "label_iast": None, "label_sa_deva": None,
                "label_hi": None, "label_kn": None, "label_roman": None, "aliases": [], "definition": None,
                "source_id": None, "locator": None, "review_status": "extracted_from_source", "confidence": 1.0}
        if nid in self.g:
            cur = self.g.nodes[nid]
            for k, v in attrs.items():
                if k == "aliases":
                    cur["aliases"] = sorted(set(cur.get("aliases", [])) | set(v or []))
                elif v is not None and cur.get(k) in (None, "", []):
                    cur[k] = v
            return
        base.update({k: v for k, v in attrs.items() if v is not None})
        base["aliases"] = sorted(set(base.get("aliases") or []))
        self.g.add_node(nid, **base)

    def edge(self, u: str, v: str, relation: str, source_id: str, locator: Optional[str],
             review_status: str, confidence: float, **attrs):
        if u not in self.g or v not in self.g:
            return
        if self.g.has_edge(u, v):
            d = self.g.edges[u, v]
            if relation not in d.get("relations", [d["relation"]]):
                d.setdefault("relations", [d["relation"]]).append(relation)
            return
        self.g.add_edge(u, v, relation=relation, source_id=source_id, locator=locator,
                        review_status=review_status, confidence=confidence, **attrs)

    # 1. project concepts (canonical names the matcher detects)
    def add_concepts(self):
        from app.core.matcher import CANONICAL_TO_HINDI, CANONICAL_TO_KANNADA
        inv = json.loads(Path(TERMINOLOGY_JSON).read_text(encoding="utf-8"))
        seeds = {e["canonical_term"]: e for e in inv if e.get("source_id") == "SEED"}
        names = sorted(set(seeds) | set(CANONICAL_TO_HINDI) | set(CANONICAL_TO_KANNADA))
        for name in names:
            e = seeds.get(name, {})
            self.node(f"CONCEPT:{name}", "Dosha" if name in ("Vata", "Pitta", "Kapha") else "Concept",
                      label_en=name, label_roman=name,
                      label_hi=CANONICAL_TO_HINDI.get(name), label_kn=CANONICAL_TO_KANNADA.get(name),
                      label_source="project lexicon (app/core/matcher.py) — native-speaker review pending",
                      aliases=e.get("aliases", []) + [name.lower()],
                      project_definition=e.get("definition") or None,
                      source_id="AyurMitra_terminology_inventory",
                      locator=f"terminology_inventory.json {e.get('concept_id', 'matcher map')}",
                      review_status="project_concept_unreviewed", confidence=0.5)
        self.log["concepts"] = len(names)

    # 2. NAMASTE
    def add_namaste(self):
        df = pd.read_excel(NAMASTE_XLSX)
        by_tid = {}
        for i, r in df.iterrows():
            code, word = str(r["Code"]).strip(), str(r["Word"]).strip()
            iast = slp1_to_iast(word)
            sd = str(r.get("Short Defination", "") or "").strip()
            ld = str(r.get("Long Defination", "") or "").strip()
            nid = f"NAMASTE:{code}"
            by_tid[int(r["t_id"])] = nid
            self.node(nid, "NAMASTETerm", label_en=sd if sd and sd != "nan" else None, label_iast=iast,
                      label_sa_deva=to_script(iast, "deva"), label_roman=word,
                      definition=ld if ld and ld != "nan" else None, namaste_code=code, namaste_word_slp1=word,
                      source_id=SRC_NAMASTE, locator=f"{NAMASTE_XLSX.name} row {i + 2} (Code {code}, t_id {int(r['t_id'])})",
                      aliases=[fold_word(iast)])
        for i, r in df.iterrows():
            child, parent = by_tid.get(int(r["t_id"])), by_tid.get(int(r["parent_id"]) if pd.notna(r["parent_id"]) else -1)
            if child and parent and child != parent:
                self.edge(child, parent, "part_of", SRC_NAMASTE, f"{NAMASTE_XLSX.name} row {i + 2} parent_id",
                          "extracted_from_source", 1.0)
        self.log["namaste_terms"] = len(df)

    # 3. WHO
    def add_who(self):
        data = extract_who_terms()
        for s in data["sections"]:
            nid = f"WHO:SEC-{s['section_id']}"
            self.node(nid, "WHOSection", label_en=s["title"], source_id=SRC_WHO,
                      locator=f"section {s['section_id']}, PDF p.{s['pdf_page']} (printed p.{s['printed_page']})",
                      pdf_page=s["pdf_page"], printed_page=s["printed_page"])
        for s in data["sections"]:
            parent = s["section_id"].rsplit(".", 1)[0] if "." in s["section_id"] else None
            if parent and f"WHO:SEC-{parent}" in self.g:
                self.edge(f"WHO:SEC-{s['section_id']}", f"WHO:SEC-{parent}", "part_of", SRC_WHO,
                          f"section numbering {s['section_id']}", "extracted_from_source", 1.0)
        for t in data["terms"]:
            iast = t["iast"] or None
            first_iast = re.split(r"[,/;]", iast)[0].strip() if iast else None
            nid = f"WHO:{t['term_id']}"
            self.node(nid, "WHOTerm", label_en=t["english"] or None, label_iast=iast,
                      label_sa_deva=to_script(first_iast, "deva") if first_iast else None,
                      label_kn_script_sanskrit=to_script(first_iast, "kn") if first_iast else None,
                      definition=t["description"] or None, who_term_id=t["term_id"],
                      pdf_page=t["pdf_page"], printed_page=t["printed_page"], source_id=SRC_WHO,
                      locator=f"{t['term_id']}, PDF p.{t['pdf_page']} (printed p.{t['printed_page']})",
                      aliases=[fold_word(x) for x in re.split(r"[,/;]", iast or "") if x.strip()])
            if t["section_id"] and f"WHO:SEC-{t['section_id']}" in self.g:
                self.edge(nid, f"WHO:SEC-{t['section_id']}", "part_of", SRC_WHO,
                          f"{t['term_id']} listed under section {t['section_id']}", "extracted_from_source", 1.0)
        self.log["who_terms"], self.log["who_sections"] = data["n_terms"], data["n_sections"]
        self.log["who_engine"] = data["engine"]
        return data

    # 4. concept ↔ WHO / NAMASTE links by deterministic matching
    def link_concepts(self, who):
        concepts = [n for n, d in self.g.nodes(data=True) if n.startswith("CONCEPT:")]
        who_terms = [(n, d) for n, d in self.g.nodes(data=True) if d["node_type"] == "WHOTerm"]
        nam = [(n, d) for n, d in self.g.nodes(data=True) if d["node_type"] == "NAMASTETerm"]
        sec = [(n, d) for n, d in self.g.nodes(data=True) if d["node_type"] == "WHOSection"]
        links = 0
        for c in concepts:
            cd = self.g.nodes[c]
            keys = {fold_word(cd["label_en"])} | {fold_word(a) for a in cd["aliases"] if len(a) >= 3}
            keys = {k for k in keys if len(k) >= 3}
            best_def = None
            for n, d in who_terms:
                head = fold_word((d["label_en"] or "").split(",")[0])
                iasts = set(d["aliases"])
                if head in keys or (iasts & keys):
                    self.edge(c, n, "described_in", SRC_WHO, d["locator"], "auto_matched_by_code", 0.8,
                              match_rule="WHO English-term head or IAST form equals concept alias")
                    links += 1
                    if best_def is None and d.get("definition") and head in keys:
                        best_def = (d["definition"], d["locator"])
            for n, d in sec:
                if fold_word(d["label_en"] or "") in keys:
                    self.edge(c, n, "described_in", SRC_WHO, d["locator"], "auto_matched_by_code", 0.8,
                              match_rule="WHO section title equals concept name")
                    links += 1
            for n, d in nam:
                if set(d["aliases"]) & keys:
                    self.edge(c, n, "described_in", SRC_NAMASTE, d["locator"], "auto_matched_by_code", 0.7,
                              match_rule="NAMASTE SLP1 word (folded) equals concept alias")
                    links += 1
            # Herb concepts only (homonyms: Kasa = cough vs plant Kāsa; Meda = fat tissue vs plant Medā)
            is_herb = c[8:] in V1_HERBS or re.search(r"\b(herb|plant|fruit|resin|tree)\b", cd.get("project_definition") or "", re.I)
            if is_herb:
                concept_forms = {fold(cd["label_en"])} | {fold(a) for a in cd["aliases"]}
                plant_hits = []
                for n, d in self.g.nodes(data=True):
                    if d["node_type"] != "Plant":
                        continue
                    via_api = {fold(a) for a in d.get("api_names", [])} & concept_forms
                    via_common = {fold(a) for a in d.get("common_names", [])} & concept_forms
                    if via_api or via_common:
                        plant_hits.append((n, d, "API (Ayurvedic Pharmacopoeia) name" if via_api else "IMPPAT common name"))
                for n, d, how in plant_hits:
                    self.edge(c, n, "refers_to_plant", SRC_API if how.startswith("API") else SRC_IMPPAT, d["locator"],
                              "auto_matched_by_code", 0.8 if len(plant_hits) == 1 else 0.5,
                              match_rule=f"concept name equals the plant's {how}",
                              ambiguity_note=(f"name matches {len(plant_hits)} different plants in the source data"
                                              if len(plant_hits) > 1 else None))
                    links += 1
            if best_def:
                cd["definition"], cd["definition_locator"] = best_def[0], best_def[1]
                cd["definition_source"] = SRC_WHO
        self.log["concept_source_links"] = links

    # 5. IMPPAT plants, therapeutic uses, API formulations
    def add_imppat(self):
        plants = pd.read_csv(PLANT_TSV, sep="\t", dtype=str).fillna("")
        name_to_pid = {}
        for i, r in plants.iterrows():
            pid = r["Plant_identifier"]
            syn = [s.strip() for s in r["Synonymous names"].split("|") if s.strip()]
            common = [s.strip() for s in re.split(r"[|,;]", r["Common_name"]) if s.strip()]
            self.node(f"PLANT:{pid}", "Plant", label_en=r["Indian_Medicinal_plant"],
                      botanical_name=r["Indian_Medicinal_plant"], family=r["Family"] or None,
                      group=r["Group"] or None, common_names=common, synonyms=syn,
                      systems_of_medicine=[s for s in r["System_of_Medicine"].split(",") if s],
                      iucn=r["IUCN_Red_List_Category"] or None, source_id=SRC_IMPPAT,
                      locator=f"{PLANT_TSV.name} row {i + 2} ({pid})",
                      aliases=[fold(x) for x in [r["Indian_Medicinal_plant"]] + syn + common if x])
            name_to_pid[r["Indian_Medicinal_plant"].strip().lower()] = pid
        self.log["plants"] = len(plants)

        tu = pd.read_csv(THERAPEUTIC_TSV, sep="\t", dtype=str).fillna("")
        agg = collections.defaultdict(lambda: {"rows": [], "parts": set()})
        for i, r in tu.iterrows():
            tid, label = r["IMPPAT_Therapeutic_use_identifier"], r["Therapeutic_use"]
            if not tid:
                continue
            self.node(f"TU:{tid}", "TherapeuticUse", label_en=label, source_id=SRC_IMPPAT,
                      locator=f"{THERAPEUTIC_TSV.name} ({tid})", aliases=[fold(label)])
            a = agg[(r["IMPPAT_Plant_identifier"], tid)]
            a["rows"].append(i + 2)
            if r["Plant_part"]:
                a["parts"].add(r["Plant_part"])
        for (pid, tid), a in agg.items():
            rows = a["rows"]
            loc = f"{THERAPEUTIC_TSV.name} row{'s' if len(rows) > 1 else ''} " + ", ".join(map(str, rows[:5])) + \
                  (f" (+{len(rows) - 5} more)" if len(rows) > 5 else "")
            self.edge(f"PLANT:{pid}", f"TU:{tid}", "traditionally_used_for", SRC_IMPPAT, loc,
                      "extracted_from_source", 1.0, row_count=len(rows), plant_parts=sorted(a["parts"]))
        self.log["therapeutic_use_rows"] = len(tu)
        self.log["plant_use_edges"] = len(agg)

        api = pd.read_csv(FORMULATIONS_TSV, sep="\t", dtype=str).fillna("")
        unmatched = 0
        for i, r in api.iterrows():
            fid = r["Formulation_identifier"]
            name = r["Formulation_name_in_API_original"]
            loc = f"{FORMULATIONS_TSV.name} row {i + 2} ({fid}; {r['References']})"
            clean_name = re.sub(r"_\d+$", "", name)
            self.node(f"FORM:{fid}", "Formulation", label_en=name, label_iast=clean_name,
                      label_sa_deva=to_script(clean_name, "deva"), label_kn_script_sanskrit=to_script(clean_name, "kn"), api_ingredient=r["Ingredient name in API_original"],
                      api_plant_part=r["Plant part in API_original"],
                      api_therapeutic_uses_sanskrit=r["Therapeutic_uses (according to The Ayurvedic Pharmacopoeia of India)"],
                      reference=r["References"], source_id=SRC_API, locator=loc, aliases=[fold(name)])
            pid = name_to_pid.get(r["Plant_name_standardised"].strip().lower())
            if pid:
                self.edge(f"FORM:{fid}", f"PLANT:{pid}", "contains", SRC_API, loc, "extracted_from_source", 1.0,
                          plant_part=r["Plant_part_standardised"] or None)
                # the API (Sanskrit) name of a single-herb formulation is a recorded name of that plant
                pn = self.g.nodes[f"PLANT:{pid}"]
                pn.setdefault("api_names", [])
                if name not in pn["api_names"]:
                    pn["api_names"].append(name)
                pn["aliases"] = sorted(set(pn["aliases"]) | {fold(name)})
                clean = re.sub(r"_\d+$", "", name)
                if not pn.get("label_iast"):
                    pn["label_iast"], pn["label_sa_deva"] = clean, to_script(clean, "deva")
                    pn["label_kn_script_sanskrit"] = to_script(clean, "kn")
                    pn["script_label_note"] = ("Devanagari/Kannada forms are transliterations of the API Sanskrit "
                                               "name, not Hindi/Kannada vernacular names")
            else:
                unmatched += 1
            tids = [t for t in r["IMPPAT_identifiers"].split("|") if t]
            labels = [l for l in r["Therapeutic_uses_standardised"].split("|")]
            for j, t in enumerate(tids):
                if f"TU:{t}" not in self.g:
                    self.node(f"TU:{t}", "TherapeuticUse", label_en=labels[j] if j < len(labels) else t,
                              source_id=SRC_API, locator=loc, aliases=[fold(labels[j]) if j < len(labels) else t])
                self.edge(f"FORM:{fid}", f"TU:{t}", "traditionally_used_for", SRC_API, loc,
                          "extracted_from_source", 1.0)
        self.log["formulations"] = len(api)
        self.log["formulations_without_plant_match"] = unmatched

    # 6. symptom phrases (keeps symptom module and graph in sync)
    def add_symptoms(self):
        from app.core.symptom_mapper import CLASSICAL_SYMPTOM_CATALOG
        for item in CLASSICAL_SYMPTOM_CATALOG:
            key = item["concept_key"]
            pats = item.get("patterns", {})
            nid = f"SYMPTOM:{key}"
            self.node(nid, "SymptomPhrase", label_en=(pats.get("en") or [key])[0],
                      label_hi=(pats.get("hi") or [None])[0], label_kn=(pats.get("kn") or [None])[0],
                      label_roman=(pats.get("hi_roman") or [None])[0],
                      aliases=[p for ps in pats.values() for p in ps], source_id="AyurMitra_symptom_mapper",
                      locator=f"app/core/symptom_mapper.py CLASSICAL_SYMPTOM_CATALOG['{key}']",
                      review_status="project_mapping_unreviewed", confidence=0.4,
                      note_en=item.get("notes", {}).get("en"))
            target = f"CONCEPT:{item['dosha']}"
            claimed = item.get("locator")
            self.edge(nid, target, "may_be_associated_with_dosha", "AyurMitra_symptom_mapper", None,
                      "project_mapping_unreviewed", 0.4, claimed_locator=f"{item.get('source_id')} {claimed}",
                      claimed_locator_verdict="not verified (audit F4: claimed page does not support the relation)")
        self.log["symptom_phrases"] = len(CLASSICAL_SYMPTOM_CATALOG)

    # 7. re-verify the old hand-written v1 edges against WHO text
    def import_v1(self, who):
        v1 = pickle.load(open(KG_PKL, "rb"))
        terms = who["terms"]
        for u, v, d in v1.edges(data=True):
            rel = d.get("relation", "related_to")
            uid, vid = f"CONCEPT:{u}", f"CONCEPT:{v}"
            row = {"edge": f"{u} -{rel}-> {v}", "claimed": f"{d.get('source_id')} {d.get('locator')}"}
            if u.startswith(("Dry", "Joint", "Burning", "Acid", "Sluggish", "Excessive")):
                row["verdict"] = "symptom mapping → kept as project_mapping_unreviewed (see SymptomPhrase nodes)"
                self.audit_rows.append(row)
                continue
            if uid not in self.g or vid not in self.g:
                row["verdict"] = "endpoint not a project concept (herb/class) → not imported"
                self.audit_rows.append(row)
                continue
            fu, fv = fold(u), fold(v)
            hit = None
            for t in terms:
                head = fold(t["english"])
                desc = fold(t["description"])
                if (fu in head.split() or fu in fold(t["iast"]).split()) and re.search(rf"\b{fv}", desc):
                    hit = t
                    break
                if (fv in head.split() or fv in fold(t["iast"]).split()) and re.search(rf"\b{fu}", desc):
                    hit = t
                    break
            if hit:
                loc = f"{hit['term_id']}, PDF p.{hit['pdf_page']} (printed p.{hit['printed_page']})"
                self.edge(uid, vid, rel, SRC_WHO, loc, "grounded_by_code_text", 0.6,
                          evidence_text=hit["description"][:300], claimed_v1_locator=row["claimed"])
                row["verdict"] = f"grounded by code in WHO {loc}"
            else:
                self.edge(uid, vid, rel, "AyurMitra_v1_graph", None, "unverified", 0.2, claimed_v1_locator=row["claimed"])
                row["verdict"] = "not found in WHO text → imported as unverified"
            self.audit_rows.append(row)

    def build(self) -> nx.DiGraph:
        t0 = time.time()
        self.add_concepts()
        self.add_namaste()
        who = self.add_who()
        self.add_imppat()
        self.link_concepts(who)
        self.add_symptoms()
        self.import_v1(who)
        self.log["build_seconds"] = round(time.time() - t0, 1)
        self.g.graph.update({"version": "v2", "built": time.strftime("%Y-%m-%d"), "log": dict(self.log),
                             "v1_reverification": self.audit_rows})
        return self.g


def stats(g: nx.DiGraph) -> Dict[str, Any]:
    nt = collections.Counter(d["node_type"] for _, d in g.nodes(data=True))
    er = collections.Counter(d["relation"] for _, _, d in g.edges(data=True))
    rs = collections.Counter(d["review_status"] for _, _, d in g.edges(data=True))
    no_src = sum(1 for _, _, d in g.edges(data=True) if not d.get("source_id"))
    no_loc = sum(1 for _, _, d in g.edges(data=True) if not d.get("locator"))
    iso = [n for n in g.nodes if g.degree(n) == 0]
    src_extracted = rs.get("extracted_from_source", 0)
    return {"nodes": g.number_of_nodes(), "edges": g.number_of_edges(), "node_types": dict(nt),
            "relations": dict(er), "review_status": dict(rs), "edges_without_source_id": no_src,
            "edges_without_locator": no_loc, "isolated_nodes": len(iso),
            "pct_edges_extracted_from_source": round(100 * src_extracted / max(1, g.number_of_edges()), 2)}


def write_outputs(g: nx.DiGraph) -> Dict[str, Any]:
    if KG_PKL.exists() and not KG_V1_PKL.exists():
        shutil.copy2(KG_PKL, KG_V1_PKL)
    with open(KG_V2_PKL, "wb") as f:
        pickle.dump(g, f, protocol=pickle.HIGHEST_PROTOCOL)
    st = stats(g)
    nodes = [{"id": n, **{k: v for k, v in d.items() if v not in (None, [], "")}} for n, d in g.nodes(data=True)]
    edges = [{"source": u, "target": v, **{k: x for k, x in d.items() if x not in (None, [], "")}}
             for u, v, d in g.edges(data=True)]
    KG_V2_JSON.write_text(json.dumps({"version": "v2", "stats": st, "nodes": nodes, "edges": edges},
                                     ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    lines = ["# Knowledge Graph v2 — build report", "",
             f"Built {g.graph.get('built')} by `python -m app.core.kg_builder` (deterministic; {g.graph['log'].get('build_seconds')} s).", "",
             "## Size", "", f"- Nodes: **{st['nodes']:,}**  ·  Edges: **{st['edges']:,}**",
             f"- Edges with a source row/page locator extracted by code: **{st['pct_edges_extracted_from_source']}%**",
             f"- Edges without source_id: {st['edges_without_source_id']}  ·  without locator: {st['edges_without_locator']} "
             "(only project mappings / unverified v1 edges, by design)",
             f"- Isolated nodes: {st['isolated_nodes']}", "", "## Node types", "", "| Type | Count |", "|---|---|"]
    lines += [f"| {k} | {v:,} |" for k, v in sorted(st["node_types"].items(), key=lambda x: -x[1])]
    lines += ["", "## Relations", "", "| Relation | Count |", "|---|---|"]
    lines += [f"| {k} | {v:,} |" for k, v in sorted(st["relations"].items(), key=lambda x: -x[1])]
    lines += ["", "## Review status of edges", "", "| Status | Count | Meaning |", "|---|---|---|"]
    meaning = {"extracted_from_source": "relation is a row/column of the source file; locator points to it",
               "auto_matched_by_code": "project concept ↔ source term by deterministic string match; needs expert review",
               "grounded_by_code_text": "old v1 relation found stated in a WHO description; needs expert review",
               "project_mapping_unreviewed": "project-written mapping, no source locator",
               "unverified": "old v1 relation whose claimed locator failed verification"}
    lines += [f"| {k} | {v:,} | {meaning.get(k, '')} |" for k, v in st["review_status"].items()]
    lines += ["", "## Build log", "", "```", json.dumps(g.graph["log"], indent=1), "```", "",
              "## Re-verification of the original v1 graph (audit F4)", "", "| v1 edge | Claimed locator | Verdict |",
              "|---|---|---|"]
    lines += [f"| {r['edge']} | {r['claimed']} | {r['verdict']} |" for r in g.graph["v1_reverification"]]
    lines += ["", "No edge in v2 says a plant or formulation *treats* or *cures* anything: IMPPAT/API rows are "
              "recorded as `traditionally_used_for`. Traditional records are not evidence of efficacy or safety."]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return st


def build_and_save() -> Dict[str, Any]:
    g = KGBuilder().build()
    return write_outputs(g)


if __name__ == "__main__":
    s = build_and_save()
    print(json.dumps(s, indent=1))
