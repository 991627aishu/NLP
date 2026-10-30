# AyurMitra — Neural Model Installation & Configuration Guide

This guide describes how to install and execute the optional neural backends for AyurMitra.

The core system is fully operational out-of-the-box using robust, transparent fallbacks (rule-based multilingual MT, multi-script TF-IDF dense retriever, extractive evidence-grounded generator, and browser Web Speech APIs).

---

## 1. System Architecture & Optional Neural Matrix

| Pipeline Component | Active Default / Fallback | Optional Neural Backend | Primary Python Module |
|---|---|---|---|
| **Query & Answer Translation** | Deterministic rule-based MT + transliteration | `ai4bharat/indictrans2` (200M distilled) | `app/pipeline/translator_neural.py` |
| **Dense Semantic Retrieval** | Character 3–5 n-gram TF-IDF (`char_wb`) | `paraphrase-multilingual-MiniLM-L12-v2` | `app/pipeline/dense_retriever.py` |
| **Answer Synthesis** | Evidence-grounded extractive generator | Anthropic Claude API / Local Ollama | `app/pipeline/llm_generator.py` |
| **Speech-to-Text (STT)** | Browser Web Speech API (Chrome / Edge) | `faster-whisper` (int8 CPU / CUDA) | `app/voice/stt.py` |
| **Text-to-Speech (TTS)** | `edge-tts` (live) / Browser `speechSynthesis` | `edge-tts` neural Indian voices | `app/voice/tts.py` |

---

## 2. Neural Translation: IndicTrans2

### Prerequisites & Licensing
- **Model weights:** `ai4bharat/indictrans2-indic-en-dist-200M` and `ai4bharat/indictrans2-en-indic-dist-200M`.
- **Licence:** MIT (AI4Bharat).
- **Access Gate:** The `indic-en` model is a gated Hugging Face repository. You must:
  1. Create or log in to a Hugging Face account at https://huggingface.co
  2. Navigate to https://huggingface.co/ai4bharat/indictrans2-indic-en-dist-200M and click **"Acknowledge and request access"**.
  3. Generate an Access Token under Hugging Face Settings -> Access Tokens.
  4. Set `HF_TOKEN` in your `.env` file:
     ```env
     HF_TOKEN=hf_your_actual_token_here
     TRANSLATOR_BACKEND=indictrans2
     ```

### Dependencies
Install neural translation dependencies:
```powershell
pip install torch transformers sentencepiece sacremoses
pip install IndicTransToolkit
```

### Execution & Verification
Run the Go/No-Go probe with IndicTrans2:
```powershell
python -m app.evaluation.go_no_go_probe_v2 --backend indictrans2
```
Verify via the health API:
```powershell
python -c "import urllib.request, json; print(json.loads(urllib.request.urlopen('http://127.0.0.1:8000/api/health').read())['backends']['neural_mt'])"
```

---

## 3. Neural Semantic Retrieval: Sentence-Transformers

### Configuration
By default, `DENSE_BACKEND=auto` attempts to load `SentenceTransformer(DENSE_MODEL_NAME)` and automatically falls back to char n-gram TF-IDF if unavailable.

To enable Sentence-Transformers:
```powershell
pip install sentence-transformers
```
Configure in `.env`:
```env
DENSE_BACKEND=sentence_transformers
DENSE_MODEL_NAME=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

### One-Time Index Encoding
When first run, the retriever encodes all 2,887 indexed chunks into `Data/processed/embeddings.npy` and records metadata in `Data/processed/embeddings_meta.json`. Subsequent starts load the precomputed numpy matrix instantaneously.

---

## 4. LLM Answer Generator (Anthropic / Ollama)

The system enforces strict evidence-only constraints on generative models:
1. Sentences must cite `[CHUNK_ID]` of an actually retrieved passage; any sentence with hallucinated or missing IDs is dropped.
2. Sentences containing prohibited prescription words (`mg`, `dosage`, `cure`, `safe and effective`) are rejected.
3. If no sentences survive, the generator automatically abstains with `INSUFFICIENT_EVIDENCE`.

### Setup
Option A (Anthropic Claude):
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-api-key
LLM_MODEL=claude-3-5-sonnet-20241022
```

Option B (Local Ollama):
```powershell
ollama pull llama3.2
```
In `.env`:
```env
LLM_PROVIDER=ollama
AYUR_OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
```

---

## 5. Voice Services (Faster-Whisper & Edge-TTS)

### Edge-TTS (Text-to-Speech)
Installed and verified. Generates high-quality neural speech in:
- English (`en-IN-NeerjaNeural`, `en-IN-PrabhatNeural`)
- Hindi (`hi-IN-SwaraNeural`, `hi-IN-MadhurNeural`)
- Kannada (`kn-IN-SapnaNeural`, `kn-IN-GaganNeural`)

### Faster-Whisper (Speech-to-Text)
Requires FFmpeg on the system `PATH`:
```powershell
winget install Gyan.FFmpeg
pip install faster-whisper
```
Configure in `.env`:
```env
STT_BACKEND=whisper
WHISPER_MODEL_SIZE=base
```
In the frontend, speech recognition populates the question box for user review and editing before submission to the RAG pipeline.

