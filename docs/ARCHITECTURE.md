# Architecture

```mermaid
flowchart LR
  A[Question: text or voice] --> SG{Safety gate\nemergency · dose · toxic · cure claim}
  SG -- blocked --> X[Referral / refusal\nspoken + written]
  SG -- ok --> L[Language & script detection\nEN · HI · KN · Hinglish · Kanglish]
  L --> T[Term detection\nNAMASTE · WHO · aliases · Kannada suffixes]
  T --> P[Protect terms\n__AYURTERM_n__ → AYTnZ]
  P --> MT[Translate to English\nIndicTrans2 → rules fallback]
  MT --> C[Restore canonical terms]
  C --> G1[P2 only: graph expansion ≤5 terms]
  G1 --> R[Hybrid retrieval\nBM25 + dense, RRF k=60]
  R --> EG{Evidence gate\ncoverage ≥ 0.4}
  EG -- weak --> Y[Abstain: insufficient evidence]
  EG -- ok --> GEN[Grounded answer\nextractive or LLM w/ citation check]
  KG[(Knowledge graph v2\n9.5k nodes · 72k edges)] --> G1
  KG --> GEN
  GEN --> O[EN→HI/KN with term protection\n+ native-script restoration]
  O --> UI[Website: answer · sources · trace · TTS]
```

| Layer | Code |
|---|---|
| Config & flags | `app/config.py` (`.env` supported) |
| Safety | `app/core/safety.py`, `app/core/symptom_mapper.py` |
| Terminology | `app/core/terminology.py`, `matcher.py`, `protection.py` |
| Translation | `app/pipeline/translator.py` (rules), `translator_neural.py` (IndicTrans2 + cache) |
| Retrieval | `bm25_retriever.py`, `dense_retriever.py` (sentence-transformers / TF-IDF), `hybrid_retriever.py`, `index_cache.py` |
| Generation | `generator.py` (extractive), `llm_generator.py` (optional) |
| Graph | `app/core/who_extract.py`, `kg_builder.py`, `kg_v2.py` (v1: `knowledge_graph.py`) |
| Herbs/lifestyle | `app/core/herbs.py` |
| Voice | `app/voice/{stt,tts,text_clean}.py` |
| API | `api/main.py` (FastAPI) |
| Website | `frontend/` (no build step) · legacy `web/app.py` (Streamlit) |
| Evaluation | `app/evaluation/{evaluator_v2,go_no_go_probe_v2,report_v2,human_eval_kit,kappa}.py` (v1 files unchanged) |
