from app.core.matcher import TerminologyMatcher

m = TerminologyMatcher()
print("Kushtha in Kannada:", m.find_terms("ಕುಷ್ಠರೋಗ ಎಂದರೇನು?"))
print("Kushtha in Kannada short:", m.find_terms("ಕುಷ್ಠ ಎಂದರೇನು?"))
print("Kushtha in Hindi:", m.find_terms("कुष्ठ रोग क्या होता है?"))
print("Kushtha in English:", m.find_terms("What is Kushtha?"))
