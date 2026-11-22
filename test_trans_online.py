from app.pipeline.translator import MultilingualTranslator

tr = MultilingualTranslator()
en_text = "Machine learning is a field of artificial intelligence concerned with algorithms that learn from data."

res_hi = tr.translate_answer_text(en_text, target_lang="hi")
print("Hindi translation:", res_hi["text"])

res_kn = tr.translate_answer_text(en_text, target_lang="kn")
print("Kannada translation:", res_kn["text"])
