"""
AyurMitra — Stage-by-Stage Performance Profiler
"""
import time
import json
import sys
from pathlib import Path

# Add project root to sys.path
root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from app.pipeline.rag_pipeline import AyurMitraPipeline

print("=== 1. Initializing Pipeline ===")
t0 = time.perf_counter()
pipeline = AyurMitraPipeline()
t_init = time.perf_counter() - t0
print(f"Pipeline initialized in {t_init:.3f}s\n")

test_queries = [
    ("English Ayurvedic query", "What is Vata dosha?", "en"),
    ("Kannada single-term query", "ಕಾಮಣಿ", "kn"),
    ("Hindi Ayurvedic query", "वात दोष के मुख्य लक्षण क्या हैं?", "hi"),
    ("Hinglish query", "Pitta badhne par kya symptoms hote hain?", "hinglish"),
    ("Kanglish query", "Agni mandya andre enu?", "kanglish"),
]

for label, q, lang in test_queries:
    print(f"=== Profiling: {label} ({q}) ===")
    t_start = time.perf_counter()
    res = pipeline.process_query(q, system_mode="P2", target_lang=lang)
    t_total = time.perf_counter() - t_start
    print(f"Total time: {t_total:.3f}s")
    print(f"Generator: {res.get('generator_used')}")
    print(f"Route: {res.get('route_category')} ({res.get('route_label')})")
    print(f"Passages: {len(res.get('retrieved_passages', []))}, Citations: {len(res.get('citations', []))}")
    print(f"Answer snippet: {res.get('answer', '')[:120]}...\n")
