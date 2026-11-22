from app.pipeline.translator import MultilingualTranslator

tr = MultilingualTranslator()
en_text = "Machine learning (ML) is a field of study in artificial intelligence concerned with the development and study of statistical algorithms that can learn from data and generalize to unseen tasks."

hi_res = tr.translate_to_target(en_text, target_lang="hi")
print("Hindi translation:", hi_res.get("translated_text"))

kn_res = tr.translate_to_target(en_text, target_lang="kn")
print("Kannada translation:", kn_res.get("translated_text"))
