from app.core.matcher import TerminologyMatcher

m = TerminologyMatcher()
terms = m.find_terms("ಕುಷ್ಠರೋಗ")
print("find_terms('ಕುಷ್ಠರೋಗ'):", terms)

terms2 = m.find_terms("Kushtha")
print("find_terms('Kushtha'):", terms2)

terms3 = m.find_terms("ಕುಷ್ಠ")
print("find_terms('ಕುಷ್ಠ'):", terms3)
