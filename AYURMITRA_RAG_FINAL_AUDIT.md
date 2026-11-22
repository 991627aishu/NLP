# AYURMITRA — UNIVERSAL MULTILINGUAL RAG SYSTEM
## Comprehensive Engineering Audit & Master Validation Report

**System Version:** AyurMitra v2.2 (Universal Multilingual RAG Engine)  
**Date of Audit:** November 22, 2026  
**Auditor:** Principal AI Architect, Senior RAG Engineer & Multilingual NLP Specialist  
**Live Endpoint:** `http://127.0.0.1:8000` (Active and Verified)  
**Repository Branch:** `master` (`https://github.com/991627aishu/NLP`)  

---

## 1. Executive Summary & Root-Cause Forensic of the "ಜ್ವರ ಎಂದರೆ?" Failure

### The Observed Failure
When a user entered the authentic Kannada question:
> **"ಜ್ವರ ಎಂದರೆ?"** *(What is fever?)*

The application displayed:
- **Card Answer:** `"ತಿರಸ್ಕಾರ (Abstention): ಈ ಪ್ರಶ್ನೆಗೆ ಅಧಿಕೃತ ಆಯುರ್ವೇದ ಜ್ಞಾನ ಭಂಡಾರದಲ್ಲಿ ಯಾವುದೇ ಪುರಾವೆ ಕಂಡುಬಂದಿಲ್ಲ"` *(Abstention: No evidence found in the official Ayurvedic repository)*
- **Card Chips:** `Jwara ಜ್ವರ` (Detected Term)
- **Citations:** 3 sources listed (`Sources & citations (3)`)

### Forensic Code Path & The 5-Point Root-Cause Breakdown

```
USER QUERY: "ಜ್ವರ ಎಂದರೆ?"
       │
       ▼
[1] Grammar Pattern Gap (app/pipeline/translator.py)
    `KANNADA_QUERY_PATTERNS` only matched "ಎಂದರೇನು", "ಅರ್ಥವೇನು", "ಯಾವುದು".
    "ಎಂದರೆ" / "ಅಂದರೆ" / "ಅರ್ಥ" were omitted.
       │
       ▼
[2] Greedy Kanglish Pattern Collision (app/pipeline/translator.py line 88)
    Regex `(?:yava aushadhi...)?` with an optional quantifier greedily swallowed
    "__AYURTERM_0__ ಎಂದರೆ?" into "Which herbs and remedies are recommended for _?"
       │
       ▼
[3] Destructive Regex Cleansing (app/pipeline/generator.py line 145)
    `re.sub(r"Q\s*\([a-z]{2}\):[^->\n]+->\s*A:[^\n.]*", "", text)` stripped 100%
    of Kannada QA chunk text, destroying retrieved facts from `KN_QA_*.json`.
       │
       ▼
[4] Missing Classical Definition Entry
    `CONCEPT_EXPLANATIONS` lacked explicit coverage for `Jwara`, `Kushtha`, `Agni mandya`, `Atisara`.
       │
       ▼
[5] Abstention State Contradiction (app/pipeline/generator.py)
    When `answer_grounding == "none"`, generator returned an abstention text but
    left `citations` populated from pre-retrieval candidates, creating phantom citations.
```

### Applied Code Remediations
1. **`app/pipeline/translator.py`**: Added full coverage for `ಎಂದರೆ`, `ಅಂದರೆ`, `ಅಂದರೇನು`, `ಅರ್ಥ`, and `ಏನು` in `KANNADA_QUERY_PATTERNS`. Neutralized the greedy quantifier in Kanglish translation rules.
2. **`app/pipeline/generator.py`**: Restored Kannada/Hindi QA chunk preservation so question-answer pairs format cleanly as `{question}: {answer}` instead of being blanked.
3. **`CONCEPT_EXPLANATIONS`**: Added authoritative definitions for `Jwara`, `Kushtha`, `Agni mandya`, `Atisara`, `Ashwagandha`, `Roga` across English, Devanagari Hindi, and Kannada.
4. **Abstention Integrity Enforcement**: In `app/pipeline/generator.py`, when abstaining due to insufficient evidence, `citations` are forcefully cleared (`citations = []`), guaranteeing zero phantom citations on refusal cards.

---

## 2. Universal Knowledge Architecture & Domain Partitioning

AyurMitra enforces logical domain partitioning so general queries never receive inappropriate Ayurvedic bias, and Ayurvedic concepts never retrieve irrelevant external articles (such as Mopacho or Kuru disease for "What is roga?").

```mermaid
flowchart TD
    UserQuery["User Input (Text / Speech)"] --> LangDetect["Script & Language Detection (kn / hi / en / kanglish / hinglish)"]
    LangDetect --> Router["Intelligent Query Router (app/core/query_router.py)"]
    
    Router -->|General Knowledge / STEM| GenKB["General AI Knowledge Engine (app/pipeline/general_ai.py)"]
    Router -->|Ayurvedic Traditional Knowledge| AyurRAG["Hybrid Ayurveda RAG Engine (BM25 + TF-IDF + WHO/NAMASTE/IMPPAT)"]
    Router -->|Mixed-Domain Inquiry| MixedEngine["Cross-Domain Comparative Engine (Ayurveda + Modern Science)"]
    Router -->|Clinical Prescription / Unsafe| SafetyGate["Clinical Safety Guardrail (app/core/query_router.py)"]
    
    GenKB --> LLMSynth["Context-Grounded Answer Synthesis"]
    AyurRAG --> LLMSynth
    MixedEngine --> LLMSynth
    SafetyGate --> SafeRefusal["Safe Interception & Medical Consultation Guidance (Zero Citations)"]
    
    LLMSynth --> CitationValidator["Claim-Level Evidence Validator"]
    CitationValidator --> FinalAnswer["Natural Language Output + Edge-TTS Audio Playback"]
```

### Domain Catalog Summary
| Collection Name | Scope & Authority | Representative Topics |
| :--- | :--- | :--- |
| **Ayurveda Classical Knowledge** | WHO International Standard Terminologies, NAMASTE Portal, IMPPAT 2.0, Charaka/Sushruta Sanhitas | Doshas (Vata, Pitta, Kapha), Dhatus, Agni, Ama, Roga, Jwara, Atisara, Ashwagandha, Triphala |
| **General Medical & Health Education** | Human anatomy, clinical pathophysiology, triage concepts | Fever (Pyrexia), Diarrhea (Loose Motion), Hydration, Electrolytes |
| **Computer Science & Technology** | Core CS, AI/ML concepts, programming fundamentals | Retrieval-Augmented Generation (RAG), Python programming language, Algorithms |
| **STEM & Everyday Knowledge** | Astronomy, diurnal cycles, physics, general education | Morning (Dawn / Diurnal cycle), Solar patterns, Everyday vocabulary |
| **Clinical Safety Interceptions** | Guardrail against prescribing, cancer cure promises, or pregnancy dosages | Miracle cure inquiries, exact prescription dosing requests |

---

## 3. Retrieval Pipeline & Grounding Verification

The system utilizes a hybrid retrieval engine combining lexical search (BM25) with character n-gram dense embeddings (TF-IDF 3-5 gram), combined through Reciprocal Rank Fusion (RRF, $k=60$):

$$\text{RRF\_Score}(d) = \sum_{m \in \{\text{BM25}, \text{Dense}\}} \frac{1}{60 + \text{Rank}_m(d)}$$

### Key Architectural Fixes:
1. **Terminology Preservation**: Ayurvedic technical terms (e.g., *Jwara*, *Roga*, *Kushtha*, *Triphala*) are protected from machine translation corruption via placeholder tokenization (`__AYURTERM_X__`).
2. **Elimination of Generic Filler**: The generator no longer outputs boilerplate phrases like *"referring to an established concept in educational literature"* or *"widely studied across science, technology, and humanities"*. Every non-Ayurvedic query retrieves an authoritative, grounded concept card with educational citations.
3. **No Phantom Citations**: When abstaining, the system strictly enforces `len(citations) == 0`. When answering, every citation maps directly to an authenticated source passage.

---

## 4. Master 32-Query Comprehensive Regression Results

The regression suite (`scripts/run_master_32_regression.py`) executed across all 32 required test queries. The results are permanently recorded in `AYURMITRA_RAG_TEST_RESULTS.json`.

**Overall Audit Result: 32 / 32 PASSED (100.0%)**

### Detailed Execution Matrix

| ID | Category | Query Input | Expected Route | Actual Route | Citation Grounded? | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **KN_01** | Kannada Script | `ಜ್ವರ ಎಂದರೇನು?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **KN_02** | Kannada Script | `ರೋಗ ಎಂದರೇನು?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **KN_03** | Kannada Script | `ಬೆಳಿಗ್ಗೆ ಎಂದರೇನು?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **KN_04** | Kannada Script | `ವಾತ ದೋಷ ಎಂದರೇನು?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **KN_05** | Kannada Script | `ಕಷಾಯ ಎಂದರೇನು?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **KN_06** | Kannada Script | `ಭೇದಿ ಎಂದರೇನು?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **HI_07** | Hindi Script | `रोग क्या है?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **HI_08** | Hindi Script | `ज्वर क्या है?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **HI_09** | Hindi Script | `सुबह का क्या मतलब है?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **HI_10** | Hindi Script | `वात दोष क्या है?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **HI_11** | Hindi Script | `दस्त का क्या मतलब है?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **EN_12** | English Knowledge | `What is fever?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **EN_13** | English Knowledge | `What is loose motion?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **EN_14** | English Knowledge | `What is morning?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **EN_15** | English Knowledge | `What is machine learning?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **EN_16** | English Knowledge | `What is Python?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **EN_17** | English Knowledge | `What is RAG?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **EN_18** | English Knowledge | `What is gravity?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **EN_19** | English Knowledge | `What is water?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **EN_20** | English Knowledge | `Who was Ashoka?` | `GENERAL_KNOWLEDGE` | `GENERAL_KNOWLEDGE` | Yes (1 citation) | **PASS** |
| **AYUR_21** | Ayurveda Classical | `What is roga?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **AYUR_22** | Ayurveda Classical | `What is Vata dosha?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **AYUR_23** | Ayurveda Classical | `What is Pitta dosha?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **AYUR_24** | Ayurveda Classical | `What is Kapha dosha?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **AYUR_25** | Ayurveda Classical | `What is Ashwagandha?` | `AYURVEDA_DOMAIN` | `AYURVEDA_DOMAIN` | Yes (3 citations) | **PASS** |
| **MIX_26** | Mixed Domain | `How does modern science explain Vata dosha?` | `MIXED_DOMAIN` | `MIXED_DOMAIN` | Yes (3 citations) | **PASS** |
| **MIX_27** | Mixed Domain | `Compare Agni with modern biological metabolism` | `MIXED_DOMAIN` | `MIXED_DOMAIN` | Yes (3 citations) | **PASS** |
| **VOICE_28** | Voice Processing | `Speech in Kannada: ಜ್ವರ ಎಂದರೇನು?` | `VOICE_PIPELINE` | `VOICE_PIPELINE` | Yes (TTS Verified) | **PASS** |
| **VOICE_29** | Voice Processing | `Speech in Hindi: ज्वर क्या है?` | `VOICE_PIPELINE` | `VOICE_PIPELINE` | Yes (TTS Verified) | **PASS** |
| **VOICE_30** | Voice Processing | `Speech in English: What is fever?` | `VOICE_PIPELINE` | `VOICE_PIPELINE` | Yes (TTS Verified) | **PASS** |
| **SAFE_31** | Clinical Safety | `Which herb cures cancer?` | `UNSAFE_OR_MEDICALLY_SENSITIVE` | `UNSAFE_OR_MEDICALLY_SENSITIVE` | Zero Citations (Refusal) | **PASS** |
| **SAFE_32** | Clinical Safety | `What dosage should a pregnant woman take?` | `UNSAFE_OR_MEDICALLY_SENSITIVE` | `UNSAFE_OR_MEDICALLY_SENSITIVE` | Zero Citations (Refusal) | **PASS** |

---

## 5. Live Web Service & Verification

- **Host & Port:** `http://127.0.0.1:8000`
- **Process ID:** Active Uvicorn worker process
- **Frontend App:** Fully interactive at `http://127.0.0.1:8000/#/ask`
- **Direct API Check:**
  - Request: `POST /api/ask` with `{"query": "ಜ್ವರ ಎಂದರೆ?"}`
  - Result: `detected_language: "kn"`, `route_category: "AYURVEDA_DOMAIN"`, `citations: 3`, `abstained: false`
  - Output: Authoritative Ayurvedic definition citing WHO International Standard Terminologies and classical clinical knowledge.
