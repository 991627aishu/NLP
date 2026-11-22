import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.dense_retriever import DenseRetriever

log_path = Path("Data/evaluation/dense_retrieval_test.log")
log_path.parent.mkdir(parents=True, exist_ok=True)

with open(log_path, "w", encoding="utf-8") as f:
    f.write("=== AYURMITRA DENSE RETRIEVER AUDIT & BENCHMARK LOG ===\n")
    f.write(f"Timestamp: 2026-10-30\n\n")
    
    # 1. Test Sentence-Transformers requested backend
    f.write("--- Test 1: Requested Backend 'sentence_transformers' ---\n")
    d_st = DenseRetriever(backend="sentence_transformers")
    f.write(f"Requested: {d_st.requested_backend}\n")
    f.write(f"Backend Used: {d_st.backend_used}\n")
    f.write(f"Backend Warning: {d_st.backend_warning}\n")
    f.write(f"Total Chunks in Index: {len(d_st.chunks)}\n\n")
    
    # 2. Test TF-IDF backend
    f.write("--- Test 2: Requested Backend 'tfidf' ---\n")
    d_tfidf = DenseRetriever(backend="tfidf")
    f.write(f"Requested: {d_tfidf.requested_backend}\n")
    f.write(f"Backend Used: {d_tfidf.backend_used}\n")
    f.write(f"Backend Warning: {d_tfidf.backend_warning}\n")
    f.write(f"Doc Matrix Shape: {d_tfidf.doc_matrix.shape if d_tfidf.doc_matrix is not None else None}\n\n")
    
    # 3. Test Retrieval Across Queries
    test_queries = [
        ("en", "What is the role of Agni in digestion?"),
        ("hi", "अग्नि पाचन में क्या भूमिका निभाती है?"),
        ("kn", "ಅಗ್ನಿ ಜೀರ್ಣಕ್ರಿಯೆಯಲ್ಲಿ ಏನು ಪಾತ್ರ ವಹಿಸುತ್ತದೆ?"),
        ("hinglish", "Agni digestion mein kya role play karta hai?"),
        ("kanglish", "Agni digestion alli enu role ide?")
    ]
    
    f.write("--- Test 3: Retrieval Evaluation (TF-IDF Character N-Gram Backend) ---\n")
    for lang, q in test_queries:
        t0 = time.perf_counter()
        results = d_tfidf.retrieve(q, top_k=5)
        dt = (time.perf_counter() - t0) * 1000.0
        f.write(f"Query ({lang}): {q}\n")
        f.write(f"  Latency: {dt:.2f} ms\n")
        f.write(f"  Results returned: {len(results)}\n")
        for i, r in enumerate(results[:3], 1):
            f.write(f"    [{i}] score={r.get('score', 0):.4f} chunk_id={r.get('chunk_id')} source={r.get('source_id')}\n")
            f.write(f"        snippet: {repr(r.get('text', '')[:90])}\n")
        f.write("\n")

print(f"Logged to {log_path}")

