from app.pipeline.web_search import WebSearchFallback
import traceback

ws = WebSearchFallback()
try:
    res = ws.search("Kushtha", max_results=3)
    print("Result:", res)
except Exception as e:
    traceback.print_exc()
