# AyurMitra — one-command setup + run (Windows PowerShell)
#   .\run.ps1                 # create .venv if needed, install core deps, build KG v2 if missing, start website+API
#   .\run.ps1 -Neural         # also install IndicTrans2 / sentence-transformers / LLM extras
#   .\run.ps1 -Voice          # also install faster-whisper / edge-tts / gTTS (needs ffmpeg: winget install Gyan.FFmpeg)
#   .\run.ps1 -Test           # run the full test suite instead of the server
#   .\run.ps1 -Streamlit      # run the legacy Streamlit interface
param([switch]$Neural, [switch]$Voice, [switch]$Test, [switch]$Streamlit, [int]$Port = 8000)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
if (-not (Test-Path ".venv")) { py -3.13 -m venv .venv 2>$null; if (-not $?) { python -m venv .venv } }
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r requirements.txt
if ($Neural) { & $py -m pip install -r requirements-neural.txt }
if ($Voice)  { & $py -m pip install -r requirements-voice.txt; if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) { Write-Warning "ffmpeg not on PATH — server speech recognition will be unavailable (browser recognition still works). Install: winget install Gyan.FFmpeg" } }
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) { Copy-Item .env.example .env }
if (-not (Test-Path "Data\processed\knowledge_graph_v2.pkl")) { & $py -m app.core.kg_builder }
if ($Test) { & $py -m pytest tests -q; exit $LASTEXITCODE }
if ($Streamlit) { & $py -m streamlit run web/app.py; exit $LASTEXITCODE }
Write-Host "AyurMitra: open http://127.0.0.1:$Port  (API docs: http://127.0.0.1:$Port/docs)"
& $py -m uvicorn api.main:app --host 127.0.0.1 --port $Port
