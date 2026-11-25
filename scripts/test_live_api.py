import urllib.request, json, time

queries = [
    ('ಕಾಮಲೆ ಎಂದರೇನು?', 'kn'),
    ('ಜ್ವರ ಎಂದರೇನು?', 'kn'),
    ('वात दोष क्या है?', 'hi'),
    ('What is Kushtha?', 'en'),
    ('What is loose motion?', 'en'),
    ('What is machine learning?', 'en')
]

for q, expected_lang in queries:
    t0 = time.time()
    payload = json.dumps({'query': q, 'mode': 'P2', 'target_lang': 'auto'}).encode('utf-8')
    req = urllib.request.Request('http://127.0.0.1:8000/api/ask', data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        dur = time.time() - t0
        print('=' * 50, flush=True)
        print(f"QUERY: {q}", flush=True)
        print(f"STATUS: OK ({dur:.2f}s)", flush=True)
        print(f"LANG: {data.get('detected_language')} -> {data.get('target_language')}", flush=True)
        print(f"TERM: {data.get('detected_term')}", flush=True)
        print(f"ABSTAINED: {data.get('abstained')}", flush=True)
        print(f"GENERATOR: {data.get('generator_used')}", flush=True)
        print(f"CITATIONS: {len(data.get('citations', []))}", flush=True)
        ans = data.get('answer', '')
        print(f"ANSWER: {ans[:180]}...", flush=True)
    except Exception as e:
        dur = time.time() - t0
        print('=' * 50, flush=True)
        print(f"QUERY: {q} FAILED in {dur:.2f}s: {e}", flush=True)
