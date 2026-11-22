from app.pipeline.translator import MultilingualTranslator

tr = MultilingualTranslator()
print("Trans HI:", tr.translate_to_english("मशीन लर्निंग क्या है?", source_lang="hi"))
print("Trans KN:", tr.translate_to_english("ಯಂತ್ರ ಕಲಿಕೆ ಎಂದರೇನು?", source_lang="kn"))
