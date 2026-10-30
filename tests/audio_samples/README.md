# Voice test clips

No clips are committed: the build environment had no text-to-speech engine and no internet
access to edge-tts. Run `python tests/audio_samples/make_samples.py` (needs `pip install edge-tts`
and internet) to create 4 **synthetic** clips per language (EN/HI/KN) plus `manifest.json`.
`test_stt_roundtrip_on_samples` runs automatically once the clips and faster-whisper exist,
and is skipped otherwise. Synthetic speech is cleaner than real users' speech — report
STT results on these clips as an upper bound, not as field accuracy.
