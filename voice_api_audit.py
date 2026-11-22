import requests
import json
import base64
import os

BASE_URL = "http://127.0.0.1:8000"

# Check TTS synthesis endpoint
tts_tests = [
    {"lang": "hi-IN", "text": "प्रमाणित आयुर्वेदिक साहित्य के अनुसार वात शरीर के तीन नियामक कारकों में से एक है।"},
    {"lang": "kn-IN", "text": "ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ ವಾತವು ದೇಹದ ಮೂರು ಮುಖ್ಯ ನಿಯಂತ್ರಕಗಳಲ್ಲಿ ಒಂದಾಗಿದೆ."},
    {"lang": "en-IN", "text": "According to authentic Ayurvedic literature, Vata is one of the three regulatory factors."}
]

tts_results = []
for t in tts_tests:
    try:
        r = requests.post(f"{BASE_URL}/api/voice/synthesize", json={"text": t["text"], "lang": t["lang"]}, timeout=20)
        tts_results.append({
            "lang": t["lang"],
            "status_code": r.status_code,
            "has_audio": ("audio_base64" in r.json() or "audio" in r.json() or r.headers.get("content-type", "").startswith("audio")) if r.status_code == 200 else False,
            "resp_keys": list(r.json().keys()) if r.status_code == 200 and "application/json" in r.headers.get("content-type", "") else []
        })
    except Exception as e:
        tts_results.append({"lang": t["lang"], "error": str(e)})

print("TTS Results:", json.dumps(tts_results, indent=2))

# Check STT transcribe endpoint with existing audio files if available
audio_dir = "Data/processed/cache/tts"
stt_results = []
if os.path.exists(audio_dir):
    files = [f for f in os.listdir(audio_dir) if f.endswith(".mp3")]
    print("Found cached audio files:", files[:5])
    for f in files[:3]:
        filepath = os.path.join(audio_dir, f)
        with open(filepath, "rb") as af:
            files_payload = {"file": (f, af, "audio/mpeg")}
            r = requests.post(f"{BASE_URL}/api/voice/transcribe", files=files_payload, timeout=30)
            if r.status_code == 200:
                stt_results.append({"file": f, "status": 200, "resp": r.json()})
            else:
                stt_results.append({"file": f, "status": r.status_code, "text": r.text})

print("STT Results:", json.dumps(stt_results, indent=2))
