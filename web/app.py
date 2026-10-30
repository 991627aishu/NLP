"""
AyurMitra — Interactive Web Application
=========================================
Streamlit user interface connecting directly to the live AyurMitra backend:
  - Multilingual Ayurvedic Question Answering (EN / HI / KN / Romanized)
  - Controlled Pipeline Comparison: B0 vs B1 vs P1 vs P2
  - Live Terminology Detection & Protection Inspector
  - Traceable Source Passages & Citations
  - Educational Knowledge Graph Browser
  - Cautious Symptom-to-Concept Mapping with Abstention Guardrails
"""

import sys
from pathlib import Path

# Resolve project root and prevent naming collision between web/app.py and 'app' package
root_dir = Path(__file__).resolve().parent.parent
web_dir = Path(__file__).resolve().parent

root_str = str(root_dir)
web_str = str(web_dir)

# Remove script directory from sys.path if inserted by Streamlit
while web_str in sys.path:
    sys.path.remove(web_str)

# Ensure project root is the first entry in sys.path
if root_str in sys.path:
    sys.path.remove(root_str)
sys.path.insert(0, root_str)

# Clear shadowed single-file 'app' module if loaded before this block
if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

import streamlit as st
from app.config import EDUCATIONAL_DISCLAIMER
from app.core.knowledge_graph import AyurKnowledgeGraph
from app.core.symptom_mapper import EducationalSymptomMapper
from app.pipeline.rag_pipeline import AyurMitraPipeline

st.set_page_config(
    page_title="AyurMitra — Multilingual Ayurvedic RAG",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize pipelines in session cache
@st.cache_resource
def get_pipeline():
    return AyurMitraPipeline()

@st.cache_resource
def get_kg():
    return AyurKnowledgeGraph()

@st.cache_resource
def get_symptom_mapper():
    return EducationalSymptomMapper()

pipe = get_pipeline()
kg = get_kg()
symptom_mapper = get_symptom_mapper()

# Header
st.title("🌿 AyurMitra")
st.caption("A Terminology-Preserving Multilingual RAG System with Knowledge Graph Grounding for Ayurvedic Knowledge Retrieval")

# Mandatory Safety Disclaimer Banner
st.warning(f"⚠️ **Educational Notice:** {EDUCATIONAL_DISCLAIMER}")

# Sidebar Settings
st.sidebar.header("⚙️ Experiment Configuration")
mode = st.sidebar.selectbox(
    "Select System Mode:",
    options=["P1", "B1", "B0", "P2"],
    format_func=lambda x: {
        "P1": "P1: Terminology-Preserving Hybrid RAG (Proposed)",
        "B1": "B1: Translation-Only Hybrid RAG (Baseline 1)",
        "B0": "B0: Translation-Only BM25 RAG (Baseline 0)",
        "P2": "P2: Proposed + Knowledge Graph Grounding"
    }[x]
)

st.sidebar.markdown("""
---
**Mode Guide:**
- **B0:** BM25 lexical search only, without terminology protection.
- **B1:** Hybrid BM25 + Dense RRF fusion, without terminology protection.
- **P1:** High-confidence terminology protection/restoration + Hybrid RAG.
- **P2:** P1 pipeline augmented with traceable knowledge graph facts.
""")

enable_web = st.sidebar.checkbox(
    "🌐 Enable Web Search Fallback",
    value=True,
    help="When enabled, queries authoritative public sources (EuropePMC, PubMed, Wikipedia) if local Ayurvedic evidence is insufficient."
)

tab_qa, tab_kg, tab_symptoms = st.tabs([
    "💬 Multilingual Knowledge Retrieval",
    "🕸️ Knowledge Graph Explorer",
    "🩺 Educational Symptom Guidance"
])

# ── TAB 1: QA & RAG ──────────────────────────────────────────────────────────
with tab_qa:
    st.subheader("Ask an Ayurvedic Question")
    st.write("Supports English, Hindi (हिन्दी), Kannada (ಕನ್ನಡ), and Romanized/Code-mixed queries.")

    # Helper callback to safely switch query presets
    def set_preset_query(text: str):
        st.session_state["query_input"] = text
        st.session_state["submitted_result"] = None

    if "query_input" not in st.session_state:
        st.session_state["query_input"] = "What is the role of Agni in digestion according to Ayurveda?"
    if "submitted_result" not in st.session_state:
        st.session_state["submitted_result"] = None

    sample_col1, sample_col2, sample_col3 = st.columns(3)
    sample_col1.button("EN: Symptoms of Pitta Dosha?", on_click=set_preset_query, args=("What are the symptoms and functions of Pitta Dosha?",))
    sample_col2.button("HI: पित्त दोष के कार्य क्या हैं?", on_click=set_preset_query, args=("पित्त दोष के कार्य क्या हैं?",))
    sample_col3.button("KN: ಪಿತ್ತಕ್ಕೆ ಲಕ್ಷಣಗಳು ಯಾವುವು?", on_click=set_preset_query, args=("ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?",))

    col_q, col_lang = st.columns([3, 1])
    with col_q:
        query_val = st.text_input(
            "Enter query:",
            key="query_input",
            help="Type in English, Hindi, Kannada, Romanized script, or mixed languages."
        )
    with col_lang:
        qa_lang_choice = st.selectbox(
            "Response Language:",
            options=["Auto (Detect)", "English", "Hindi (हिन्दी)", "Kannada (ಕನ್ನಡ)"],
            index=0,
            key="qa_lang_choice",
            help="Choose explicit answer language, or Auto to match input language."
        )
        qa_lang_map = {
            "Auto (Detect)": "auto",
            "English": "en",
            "Hindi (हिन्दी)": "hi",
            "Kannada (ಕನ್ನಡ)": "kn"
        }
        qa_target_lang = qa_lang_map[qa_lang_choice]

    col_btn1, col_btn2 = st.columns([1, 5])
    submit_clicked = col_btn1.button("Submit Query", type="primary")
    if col_btn2.button("Clear Results"):
        st.session_state["submitted_result"] = None
        st.rerun()

    if submit_clicked:
        if not query_val.strip():
            st.warning("Please enter a question.")
        else:
            with st.spinner("Processing through AyurMitra pipeline..."):
                st.session_state["submitted_result"] = pipe.process_query(
                    query_val,
                    system_mode=mode,
                    top_k=5,
                    target_lang=qa_target_lang,
                    enable_web_search=enable_web
                )

    res = st.session_state.get("submitted_result")
    if res is not None:
        col_left, col_right = st.columns([3, 2])

        with col_left:
            lang_label = {"en": "English", "hi": "हिन्दी (Hindi)", "kn": "ಕನ್ನಡ (Kannada)"}.get(res["target_language"], res["target_language"])
            st.markdown(f"### Generated Answer (`{lang_label}`)")
            if res["abstained"]:
                st.error(f"🛑 **Abstention Enforced:** {res['answer']}")
                st.info(f"Reason: `{res['abstention_reason']}`")
            else:
                st.success(res["answer"])

            st.markdown("#### Citations & Traceable Sources")
            if res["citations"]:
                for c in res["citations"]:
                    if c.get("is_web"):
                        st.markdown(f"- 🌐 **[{c['title']}]({c.get('url', '#')})** (*{c.get('publisher', 'Academic Reference')}*, {c.get('year', '')})")
                    else:
                        st.markdown(f"- 📚 **{c['title']}** (`{c['source_id']}` | {c['locator']})")
            else:
                st.caption("No passage citations available.")

        with col_right:
            st.markdown("### 🔍 Pipeline Execution Trace")
            comp = res.get("active_components", {})
            st.json({
                "System Mode": res["system_mode"],
                "Dominant Input Language": res["detected_language"],
                "Response Language": res["target_language"],
                "Code-Mixed Input": res.get("is_code_mixed", False),
                "Code-Mix Type": res.get("code_mix_type", "monolingual"),
                "Language Confidence": res["lang_detect_meta"].get("confidence"),
                "Confidence Level": res["lang_detect_meta"].get("confidence_level", "high"),
                "Web Fallback Enabled": comp.get("web_search_configured", False),
                "Web Search Status": comp.get("web_search_status", "disabled"),
                "Web Search Triggered": comp.get("web_search_triggered", False),
                "Web Sources Retrieved": comp.get("web_sources_retrieved", 0),
                "Latency (ms)": f"{res['latency_ms']:.1f}",
            })

            if res.get("segments"):
                st.caption(f"Input Segments Detected: {len(res['segments'])}")
                with st.expander("View Input Script Segments"):
                    for seg in res["segments"]:
                        st.markdown(f"- `[{seg.get('lang', 'unknown')}:{seg.get('script', '')}]` {seg.get('text', '')}")

            st.markdown("#### ⚙️ Active Pipeline Components")
            st.markdown(f"- **Terminology Protection & Restoration:** `{'ENABLED' if comp.get('terminology_protection') else 'DISABLED'}`")
            st.markdown(f"- **Dense Semantic RRF Fusion:** `{'ENABLED' if comp.get('dense_semantic') else 'DISABLED'}`")
            st.markdown(f"- **Knowledge Graph Fact Grounding:** `{'ENABLED' if comp.get('kg_grounding') else 'DISABLED'}`")
            st.markdown(f"- **Lexical BM25 Retrieval:** `{'ENABLED' if comp.get('bm25_lexical') else 'DISABLED'}`")
            
            # Accurate Web Fallback reporting
            if comp.get("web_search_triggered"):
                st.markdown("- **Web Search Fallback:** `ENABLED (Triggered & Sources Retrieved)`")
            elif comp.get("web_search_configured"):
                st.markdown("- **Web Search Fallback:** `ENABLED (Standby — Local evidence sufficient)`")
            else:
                st.markdown("- **Web Search Fallback:** `DISABLED`")

            if res["translation_meta"].get("warning"):
                st.info(f"ℹ️ {res['translation_meta']['warning']}")

            st.markdown("#### Detected Domain Terms")
            if res["detected_terms"]:
                for t in res["detected_terms"]:
                    st.info(f"📌 **{t['canonical_term']}** (matched: `{t['matched_text']}` [{t['script']}])")
            else:
                st.caption("No specific Ayurvedic domain terms detected.")

            st.markdown("#### Retrieved Evidence Passages")
            with st.expander(f"View {len(res['retrieved_passages'])} retrieved passages"):
                for p in res["retrieved_passages"]:
                    st.markdown(f"**[{p['chunk_id']}] {p['title']}**")
                    st.caption(f"Locator: {p['locator']} | Score: {p.get('rrf_score', p.get('bm25_score', 0.0)):.4f}")
                    st.write(p["text"][:250] + "...")
                    st.markdown("---")

            if res.get("web_passages"):
                st.markdown("#### 🌐 External Public Literature (EuropePMC / Wikipedia)")
                with st.expander(f"View {len(res['web_passages'])} external web fallback sources", expanded=True):
                    for wp in res["web_passages"]:
                        st.markdown(f"**[{wp.get('title')}]({wp.get('url', '#')})**")
                        st.caption(f"Publisher: {wp.get('publisher')} | Year: {wp.get('year')} | Type: {wp.get('source_type')}")
                        st.write(wp.get("snippet", ""))
                        st.markdown("---")

# ── TAB 2: Knowledge Graph Explorer ──────────────────────────────────────────
with tab_kg:
    st.subheader("Traceable Knowledge Graph Explorer")
    st.write("Inspect verified concepts, dosha principles, and medicinal plants from WHO, NAMASTE, and IMPPAT 2.0.")

    kg_query = st.selectbox(
        "Select Concept to Inspect:",
        options=["Vata", "Pitta", "Kapha", "Agni", "Ama", "Ojas", "Ashwagandha", "Triphala", "Tulsi", "Neem"]
    )

    if kg_query:
        node_info = kg.query_concept(kg_query)
        if node_info["found"]:
            st.markdown(f"### Node: `{node_info['concept']}`")
            st.json(node_info["attributes"])

            st.markdown("#### Connected Concept Relations (with Provenance)")
            for conn in node_info["connections"]:
                target = conn.get("target") or conn.get("source")
                st.markdown(
                    f"🔗 **{conn['relation']}** -> `{target}` "
                    f"*(Source: {conn['source_id']}, {conn['locator']})*"
                )
        else:
            st.error("Concept not found in knowledge graph.")

# ── TAB 3: Symptom Guidance ──────────────────────────────────────────────────
with tab_symptoms:
    st.subheader("Educational Symptom-to-Concept Guidance")
    st.write(
        "Maps non-acute symptom descriptions across English, Hindi (हिन्दी), Kannada (ಕನ್ನಡ), "
        "and Romanized scripts to classical Ayurvedic concepts with strict medical safety guardrails."
    )

    def set_preset_symptom(text: str):
        st.session_state["symptom_input"] = text
        st.session_state["symptom_result"] = None

    if "symptom_input" not in st.session_state:
        st.session_state["symptom_input"] = "I have severe dry skin and joint stiffness after cold weather."
    if "symptom_result" not in st.session_state:
        st.session_state["symptom_result"] = None

    st.markdown("**Sample Multilingual Presets:**")
    scol1, scol2, scol3, scol4 = st.columns(4)
    scol1.button("EN: Dry skin & joint stiffness", on_click=set_preset_symptom, args=("I have severe dry skin and joint stiffness after cold weather.",))
    scol2.button("HI: रूखी त्वचा और जोड़ों में दर्द", on_click=set_preset_symptom, args=("मेरी त्वचा बहुत रूखी है और जोड़ों में दर्द रहता है।",))
    scol3.button("KN: ಒಣ ಚರ್ಮ ಮತ್ತು ಕೀಲು ನೋವು", on_click=set_preset_symptom, args=("ನನ್ನ ಚರ್ಮ ಒಣಗಿದೆ ಮತ್ತು ಕೀಲುಗಳಲ್ಲಿ ನೋವು ಇದೆ.",))
    scol4.button("Hinglish: Dry skin aur joint pain", on_click=set_preset_symptom, args=("mujhe severe dry skin aur joint pain hai.",))

    ecol1, ecol2, ecol3 = st.columns(3)
    ecol1.button("🚨 EN Emergency: Severe headache", on_click=set_preset_symptom, args=("I have severe headache",))
    ecol2.button("🚨 HI Emergency: तेज सिरदर्द", on_click=set_preset_symptom, args=("मुझे बहुत तेज सिरदर्द है",))
    ecol3.button("🚨 KN Emergency: ತೀವ್ರ ತಲೆನೋವು", on_click=set_preset_symptom, args=("ನನಗೆ ತೀವ್ರ ತಲೆನೋವು ಇದೆ",))

    col_s_text, col_s_lang = st.columns([3, 1])
    with col_s_text:
        symptom_val = st.text_area(
            "Describe general physical sensations or discomforts:",
            key="symptom_input",
            help="Enter in English, Hindi (Devanagari), Kannada script, Hinglish, Kanglish, or mixed languages."
        )
    with col_s_lang:
        symptom_lang_choice = st.selectbox(
            "Response Language:",
            options=["Auto (Detect)", "English", "Hindi (हिन्दी)", "Kannada (ಕನ್ನಡ)"],
            index=0,
            key="symptom_lang_choice",
            help="Choose response language, or Auto to match input language."
        )
        s_lang_map = {
            "Auto (Detect)": "auto",
            "English": "en",
            "Hindi (हिन्दी)": "hi",
            "Kannada (ಕನ್ನಡ)": "kn"
        }
        symptom_target_code = s_lang_map[symptom_lang_choice]

    s_btn1, s_btn2 = st.columns([1, 5])
    if s_btn1.button("Analyze Sensations", type="primary"):
        if not symptom_val.strip():
            st.warning("Please enter a description.")
        else:
            with st.spinner("Analyzing against classical literature & safety rules..."):
                st.session_state["symptom_result"] = symptom_mapper.analyze_symptoms(
                    symptom_val, target_lang=symptom_target_code
                )

    if s_btn2.button("Clear Symptom Analysis"):
        st.session_state["symptom_result"] = None
        st.rerun()

    analysis = st.session_state.get("symptom_result")
    if analysis is not None:
        lang_display = {
            "en": "English",
            "hi": "हिन्दी (Hindi)",
            "kn": "ಕನ್ನಡ (Kannada)",
            "hi_roman": "Hinglish (Romanized Hindi)",
            "kn_roman": "Kanglish (Romanized Kannada)"
        }.get(analysis.get("target_language", analysis.get("detected_language")), analysis.get("detected_language"))

        cm_badge = f" | Code-mixed: **{analysis.get('code_mix_type')}**" if analysis.get("is_code_mixed") else ""
        st.caption(f"Input: **{analysis.get('detected_language')}** -> Response: **{lang_display}**{cm_badge} | Safety Check: **{'TRIGGERED (Abstention)' if analysis['abstained'] else 'PASSED'}**")

        if analysis["abstained"]:
            if analysis.get("reason") == "emergency_symptom_detected":
                st.error(f"🚨 **{analysis['emergency_alert']}**")
                st.info(f"Red flag detected: `{analysis.get('matched_red_flag', 'acute_symptom')}` | Emergency triage prioritized over concept mapping.")
            else:
                st.warning(f"🛑 {analysis.get('message', 'Abstention enforced.')}")
                st.caption(f"Reason: `{analysis.get('reason')}`")
        else:
            st.success(f"**Primary Conceptual Tendency:** {analysis['primary_conceptual_tendency']}")
            st.info(analysis["summary"])

            st.markdown("#### Concept Mappings & Verified Literature Citations:")
            for m in analysis["mappings"]:
                st.markdown(
                    f"- **{m['symptom_phrase'].title()}** -> `{m['associated_dosha']}`: "
                    f"{m['educational_note']} *{m['provenance']}*"
                )

