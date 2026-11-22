import urllib.request
import json

print("Testing TTS Synthesize Endpoint ...")
tts_tests = [
    ("मधुमेह आयुर्वेद में एक प्रमुख विकार है।", "hi", "hi-IN"),
    ("ಮಧುಮೇಹವು ಆಯುರ್ವೇದದಲ್ಲಿ ಪ್ರಮುಖ ಕಾಯಿಲೆಯಾಗಿದೆ.", "kn", "kn-IN"),
    ("Vata dosha governs movement in the body.", "en", "en-IN"),
]

for text, lang, exp_tts in tts_tests:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/tts",
        data=json.dumps({"text": text, "lang": lang, "voice": "female"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"TTS [{lang}]: backend={data.get('backend')}, chunks={len(data.get('chunks', []))}, browser_lang={data.get('browser_lang')}")

print("\nTesting STT Transcribe with empty check ...")
try:
    # boundary multipart form
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="lang_hint"\r\n\r\n'
        f"hi\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="empty.webm"\r\n'
        f"Content-Type: audio/webm\r\n\r\n"
        f"\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")

    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/voice/transcribe",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"STT validation response: {data}")
except Exception as e:
    print(f"STT validation exception: {e}")
