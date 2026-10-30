"""Phase 3-4 tests: KG v2 provenance (locators re-checked against the real source files), P2 use, herbs module."""
import pickle
import random
import re

import pandas as pd
import pytest

from app import config


@pytest.fixture(scope="module")
def kg():
    from app.core.kg_v2 import KnowledgeGraphV2
    return KnowledgeGraphV2()


def test_v1_graph_preserved():
    for p in (config.KG_PKL, config.KG_V1_PKL):
        g = pickle.load(open(p, "rb"))
        assert g.number_of_nodes() == 24 and g.number_of_edges() == 12


def test_every_edge_has_provenance_fields(kg):
    for u, v, d in kg.graph.edges(data=True):
        assert d.get("source_id"), (u, v)
        assert d.get("review_status") in {"extracted_from_source", "auto_matched_by_code", "grounded_by_code_text",
                                          "project_mapping_unreviewed", "unverified"}
        assert isinstance(d.get("confidence"), float)
        if d["review_status"] in ("extracted_from_source", "auto_matched_by_code", "grounded_by_code_text"):
            assert d.get("locator"), (u, v, d)


def test_no_node_without_source(kg):
    assert all(d.get("source_id") for _, d in kg.graph.nodes(data=True))


def test_no_treats_or_cures_wording(kg):
    rels = {d["relation"] for _, _, d in kg.graph.edges(data=True)}
    assert not {r for r in rels if re.search(r"treat|cure|heal", r)}


def test_who_locators_match_real_pdf_pages(kg):
    import pdfplumber
    who = [(n, d) for n, d in kg.graph.nodes(data=True) if d["node_type"] == "WHOTerm"]
    random.Random(7).shuffle(who)
    with pdfplumber.open(config.WHO_PDF) as pdf:
        for n, d in who[:12]:
            text = pdf.pages[d["pdf_page"] - 1].extract_text() or ""
            assert d["who_term_id"] in text, (n, d["pdf_page"])
            assert d["printed_page"] == d["pdf_page"] - 18


def test_namaste_locators_match_rows(kg):
    df = pd.read_excel(config.NAMASTE_XLSX)
    for n, d in list((n, d) for n, d in kg.graph.nodes(data=True) if d["node_type"] == "NAMASTETerm")[:40]:
        row = int(re.search(r"row (\d+)", d["locator"]).group(1))
        assert str(df.iloc[row - 2]["Code"]).strip() == d["namaste_code"]


def test_imppat_use_locators_match_rows(kg):
    tu = pd.read_csv(config.THERAPEUTIC_TSV, sep="\t", dtype=str).fillna("")
    edges = [(u, v, d) for u, v, d in kg.graph.edges(data=True) if d["relation"] == "traditionally_used_for"
             and d["source_id"] == "IMPPAT_2.0"]
    random.Random(3).shuffle(edges)
    for u, v, d in edges[:25]:
        first_row = int(re.search(r"rows? (\d+)", d["locator"]).group(1))
        r = tu.iloc[first_row - 2]
        assert f"PLANT:{r['IMPPAT_Plant_identifier']}" == u and f"TU:{r['IMPPAT_Therapeutic_use_identifier']}" == v


def test_old_v1_locators_reverified(kg):
    rows = kg.graph.graph["v1_reverification"]
    assert len(rows) == 12 and all(r["verdict"] for r in rows)
    e = kg.graph.edges["CONCEPT:Tridosha", "CONCEPT:Vata"]
    assert e["review_status"] == "grounded_by_code_text" and e["locator"].startswith("ITA-2.1.2")
    assert "page 15" in e["claimed_v1_locator"]


def test_symptom_catalog_in_sync_with_graph(kg):
    from app.core.symptom_mapper import CLASSICAL_SYMPTOM_CATALOG
    for item in CLASSICAL_SYMPTOM_CATALOG:
        n = f"SYMPTOM:{item['concept_key']}"
        assert n in kg.graph
        e = kg.graph.edges[n, f"CONCEPT:{item['dosha']}"]
        assert e["review_status"] == "project_mapping_unreviewed"


def test_devanagari_labels_from_iast_not_garbled_pdf(kg):
    assert kg.graph.nodes["WHO:ITA-2.1.2"]["label_sa_deva"] == "त्रिदोषः"


def test_query_concept_v1_compatible(kg):
    r = kg.query_concept("Pitta")
    assert r["found"] and r["connections"] and "source_id" in r["connections"][0]
    assert kg.query_concept("zzz")["connections"] == []


@pytest.mark.parametrize("q,expect", [("pitta", "CONCEPT:Pitta"), ("ಪಿತ್ತ", "CONCEPT:Pitta"),
                                      ("पित्त", "CONCEPT:Pitta"), ("ashwagandha", "CONCEPT:Ashwagandha")])
def test_multilingual_search(kg, q, expect):
    assert expect in [h["id"] for h in kg.search(q, limit=5)]


def test_neighbourhood_is_capped(kg):
    nb = kg.neighbourhood("Ashwagandha", depth=3, limit=1000)
    assert 0 < len(nb["nodes"]) <= 300
    ids = {n["id"] for n in nb["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in nb["edges"])


def test_shortest_path(kg):
    p = kg.shortest_path("Tridosha", "Pitta")
    assert p["found"] and p["edges"][0]["locator"]


def test_p2_uses_graph_with_provenance():
    from app.pipeline.rag_pipeline import AyurMitraPipeline
    pipe = AyurMitraPipeline()
    assert pipe.kg.version == "v2"
    r = pipe.process_query("What is the function of Pitta?", system_mode="P2", enable_web_search=False)
    assert r["graph_facts"] and all(f.get("review_status") for f in r["graph_facts"])
    assert len(r["graph_expansion_terms"]) <= 5
    r1 = pipe.process_query("What is the function of Pitta?", system_mode="P1", enable_web_search=False)
    assert r1["graph_facts"] == [] and r1["graph_expansion_terms"] == []


# ── herbs module ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def herbs(kg):
    from app.core.herbs import HerbService
    from app.pipeline.hybrid_retriever import HybridRetriever
    return HerbService(kg=kg, retriever=HybridRetriever())


@pytest.mark.parametrize("q", ["ashwagandha", "अश्वगन्धा", "Withania somnifera", "ಅಶ್ವಗನ್ಧಾ"])
def test_herb_search_multiscript(herbs, q):
    assert herbs.search(q)["results"][0]["botanical_name"] == "Withania somnifera"


def test_herb_detail_is_source_backed_and_dose_free(herbs):
    d = herbs.detail("ashwagandha")
    assert d["family"] == "Solanaceae" and d["recorded_traditional_uses"] and d["formulations"]
    assert all(u["locator"] and u["source_id"] for u in d["recorded_traditional_uses"])
    assert "not evidence" in d["traditional_records_note"] and d["disclaimer"]
    blob = str(d).lower()
    assert not re.search(r"\b(dose|dosage|mg)\b", blob) and "safe to" not in blob


def test_lifestyle_topics_retrieve_sources(herbs):
    assert len(herbs.lifestyle_topics()) >= 5
    t = herbs.lifestyle_topic("daily_routine")
    assert t["passages"] and all(p["chunk_id"] and p["source_id"] for p in t["passages"])
    assert herbs.lifestyle_topic("nope") is None
