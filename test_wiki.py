from app.pipeline.web_search import WebSearchFallback

ws = WebSearchFallback()
res = ws.search_encyclopedic_wikipedia("machine learning", max_results=2)
print("Wikipedia ML count:", len(res))
if res:
    print(" - Title:", res[0].get("title"))
    print(" - Snippet:", res[0].get("snippet")[:200])

res2 = ws.search_encyclopedic_wikipedia("Newton's laws of motion", max_results=2)
print("Wikipedia Newton count:", len(res2))
if res2:
    print(" - Title:", res2[0].get("title"))
    print(" - Snippet:", res2[0].get("snippet")[:200])
