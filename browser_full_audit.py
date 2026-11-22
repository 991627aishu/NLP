import os
import time
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = Path(r"C:\Users\texta\.gemini\antigravity\brain\e7397254-0b18-4a49-a82a-e4bb44e3b69a\screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
BASE_URL = "http://127.0.0.1:8000/#/ask"

tests = [
    {
        "id": "A",
        "name": "Hinglish to Hindi Devanagari",
        "query": "Madhumeh kya hota hai?",
        "expected_lang": "hi",
        "expected_script": "Devanagari",
        "screenshot": SCREENSHOTS_DIR / "test_A_madhumeh.png"
    },
    {
        "id": "B",
        "name": "Romanized Hindi (Pitta) to Devanagari",
        "query": "Pitta badhne par kya hota hai?",
        "expected_lang": "hi",
        "expected_script": "Devanagari",
        "screenshot": SCREENSHOTS_DIR / "test_B_pitta.png"
    },
    {
        "id": "C",
        "name": "Kanglish to Kannada script",
        "query": "Agni mandya andre enu?",
        "expected_lang": "kn",
        "expected_script": "Kannada",
        "screenshot": SCREENSHOTS_DIR / "test_C_agnimandya.png"
    },
    {
        "id": "D",
        "name": "Kannada script query",
        "query": "ವಾತ ದೋಷ ಎಂದರೇನು?",
        "expected_lang": "kn",
        "expected_script": "Kannada",
        "screenshot": SCREENSHOTS_DIR / "test_D_vata_kannada.png"
    },
    {
        "id": "E",
        "name": "Hindi Devanagari query",
        "query": "वात दोष क्या है?",
        "expected_lang": "hi",
        "expected_script": "Devanagari",
        "screenshot": SCREENSHOTS_DIR / "test_E_vata_hindi.png"
    },
    {
        "id": "F",
        "name": "English query",
        "query": "What is Vata dosha?",
        "expected_lang": "en",
        "expected_script": "English",
        "screenshot": SCREENSHOTS_DIR / "test_F_vata_english.png"
    }
]

print("Starting Browser Testing via Playwright + Installed Chrome ...\n")
results = []

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(BASE_URL)
    page.wait_for_selector("#q", timeout=15000)
    time.sleep(1)

    expected_cards = 0
    for t in tests:
        expected_cards += 1
        print(f"--- Running Test {t['id']}: {t['query']} ---")
        textarea = page.locator("#q")
        textarea.fill("")
        textarea.fill(t["query"])
        
        # Click ask/send button
        send_btn = page.locator("#send")
        send_btn.click()
        
        # Wait until the thread has expected_cards completed cards (not skeleton)
        page.wait_for_function(
            f"document.querySelectorAll('#thread .a:not([aria-busy=\\'true\\'])').length >= {expected_cards}",
            timeout=35000
        )
        time.sleep(1.2)
        
        # Find the latest answer card
        latest_card = page.locator("#thread .a:not([aria-busy='true'])").last
        card_text = latest_card.inner_text()
        badge_text = latest_card.locator(".badge").first.inner_text() if latest_card.locator(".badge").count() > 0 else ""
        
        # Take screenshot of the answer card
        latest_card.screenshot(path=str(t["screenshot"]))
        
        res_info = {
            "id": t["id"],
            "query": t["query"],
            "badge": badge_text,
            "text": card_text,
            "screenshot": str(t["screenshot"]),
            "has_abrita_corrupt": ("abritA" in card_text or "nadhunehA" in card_text or "prakAra" in card_text or "__आयुरटर्म" in card_text)
        }
        results.append(res_info)
        print(f"Badge: {badge_text}")
        print(f"Sample: {card_text[:180].replace(chr(10), ' ')}...")
        print(f"Screenshot saved to: {t['screenshot']}\n")

    # Consecutive Turn-by-Turn Switching Screenshot
    full_thread_screenshot = SCREENSHOTS_DIR / "test_I_consecutive_switching.png"
    page.locator("#thread").screenshot(path=str(full_thread_screenshot))
    print(f"Thread screenshot saved to: {full_thread_screenshot}")

    browser.close()

# Save JSON results
with open(SCREENSHOTS_DIR / "browser_test_results.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("\nALL BROWSER TESTS COMPLETE!")
