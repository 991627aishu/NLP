# AyurMitra — user guide

## Start it
Windows (PowerShell, inside the project folder):
```powershell
.\run.ps1            # first run creates .venv and installs everything it needs
```
Then open **http://127.0.0.1:8000**. Linux/macOS: `./run.sh`.
If PowerShell refuses to run the script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.

Optional extras: `.\run.ps1 -Neural` (IndicTrans2 translation, neural embeddings), `.\run.ps1 -Voice`
(server speech recognition and voices; needs `winget install Gyan.FFmpeg`). Without them the site still
works and the **System status** chip (top right) says which fallback is in use.

## Ask
- Pick the language you'll ask in (English, हिन्दी, ಕನ್ನಡ, Hinglish) — this also sets the speech-recognition language.
- Type and press **Enter**, or tap the **microphone** (keyboard: **Alt+M**). Speak, then tap again or pause — recording stops
  after ~2 s of silence or 60 s. Check the text that appears, then press **Ask**.
- Each answer shows: the answer, the detected Ayurvedic terms (turmeric chips — click one to open it in the graph),
  **Sources & citations** (passage ID + page/row), **How this was answered** (language, protected terms, translation, backends,
  graph facts, latency) and **Read aloud** with pause/stop/speed.
- A *Machine-translated* badge means the Hindi/Kannada text came from neural MT and may contain errors.
  *English source text* means no neural MT was available, so the cited English sentence is shown as is.
- **Research options**: system configuration (B0/B1/P1/P2; default P2), answer language, web fallback (off by default;
  external sources are marked), answer writer, voice, auto-read, conversation mode (mic re-opens after the answer is read).

AyurMitra will not give doses, prescriptions or diagnoses, and it refers sudden or severe symptoms to emergency care — those
messages are always read aloud. When the sources don't cover a question, it says so instead of guessing.

## Knowledge graph
Search in English, Hindi, Kannada or IAST; filter node types; set depth 1–3. Click a node to see its definition, labels
and **every link with its source and locator**. A dashed clay line means the link still needs expert review.
*Show the path* finds how two concepts connect. **List view** gives a table (screen-reader friendly; default on phones).
Save the view as PNG or JSON.

## Symptom guidance
Describe how you feel; AyurMitra shows the Ayurvedic concepts traditional texts associate with it ("conceptual tendency").
It is not a diagnosis. These mappings are project-written and unreviewed — the page says so.

## Herbs & lifestyle
Search by common, Sanskrit or botanical name. A herb page lists IMPPAT records, recorded traditional uses (each with its
source row) and Ayurvedic Pharmacopoeia formulations. Recorded uses are **not** evidence that a plant works or is safe.
Daily-life topics (routine, seasons, diet, sleep, exercise, digestion, rejuvenation) show WHO terms and source passages.

## Research lab
Compare B0/B1/P1/P2 on any question, and read the measured pilot results, ablations, probe and error analysis
(downloadable CSV/JSON).

## Legacy interface
`.\run.ps1 -Streamlit` starts the original Streamlit app (unchanged).
