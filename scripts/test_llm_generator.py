import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pipeline.llm_generator import LLMGenerator, post_check, build_user_prompt
from app.pipeline.generator import EvidenceGroundedGenerator

log_path = Path("Data/evaluation/llm_generator_test.log")
log_path.parent.mkdir(parents=True, exist_ok=True)

with open(log_path, "w", encoding="utf-8") as f:
    f.write("=== AYURMITRA LLM GENERATOR & SAFETY POST-CHECK LOG ===\n")
    f.write(f"Timestamp: 2026-10-30\n\n")
    
    # 1. Check availability
    f.write("--- 1. Provider Availability Check ---\n")
    gen_ant = LLMGenerator(provider="anthropic")
    av_ant = gen_ant.available()
    f.write(f"Anthropic Provider: {av_ant}\n")
    
    gen_oll = LLMGenerator(provider="ollama")
    av_oll = gen_oll.available()
    f.write(f"Ollama Provider: {av_oll}\n\n")
    
    # 2. Test Grounding & Citation Post-Checking
    f.write("--- 2. Citation Post-Check & Safety Gate Tests ---\n")
    allowed_ids = {"WHO_CHUNK_0012", "IMPPAT_PLT_003254"}
    
    # Test case A: Perfectly grounded sentence
    s_good = "Agni is described in Ayurvedic texts as the bodily fire responsible for digestion and metabolism [WHO_CHUNK_0012]."
    res_good = post_check(s_good, allowed_ids)
    f.write(f"Test A (Valid citation):\n  Input: {s_good}\n  Kept: {res_good['sentences']}\n  Dropped: {res_good['dropped']}\n  Insufficient: {res_good['insufficient']}\n\n")
    
    # Test case B: Uncited sentence (hallucination)
    s_uncited = "Agni also cures cardiovascular diseases and lowers blood cholesterol."
    res_uncited = post_check(s_uncited, allowed_ids)
    f.write(f"Test B (Uncited hallucination):\n  Input: {s_uncited}\n  Kept: {res_uncited['sentences']}\n  Dropped: {res_uncited['dropped']}\n  Insufficient: {res_uncited['insufficient']}\n\n")
    
    # Test case C: Unknown/fabricated citation
    s_fake_cite = "Agni regulates circadian rhythms [FABRICATED_CHUNK_9999]."
    res_fake = post_check(s_fake_cite, allowed_ids)
    f.write(f"Test C (Fabricated citation):\n  Input: {s_fake_cite}\n  Kept: {res_fake['sentences']}\n  Dropped: {res_fake['dropped']}\n  Insufficient: {res_fake['insufficient']}\n\n")
    
    # Test case D: Forbidden medical claim / dosage
    s_forbidden = "Take 500 mg twice daily as it cures acute digestive disorders [WHO_CHUNK_0012]."
    res_forbidden = post_check(s_forbidden, allowed_ids)
    f.write(f"Test D (Dosage and cure claim):\n  Input: {s_forbidden}\n  Kept: {res_forbidden['sentences']}\n  Dropped: {res_forbidden['dropped']}\n  Insufficient: {res_forbidden['insufficient']}\n\n")
    
    # Test case E: Model abstention trigger
    s_abstain = "INSUFFICIENT_EVIDENCE"
    res_abstain = post_check(s_abstain, allowed_ids)
    f.write(f"Test E (Abstention):\n  Input: {s_abstain}\n  Insufficient: {res_abstain['insufficient']}\n\n")
    
    # 3. Test Grounded Extractive Generator Fallback
    f.write("--- 3. Extractive Grounded Generator Fallback ---\n")
    eg = EvidenceGroundedGenerator()
    dummy_passages = [
        {"chunk_id": "WHO_CHUNK_0012", "source_id": "WHO_Benchmark", "locator": "Section 2.1",
         "text": "Agni refers to the biological fire responsible for digestion and cellular metabolism in Ayurveda."}
    ]
    ext_ans = eg.generate_answer("What is Agni?", dummy_passages, target_lang="en")
    f.write(f"Extractive answer generated:\n  Answer: {repr(ext_ans.get('answer_en', ext_ans.get('answer', ''))[:120])}...\n")
    f.write(f"  Citations: {ext_ans.get('citations')}\n")
    f.write(f"  Language: {ext_ans.get('language')}\n")

print(f"Logged to {log_path}")
