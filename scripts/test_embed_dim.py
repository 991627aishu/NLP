import os
from pathlib import Path

for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if line.strip().startswith("GEMINI_API_KEY="):
        os.environ["GEMINI_API_KEY"] = line.strip().split("=", 1)[1].strip().strip("\"'")

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
resp = client.models.embed_content(
    model="gemini-embedding-001",
    contents="Ayurveda is a traditional system of medicine.",
    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
)
print("resp type:", type(resp))
print("fields:", [x for x in dir(resp) if not x.startswith("_")])
if hasattr(resp, "embeddings") and resp.embeddings:
    print("resp.embeddings count:", len(resp.embeddings))
    print("embedding 0 dim:", len(resp.embeddings[0].values))
if hasattr(resp, "embedding") and resp.embedding:
    print("resp.embedding dim:", len(resp.embedding.values))
