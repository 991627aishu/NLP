"""FastAPI backend for the conventional AyurMitra website."""
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')

from app.service import search_project
from app.language import detect_language, translator
from app.core import dataset_status
from app.knowledge_graph import graph_summary

WEB = ROOT / 'web'
app = FastAPI(title='AyurMitra', description='Source-grounded Ayurveda multilingual RAG research prototype', version='1.2.0')
app.mount('/static', StaticFiles(directory=str(WEB)), name='static')


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    category: Literal["general", "herbs", "disease"] = "general"
    answer_mode: Literal["ollama", "extractive"] = "ollama"


@app.get('/', include_in_schema=False)
def home():
    return FileResponse(WEB / 'index.html')


@app.get('/api/health')
def health():
    return {
        'status': 'ok',
        'app': 'AyurMitra',
        'version': '1.2.0',
        'translation_enabled': translator.enabled,
        'ollama_model_configured': bool(__import__('os').environ.get('AYURMITRA_OLLAMA_MODEL', '').strip()),
        'answer_generation': 'Ollama local model if configured & responsive; otherwise grounded extractive RAG',
        'dense_retrieval': 'optional sentence-transformers; hybrid BM25 + TF-IDF fallback always active',
    }


@app.get('/api/status')
def status():
    return {'datasets': dataset_status(), 'translation_enabled': translator.enabled}


@app.post('/api/language')
def language(request: SearchRequest):
    return detect_language(request.query)


@app.get('/api/knowledge-graph')
def knowledge_graph():
    return graph_summary()


@app.get('/api/evaluation')
def evaluation():
    eval_file = ROOT / 'data' / 'processed' / 'retrieval_evaluation.json'
    if eval_file.exists():
        import json
        return json.loads(eval_file.read_text(encoding='utf-8'))
    return {'status': 'pending', 'message': 'Run scripts/evaluate_retrieval.py to generate benchmarks.'}


@app.get('/api/classifier-metrics')
def classifier_metrics():
    metrics_file = ROOT / 'data' / 'processed' / 'classifier_evaluation.json'
    if metrics_file.exists():
        import json
        return json.loads(metrics_file.read_text(encoding='utf-8'))
    from app.classifier import classifier
    return classifier.train_and_evaluate()


@app.post('/api/search')
def search(request: SearchRequest):
    try:
        return search_project(request.query, request.category, request.answer_mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc