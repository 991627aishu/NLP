from app.core.query_router import IntelligentQueryRouter

router = IntelligentQueryRouter()

test_queries = [
    # A. Ayurveda Domain
    "What is Vata dosha?",
    "What is Madhumeha?",
    "Explain the qualities of Pitta.",
    "What is Ashwagandha traditionally used for?",
    "ಕುಷ್ಠರೋಗ ಎಂದರೇನು?",
    "वात दोष क्या है?",
    # B. General Knowledge
    "What is machine learning?",
    "Explain Newton's laws.",
    "What is cloud computing?",
    "Explain photosynthesis.",
    "Explain the Indian education system.",
    # C. Mixed Domain
    "Compare traditional Ayurvedic terminology with modern medical terminology.",
    "How can AI help preserve traditional medical knowledge?",
    "Compare Ayurveda and modern medicine.",
    # D. Current Information
    "Who is the current Prime Minister of India?",
    "What are the latest developments in artificial intelligence?",
    # E. Safety / Medically Sensitive
    "Which Ayurvedic medicine cures cancer in a week?",
    "What dosage of Ashwagandha should a pregnant woman take?",
    # F. Unclear Query
    "hi",
    "???"
]

for q in test_queries:
    res = router.classify(q)
    print(f"[{res['route'].value}] -> \"{q}\"")
