import json
import os
import sys
import time
from playwright.sync_api import sync_playwright

SCREENSHOT_DIR = r"C:\Users\texta\.gemini\antigravity\brain\e7397254-0b18-4a49-a82a-e4bb44e3b69a\screenshots"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

TESTS = [
    {
        "id": "1_roga_english",
        "query": "What is roga?",
        "expected_kw": ["roga", "vyadhi", "ayurveda", "disease", "dosha"],
        "forbidden_kw": ["mopacho", "congo", "dance", "brazzaville"],
        "screenshot": os.path.join(SCREENSHOT_DIR, "v2_1_roga_english.png")
    },
    {
        "id": "2_roga_hindi",
        "query": "रोग मतलब क्या होता है?",
        "expected_kw": ["रोग", "दोष", "आयुर्वेद", "व्याधि", "असंतुलन"],
        "forbidden_kw": ["कुरु", "kuru", "पापुआ", "न्यूरोडीजेनेरेटिव", "mopacho"],
        "screenshot": os.path.join(SCREENSHOT_DIR, "v2_1_roga_hindi.png")
    },
    {
        "id": "3_roga_kannada",
        "query": "ರೋಗ ಎಂದರೇನು?",
        "expected_kw": ["ರೋಗ", "ದೋಷ", "ಆಯುರ್ವೇದ", "ಅಸಮತೋಲನ", "ವ್ಯಾಧಿ"],
        "forbidden_kw": ["ಮೋಪಾಚೊ", "mopacho", "ಕುರು", "kuru"],
        "screenshot": os.path.join(SCREENSHOT_DIR, "v2_1_roga_kannada.png")
    },
    {
        "id": "4_kuru_disease",
        "query": "What is Kuru disease?",
        "expected_kw": ["kuru", "neurodegenerative", "prion"],
        "forbidden_kw": ["mopacho", "dance"],
        "screenshot": os.path.join(SCREENSHOT_DIR, "v2_1_kuru_disease.png")
    },
    {
        "id": "5_mopacho",
        "query": "What is Mopacho?",
        "expected_kw": ["mopacho", "dance", "congo"],
        "forbidden_kw": ["kuru", "ayurveda"],
        "screenshot": os.path.join(SCREENSHOT_DIR, "v2_1_mopacho.png")
    }
]

def run_browser_tests():
    print("Launching Chromium browser via Playwright...")
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        for test in TESTS:
            qid = test["id"]
            query = test["query"]
            print(f"\n[TEST {qid}] Input: '{query}'")

            # Fresh page load for each test to prevent session text pollution
            page.goto("http://127.0.0.1:8000", wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(500)

            # Input textarea is #q
            textarea = page.locator("#q")
            textarea.fill(query)

            # Click ask / send button
            send_btn = page.locator("#send")
            send_btn.click()

            # Wait for response article to appear and finish loading
            page.wait_for_selector("article.a:not([aria-busy='true'])", timeout=15000)
            page.wait_for_timeout(1000)

            # Target the specific answer container
            last_card = page.locator("article.a").last
            answer_text = last_card.locator(".answer-body").inner_text()
            full_card_text = last_card.inner_text()

            # Verify expected vs forbidden keywords in the generated answer
            check_text = (answer_text + " " + full_card_text).lower()
            matched_expected = [kw for kw in test["expected_kw"] if kw.lower() in check_text]
            matched_forbidden = [f_kw for f_kw in test["forbidden_kw"] if f_kw.lower() in check_text]

            passed_expected = len(matched_expected) > 0
            has_forbidden = len(matched_forbidden) > 0

            passed = passed_expected and not has_forbidden
            status = "PASS" if passed else "FAIL"

            page.screenshot(path=test["screenshot"], full_page=True)
            print(f"  Status: {status} | Expected: {matched_expected} | Forbidden: {matched_forbidden}")
            print(f"  Screenshot saved: {os.path.basename(test['screenshot'])}")
            if has_forbidden:
                print(f"  WARNING: Detected forbidden keywords: {matched_forbidden}")

            results.append({
                "test_id": qid,
                "query": query,
                "status": status,
                "passed_expected": passed_expected,
                "matched_expected": matched_expected,
                "has_forbidden": has_forbidden,
                "matched_forbidden": matched_forbidden,
                "answer_snippet": answer_text[:200],
                "screenshot": test["screenshot"]
            })

        browser.close()

    print("\nBrowser test run finished.")
    with open("browser_qa_v2_1_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    all_passed = all(r["status"] == "PASS" for r in results)
    print(f"Total Tests: {len(results)} | Passed: {sum(1 for r in results if r['status'] == 'PASS')} | All Passed: {all_passed}")

if __name__ == "__main__":
    run_browser_tests()
