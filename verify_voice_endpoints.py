import requests
import json
import os

BASE_URL = "http://127.0.0.1:8000"

# 1. Test /api/tts
tts_cases = [
    {"lang": "hi", "text": "प्रमाणित आयुर्वेदिक साहित्य के अनुसार वात शरीर के नियामक कारकों में से एक है।"},
    {"lang": "kn", "text": "ಪ್ರಾಮಾಣಿಕ ಆಯುರ್ವೇದ ಸಾಹಿತ್ಯದ ಪ್ರಕಾರ ವಾತವು ದೇಹದ ಮುಖ್ಯ ನಿಯಂತ್ರಕಗಳಲ್ಲಿ ಒಂದಾಗಿದೆ."},
    {"lang": "en", "text": "According to authentic Ayurvedic literature, Vata is one of the three regulatory factors."}
]

tts_out = []
for c in tts_cases:
    r = requests.post(f"{BASE_URL}/api/tts", json={"text": c["text"], "lang": c["lang"]})
    if r.status_code == 200:
        d = r.json()
        tts_out.append({
            "lang": c["lang"],
            "status": 200,
            "engine": d.get("engine"),
            "has_audio_base64": bool(d.get("audio_base64")),
            "audio_len": len(d.get("audio_base64", "")) if d.get("audio_base64") else 0,
            "client_speak": d.get("client_speak", False)
        })
    else:
        tts_out.append({"lang": c["lang"], "status": r.status_code, "err": r.text})

print("TTS Verification:", json.dumps(tts_out, indent=2))

# 2. Test /api/voice/transcribe with form field 'audio'
audio_dir = "Data/processed/cache/tts"
stt_out = []
if os.path.exists(audio_dir):
    files = [f for f in os.listdir(audio_dir) if f.endswith(".mp3")]
    for f in files[:3]:
        filepath = os.path.join(audio_dir, f)
        with open(filepath, "rb") as af:
            files_payload = {"audio": (f, af, "audio/mpeg")}
            r = requests.post(f"{BASE_URL}/api/voice/transcribe", files=files_payload, data={"lang_hint": "auto"})
            if r.status_code == 200:
                stt_out.append({"file": f, "status": 200, "resp": r.json()})
            else:
                stt_out.append({"file": f, "status": r.status_code, "err": r.text})

print("STT Verification:", json.dumps(stt_out, indent=2))
