from app.pipeline.web_search import WebSearchFallback

ws = WebSearchFallback()
res = ws.search("Kushtha skin disease Ayurveda", max_results=3)
print("Success:", res.get("success"))
print("Total found:", res.get("total_found"))
for p in res.get("passages", []):
    print(" - Title:", p.get("title"))
    print("   Snippet:", p.get("snippet")[:150])
