"""Generate SYNTHETIC test clips (edge-tts; needs internet + pip install edge-tts).

    python tests/audio_samples/make_samples.py

Files are named synthetic_<lang>_<n>.mp3 and listed in manifest.json with the text
that was spoken, so tests/test_phase5_6_voice_api.py::test_stt_roundtrip_on_samples
can check the STT -> term-normalisation round trip. They are machine speech, not
real recordings — label them as such in any report.
"""
import asyncio
import json
from pathlib import Path

SAMPLES = {
    "en": ["What is the role of Agni in digestion?", "What are the functions of Pitta dosha?",
           "What is Ojas according to Ayurveda?", "I have a sudden severe headache"],
    "hi": ["पित्त दोष के कार्य क्या हैं?", "अग्नि क्या है?", "ओजस क्या है?", "मुझे अचानक तेज सिरदर्द हो रहा है"],
    "kn": ["ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?", "ಅಗ್ನಿ ಎಂದರೇನು?", "ಓಜಸ್ಸು ಎಂದರೇನು?", "ನನಗೆ ತೀವ್ರ ತಲೆನೋವು ಇದೆ"],
}
VOICES = {"en": "en-IN-NeerjaNeural", "hi": "hi-IN-SwaraNeural", "kn": "kn-IN-SapnaNeural"}


async def main():
    import edge_tts
    here = Path(__file__).parent
    manifest = []
    for lang, texts in SAMPLES.items():
        for i, t in enumerate(texts, 1):
            out = here / f"synthetic_{lang}_{i}.mp3"
            await edge_tts.Communicate(t, VOICES[lang]).save(str(out))
            manifest.append({"file": out.name, "lang": lang, "text": t, "synthetic": True, "voice": VOICES[lang]})
    (here / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(manifest)} synthetic clips")


if __name__ == "__main__":
    asyncio.run(main())
