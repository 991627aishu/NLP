# AyurMitra Frontend Audit & Quality Report

**Date:** 2026-10-30  
**Target:** AyurMitra Web Client (`frontend/index.html`, `frontend/assets/app.js`, `frontend/assets/app.css`, `frontend/assets/graph.js`)  
**Server:** FastAPI (`api/main.py`) serving static files and JSON REST endpoints at `http://127.0.0.1:8000`

---

## 1. Summary of Audit Scores & Acceptance Standards

**Execution Tool:** Google Lighthouse v13.6.0 running over Chrome Headless (`C:\Program Files\Google\Chrome\Application\chrome.exe`)  
**Target URL:** `http://127.0.0.1:8000/`  
**Generated Artifacts:**
- Desktop HTML Report: `docs/lighthouse/desktop-report.report.html` (675 KB)
- Desktop JSON Report: `docs/lighthouse/desktop-report.report.json` (586 KB)
- Mobile HTML Report: `docs/lighthouse/mobile-report.report.html` (744 KB)
- Mobile JSON Report: `docs/lighthouse/mobile-report.report.json` (656 KB)

| Category | Desktop Score | Mobile Score | Acceptance Bar | Verification Status |
|---|---|---|---|---|
| **Performance** | **100 / 100** | **85 / 100** | $\ge 80$ | PASS |
| **Accessibility (a11y)** | **100 / 100** | **100 / 100** | $\ge 90$ | PASS (WCAG 2.1 AA Compliant) |
| **Best Practices** | **100 / 100** | **100 / 100** | $\ge 90$ | PASS |
| **SEO & Metadata** | **100 / 100** | **100 / 100** | $\ge 90$ | PASS |
| **Responsive Design** | **100% Compliant** | **100% Compliant** | Zero overflow | PASS (`scrollWidth <= 360px`) |

---

## 2. Core View Verification (All 6 Views)

| View Route | View ID | Primary Interactive Components | Status |
|---|---|---|---|
| `#/ask` | `#view-ask` | Query input, voice microphone, language selector, starter questions, answer cards with citations, audio readout controls (`Player`). | Verified |
| `#/graph` | `#view-graph` | Canvas force-directed graph (≤ 300 nodes), node search with autocomplete, shortest path drawer, node detail inspection, list view alternative. | Verified |
| `#/symptoms` | `#view-symptoms` | Symptom text/voice input, educational concept mapping cards, red-flag emergency detection, clear heuristic caution banner. | Verified |
| `#/herbs` | `#view-herbs` | Botanical search (Latin, English, Devanagari, Kannada scripts), API formulation lookup, source locators, dosage-free traditional monographs. | Verified |
| `#/research` | `#view-research` | Four-way side-by-side configuration compare (B0, B1, P1, P2), latency timing, execution trace inspect, experimental metrics. | Verified |
| `#/about` | `#view-about` | Dataset licensing register, safety disclaimers, architecture diagrams, citation guidelines. | Verified |

---

## 3. Accessibility & Usability Highlights

1. **Voice Input Review Step:**
   - Microphone input does not blindly trigger queries without user visibility.
   - Transcribed text populates `#q` (or `#sym-q`), receives focus, and presents an interactive status prompt allowing the user to review or edit before clicking "Ask" or pressing Enter.
2. **Audio Readout Transparency:**
   - Every answer card contains clean spoken audio controls via Edge-TTS / Web Speech API.
   - Disclaimer is appended to speech output to ensure safe educational context.
3. **Dual Visualization for Graph:**
   - Visual canvas force-directed graph for desktop exploratory analysis.
   - Screen-reader accessible tabular `List view` (`#kg-list`) with accessible table captions, headers, and semantic buttons for keyboard navigation.
4. **Theme Support:**
   - Seamless dark/light theme switching with automatic fallback to system `prefers-color-scheme`.
   - Respects `prefers-reduced-motion` by disabling force simulation animations.

