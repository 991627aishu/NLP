"""Website smoke tests (Playwright, headless Chromium). Skipped if Playwright/Chromium is unavailable.

Run alone:  python -m pytest tests/test_web_smoke.py -q
"""
import socket
import threading
import time

import pytest

pw = pytest.importorskip("playwright.sync_api")

FAKE_MIC = """
window.SpeechRecognition = class {
  constructor(){ this.lang='en-IN'; }
  start(){ setTimeout(()=>{ this.onresult && this.onresult({resultIndex:0, results:[Object.assign([{transcript:'What is Ojas?'}],{isFinal:true})]});
                            this.onend && this.onend(); }, 150); }
  stop(){ this.onend && this.onend(); } abort(){}
};
Object.defineProperty(window, 'speechSynthesis', { configurable: true,
  value: { speak(){}, cancel(){}, pause(){}, resume(){}, getVoices(){ return []; }, paused: false } });
"""


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture(scope="module")
def base_url():
    import uvicorn
    from api.main import app
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True); th.start()
    for _ in range(120):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close(); break
        except OSError:
            time.sleep(0.25)
    time.sleep(1.0)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True; th.join(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:  # pragma: no cover
            pytest.skip(f"Chromium not available: {e}")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_init_script(FAKE_MIC)
    pg = ctx.new_page()
    pg.route("**/fonts.googleapis.com/**", lambda r: r.abort()); pg.route("**/fonts.gstatic.com/**", lambda r: r.abort())
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    yield pg
    assert not errors, errors
    ctx.close()


@pytest.mark.parametrize("q,lang", [("What is Ojas?", "en"), ("पित्त दोष के कार्य क्या हैं?", "hi"),
                                    ("ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?", "kn")])
def test_ask_in_three_languages(page, base_url, q, lang):
    page.goto(base_url + "/#/ask")
    page.fill("#q", q); page.click("#send")
    card = page.wait_for_selector("article.a", timeout=30000)
    assert card.get_attribute("lang") == lang
    assert page.locator("article.a details.fold summary").first.is_visible()


def test_emergency_abstention_card(page, base_url):
    page.goto(base_url + "/#/ask")
    page.fill("#q", "I have a sudden severe headache"); page.click("#send")
    page.wait_for_selector("article.a.emergency", timeout=30000)
    assert "emergency" in page.inner_text("article.a.emergency").lower()


def test_kg_node_panel(page, base_url):
    page.goto(base_url + "/#/graph?center=Pitta")
    page.wait_for_selector("#kg-panel h2", timeout=30000)
    assert "Pitta" in page.inner_text("#kg-panel h2")
    assert page.locator("#kg-panel .edge-list li").count() > 0
    page.click("#kg-listbtn"); assert page.locator("#kg-list table").is_visible()


def test_voice_with_mocked_mic(page, base_url):
    page.goto(base_url + "/#/ask")
    assert page.get_attribute("#mic", "aria-label")
    page.click("#mic")
    page.wait_for_function("document.querySelector('#q').value === 'What is Ojas?'", timeout=5000)
    page.click("#send")
    page.wait_for_selector("article.a", timeout=30000)


def test_herbs_and_symptoms_pages(page, base_url):
    page.goto(base_url + "/#/herbs?herb=ashwagandha")
    page.wait_for_selector("#herb-detail h2", timeout=30000)
    assert "Withania" in page.inner_text("#herb-detail h2")
    page.goto(base_url + "/#/symptoms")
    page.fill("#sym-q", "I have dry skin"); page.click("#sym-form button[type=submit]")
    page.wait_for_selector("#sym-out .edge-list li", timeout=30000)


def test_mobile_no_horizontal_scroll(browser, base_url):
    ctx = browser.new_context(viewport={"width": 360, "height": 780}, is_mobile=True)
    pg = ctx.new_page(); pg.route("**/fonts.g*/**", lambda r: r.abort())
    for v in ("ask", "graph", "herbs", "research", "about"):
        pg.goto(f"{base_url}/#/{v}"); pg.wait_for_timeout(600)
        assert pg.evaluate("document.documentElement.scrollWidth") <= 360, v
    assert pg.locator(".mobile-nav").is_visible()
    ctx.close()
