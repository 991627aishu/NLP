#!/usr/bin/env bash
# AyurMitra — one-command setup + run (Linux / macOS)
#   ./run.sh            ./run.sh --neural   ./run.sh --voice   ./run.sh --test   ./run.sh --streamlit
set -euo pipefail
cd "$(dirname "$0")"
PORT="${AYUR_PORT:-8000}"
[ -d .venv ] || python3 -m venv .venv
PY=.venv/bin/python
$PY -m pip install --upgrade pip >/dev/null
$PY -m pip install -r requirements.txt
for a in "$@"; do
  case "$a" in
    --neural) $PY -m pip install -r requirements-neural.txt ;;
    --voice)  $PY -m pip install -r requirements-voice.txt; command -v ffmpeg >/dev/null || echo "WARNING: ffmpeg not found — server STT unavailable (browser STT still works)";;
  esac
done
[ -f .env ] || { [ -f .env.example ] && cp .env.example .env; }
[ -f Data/processed/knowledge_graph_v2.pkl ] || $PY -m app.core.kg_builder
for a in "$@"; do
  case "$a" in
    --test) exec $PY -m pytest tests -q ;;
    --streamlit) exec $PY -m streamlit run web/app.py ;;
  esac
done
echo "AyurMitra: open http://127.0.0.1:$PORT  (API docs: http://127.0.0.1:$PORT/docs)"
exec $PY -m uvicorn api.main:app --host 127.0.0.1 --port "$PORT"
