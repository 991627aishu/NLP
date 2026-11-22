import urllib.request, json, os
from pathlib import Path

tok = (Path.home() / '.cache' / 'huggingface' / 'token').read_text().strip()

models = [
    'ai4bharat/indictrans2-indic-en-dist-200M',
    'ai4bharat/indictrans2-en-indic-dist-200M',
    'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
]

for m in models:
    url = f'https://huggingface.co/api/models/{m}'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            gated = data.get('gated', False)
            private = data.get('private', False)
            print(f'Model: {m} -> STATUS 200 OK (Gated: {gated}, Private: {private})')
    except urllib.error.HTTPError as e:
        print(f'Model: {m} -> HTTP {e.code}: {e.reason}')
    except Exception as e:
        print(f'Model: {m} -> Error: {e}')

