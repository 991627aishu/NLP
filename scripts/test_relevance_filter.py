import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import re
from app.pipeline.generator import _clean_passage_sentence, QUESTION_STOPWORDS

def is_promotional_or_irrelevant(s: str) -> bool:
    promo_pattern = re.compile(
        r"(\bwww\.|\bhttps?://|\b[a-zA-Z0-9_\-]+\.(?:com|net|org|in)\b|"
        r"visit\s|clinic|author's\s+other\s+books|piyushavarshi|aushadhalaya)",
        re.IGNORECASE
    )
    return bool(promo_pattern.search(s))

test_sentences = [
    "At least for three months.",
    "At least for six months.",
    "They can visit www.ayurvedicclinic.net or check out the author's other books listed on the same website.",
    "Ayurveda is an ancient Indian system of traditional medicine that emphasizes the importance of maintaining balance in the body through a holistic approach to health."
]

query = "What is Ayurveda?"
concept_keywords = {"ayurveda"}

clean_facts = []
for s in test_sentences:
    if is_promotional_or_irrelevant(s):
        print(f"DROPPED (promotional): {s}")
        continue
    # Require topical relevance: must contain at least one concept keyword
    overlap = sum(1 for kw in concept_keywords if len(kw) >= 3 and kw in s.lower())
    if overlap == 0:
        print(f"DROPPED (irrelevant topic): {s}")
        continue
    clean_facts.append(s)
    print(f"KEPT: {s}")

print("\nFinal clean_facts:")
for f in clean_facts:
    print("-", f)

