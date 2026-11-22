from app.pipeline.translator import MultilingualTranslator

tr = MultilingualTranslator()
en_text = "Machine learning is a field of artificial intelligence concerned with algorithms that learn from data."

hi_res = tr.translate_from_english(en_text, target_lang="hi")
print("Hindi:", hi_res.get("translated_text"))

kn_res = tr.translate_from_english(en_text, target_lang="kn")
print("Kannada:", kn_res.get("translated_text"))
