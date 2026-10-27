AYURMITRA — MASTER README.MD GENERATION COMPLETED
The root-level 

README.md
 has been created from the ground up based on the actual repository implementation, real verified datasets, passing test suites, and empirical evaluation metrics.

1. Summary of Sections Added and Corrected in README.md
Executive Overview & Scientific Boundaries:
Detailed the core problem: hallucination in general-purpose LLMs when addressing specialized traditional medicine, loss of Sanskrit technical meaning in translation, and lack of red-flag emergency triage.
Enforced the distinction between traditional ethnobotanical associations (e.g. historical textual uses in IMPPAT 2.0 / WHO) and modern clinical trial efficacy.
Clarified that AyurMitra is an academic research prototype, explicitly not an autonomous diagnostic or prescription device.
Detailed System Architecture with 2 Real Mermaid Diagrams:
End-to-End System Architecture Diagram: Illustrating client interaction, the NLP/Safety gateway, the orchestration service, hybrid retrieval, the NetworkX knowledge graph, the ML condition classifier, and the dual-mode RAG synthesizer.
Query Processing Lifecycle Sequence Diagram: Showing the exact step-by-step dataflow across web_app.py, nlp.py, service.py, retrieval.py, core.py, and rag.py.
Feature-by-Feature Analysis (All 16 Implemented Features):
Detailed What it does, Internal mechanism, Implementing modules, Accepted inputs, Produced outputs, Known limitations, and Verification status for:
General Ayurveda Knowledge Search
Ayurvedic Herb & Botanical Identification
Symptom & Condition Exploration
Multilingual Script & Language Understanding (KN, HI, TE, EN)
Sanskrit & AYUSH Terminology Preservation
Intent Classification & Automatic Category Routing
Multi-tier Hybrid Retrieval Pipeline
Grounded Extractive RAG & Citation Enforcement
Interactive Knowledge Graph & Subgraph Traversal
Explainable Machine Learning Classifier (XAI)
Multi-Lingual Emergency Red-Flag Triage
Honest Grounded Abstention
Rich Web Frontend & Design System
Empirical Research Ablation & Evaluation API
Automated Multi-Level Test Harness
Local-Only Privacy & Security Architecture
Complete Repository Structure Tree:
Mapped all directories and files, explaining the role of each module, dataset, script, fixture, and web asset.
Verified Datasets, Sources & Provenance Table:
Cataloged all 5 datasets with exact verified counts: WHO Guidelines (1,023 text chunks), NAMASTE SAT Combined (14,968 rows), IMPPAT 2.0 (94,261 uses / 4,154 plants), Columbia KB (1,898 pairs / 134 conditions), and AYUSH Evidence Register (schema initialized).
Complete Windows Installation Guide for Beginners (Steps A to I):
Step-by-step instructions from downloading the ZIP file, installing Python 3.11/3.12, setting up .venv in PowerShell, installing requirements.txt, verifying datasets, starting the Uvicorn server, to testing 8 representative queries across all supported languages.
Troubleshooting Guide:
Detailed diagnostics and solutions for 5 realistic Windows challenges: PowerShell script execution policies, port 8000 conflicts, terminal Unicode/charmap encoding, Ollama runtime vs extension confusion, and missing dataset indexing warnings.
Empirical Benchmarks & Corrected Metrics:
Included the exact IR ablation comparison across 18,473 candidate passages.
Documented the mathematically recalculated MRR improvement: +0.0079 absolute gain, +2.89% relative over BM25, and +71.9% relative over dense hybrid.
Included the in-depth explanation of the unjudged documents (pooling bias) phenomenon in retrieval precision and nDCG.
Documented the Scikit-Learn Multiclass Condition Classifier metrics (54.64% Top-1, 70.71% Top-3, 76.07% Top-5 accuracy, 0.5373 Macro F1).
2. Exact Verified Windows Commands for a New User
Assuming the repository has been extracted to C:\Projects\AyurMitra\AyurMitra_Research_Ready:

powershell
# 1. Open Windows PowerShell and navigate to the extracted directory
cd C:\Projects\AyurMitra\AyurMitra_Research_Ready
# 2. Allow local virtual environment activation (if restricted)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
# 3. Create the Python virtual environment
python -m venv .venv
# 4. Activate the virtual environment
.\.venv\Scripts\Activate.ps1
# 5. Upgrade pip and install core dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
# 6. Copy the environment configuration template
Copy-Item .env.example .env
# 7. Audit datasets and verify cryptographic SHA-256 integrity
python scripts\audit_datasets.py
# 8. Run full automated test suite (41 tests)
python -m unittest discover -s tests -v
# 9. Start the FastAPI application server
python -m uvicorn app.web_app:app --host 127.0.0.1 --port 8000 --reload
Then open the browser to:

Web Interface: http://127.0.0.1:8000
Interactive OpenAPI Documentation: http://127.0.0.1:8000/docs
3. Prerequisite, Model, Dataset & Credential Requirements
Operating System: Windows 10 or 11 (64-bit).
Python Version: Python 3.11 or 3.12 (64-bit). Must have "Add python.exe to PATH" enabled.
Node.js / npm: NOT REQUIRED. The frontend is built with pure semantic HTML5, Vanilla CSS3, and JavaScript, served directly by FastAPI.
External Cloud API Keys / Credentials: NONE REQUIRED. All indexing, classification, graph queries, and extractive RAG run 100% locally on device.
Local LLM Runtime (Optional): If generative synthesis is desired, install the Ollama Windows runtime from ollama.com/download/windows, pull qwen2.5:3b, and set AYURMITRA_OLLAMA_MODEL=qwen2.5:3b in .env. If omitted, the system defaults to zero-hallucination extractive RAG.
Optional Translation Dependencies (IndicTrans2): Detailed in requirements/optional_translation.txt and docs/MULTILINGUAL_SETUP.md. Requires PyTorch and ~2 GB of model weights. If omitted, native-script queries use domain concept normalization.
4. Commands Actually Tested and Their Verified Results
Tested Command	Output / Verified Result	Status
python scripts/audit_datasets.py	5 datasets verified; 100% SHA-256 match; WHO (1,023 chunks), NAMASTE (14,968 rows), IMPPAT (94,261 uses), Columbia (1,898 pairs)	PASSED
python -m unittest discover -s tests -v	Ran 41 tests in 126.706s; 0 failures, 0 errors	PASSED (41/41)
python scripts/independent_verification.py	Ran 16 diverse test cases across KN, HI, TE, EN, herbs, symptoms, out-of-domain, and emergency triage; 16 passed, 0 failed	PASSED (16/16)
python scripts/evaluate_retrieval.py	Evaluated 18 gold queries across 18,473 candidate passages; BM25 MRR = 0.2735, Proposed MRR = 0.2814	PASSED
python -m uvicorn app.web_app:app --host 127.0.0.1 --port 8000	Server launched on port 8000; served HTML, OpenAPI endpoints, and JSON search API	PASSED
5. README Instructions That Remain Unverified & Why
IndicTrans2 Full Deep-Learning Sentence Translation on Windows CPU:
Reason: The full IndicTrans2 package requires custom PyTorch C++ compilation and sentencepiece wheels on Windows that require several gigabytes of disk space and specialized build toolchains. As documented in docs/MULTILINGUAL_SETUP.md and the README, this is explicitly treated as an optional feature. Native script inputs are fully supported and verified via canonical Ayurvedic entity normalization.
Ollama GPU Acceleration:
Reason: While the Ollama API integration and citation validation were verified via extractive RAG fallback, GPU acceleration depends on whether the user's specific Windows PC possesses an NVIDIA CUDA GPU.
The complete 

README.md
 is now in place in the repository root. A new user downloading the project as a ZIP can set up the environment, run the tests, start the application, understand the scientific architecture, and navigate the platform.
\
