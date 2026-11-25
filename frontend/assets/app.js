/* AyurMitra web client — no framework, no build step. */
(function () {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const store = { get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
                  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* storage unavailable */ } } };
  let UI = store.get("ayur.ui", "en");
  const t = k => (I18N[UI] && I18N[UI][k]) || I18N.en[k] || k;

  // ── API ────────────────────────────────────────────────────────────────────
  const inflight = {};
  async function api(path, { method = "GET", body, form, key, params } = {}) {
    if (key && inflight[key]) inflight[key].abort();
    const ctl = new AbortController(); if (key) inflight[key] = ctl;
    const url = params ? path + "?" + new URLSearchParams(params) : path;
    let res;
    try {
      res = await fetch(url, { method, signal: ctl.signal, headers: body ? { "content-type": "application/json" } : undefined,
                               body: body ? JSON.stringify(body) : form });
    } catch (e) {
      if (e.name === "AbortError") throw e;
      showOffline(true); throw new Error(t("backend_offline"));
    }
    showOffline(false);
    let data = {}; try { data = await res.json(); } catch { /* non-JSON */ }
    if (!res.ok) {
      if (res.status === 502 || res.status === 504) {
        throw new Error(data.message || `Render gateway timeout (HTTP ${res.status}): The backend took longer to respond or was waking up. Please retry.`);
      }
      throw new Error(data.message || data.detail || `Request failed (${res.status})`);
    }
    return data;
  }
  function showOffline(on) { const o = $("#offline"); o.hidden = !on; if (on) o.textContent = t("backend_offline"); }
  const debounce = (fn, ms) => { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); }; };

  // light markdown: **bold**, `code`, [text](url), lists, paragraphs
  function md(src) {
    const lines = esc(src).split("\n"); let html = "", inList = false;
    for (let raw of lines) {
      let l = raw.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, '<code class="mono">$1</code>')
                 .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
                 .replace(/(^|\s)\*([^*]+)\*/g, "$1<em>$2</em>");
      if (/^\s*[-•]\s+/.test(raw)) { if (!inList) { html += "<ul>"; inList = true; } html += "<li>" + l.replace(/^\s*[-•]\s+/, "") + "</li>"; continue; }
      if (inList) { html += "</ul>"; inList = false; }
      html += l.trim() ? "<p>" + l + "</p>" : "";
    }
    return html + (inList ? "</ul>" : "");
  }

  // ── i18n / theme / router ──────────────────────────────────────────────────
  function applyI18n() {
    document.documentElement.lang = UI;
    $$("[data-i18n]").forEach(e => { e.textContent = t(e.dataset.i18n); });
    $$("[data-i18n-ph]").forEach(e => { e.placeholder = t(e.dataset.i18nPh); });
    $("#ui-lang").value = UI; renderStarters(); renderSymStarters();
  }
  $("#ui-lang").addEventListener("change", e => { UI = e.target.value; store.set("ayur.ui", UI); applyI18n(); });
  const theme = store.get("ayur.theme", null); if (theme) document.documentElement.dataset.theme = theme;
  $("#theme").addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme === "dark" ||
      (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.dataset.theme = dark ? "light" : "dark"; store.set("ayur.theme", document.documentElement.dataset.theme);
    graph && graph.draw();
  });
  const VIEWS = ["ask", "graph", "symptoms", "herbs", "research", "about"]; const loaded = {};
  function route() {
    const [path, query] = (location.hash.replace(/^#\/?/, "") || "ask").split("?");
    const v = VIEWS.includes(path) ? path : "ask"; const params = new URLSearchParams(query || "");
    VIEWS.forEach(x => { $("#view-" + x).hidden = x !== v; });
    $$("#nav a, #mnav a").forEach(a => a.setAttribute("aria-current", a.getAttribute("href") === "#/" + v ? "page" : "false"));
    if (!loaded[v]) { loaded[v] = true; ({ graph: initGraph, herbs: initHerbs, research: initResearch, about: initAbout }[v] || (() => {}))(params); }
    if (v === "graph" && params.get("center")) loadGraph(params.get("center"));
    if (v === "herbs") {
      const qVal = params.get("q") || params.get("context");
      if (qVal) {
        const hq = $("#herb-q");
        if (hq) {
          hq.value = qVal;
          hq.dispatchEvent(new Event("input"));
        }
      }
      if (params.get("context") || params.get("dosha")) {
        loadHerbContext(params.get("context") || qVal, params.get("dosha"));
      } else if (params.get("herb")) {
        showHerb(params.get("herb"));
      }
      if (params.get("tab") === "lifestyle") {
        setTimeout(() => {
          const lsec = $("#lifestyle-search-section") || $("#topics");
          if (lsec) lsec.scrollIntoView({ behavior: "smooth" });
        }, 350);
      }
    }
    $("#main").focus({ preventScroll: true }); window.scrollTo(0, 0);
  }
  window.addEventListener("hashchange", route);

  // ── status chip ────────────────────────────────────────────────────────────
  const NAMES = { neural_mt: "Neural translation (IndicTrans2)", embeddings: "Multilingual embeddings", stt: "Server speech recognition",
                  tts: "Server speech synthesis", llm: "Language-model writer", web: "Web fallback", knowledge_graph: "Knowledge graph",
                  safety_gate: "Safety checks" };
  let HEALTH = null;
  async function loadHealth() {
    try {
      HEALTH = await api("/api/health"); const b = HEALTH.backends;
      const core = ["neural_mt", "embeddings"].every(k => b[k].live);
      $("#status-dot").className = "dot " + (b.safety_gate.live ? (core ? "ok" : "warn") : "bad");
      $("#status-pop").innerHTML = `<h3>${t("status")}</h3><ul>` + Object.keys(NAMES).map(k => {
        const x = b[k] || {}; const note = x.note || x.reason || (k === "tts" && !x.live ? "Using the browser's voice instead" : "") ||
          (k === "stt" && !x.live ? "Using in-browser recognition (Chrome/Edge) instead" : "");
        return `<li><span class="dot ${x.live ? "ok" : "warn"}" style="margin-top:7px"></span><span><b>${NAMES[k]}</b> — ${x.live ? "live" : "fallback active"}${x.backend ? ` <small>(${esc(x.backend)})</small>` : ""}${note ? `<br><small>${esc(note)}</small>` : ""}</span></li>`;
      }).join("") + `</ul><p class="muted" style="margin-top:8px">${t("first_slow")}</p>`;
    } catch { $("#status-dot").className = "dot bad"; }
  }
  $("#status-btn").addEventListener("click", () => { const p = $("#status-pop"); p.hidden = !p.hidden; $("#status-btn").setAttribute("aria-expanded", String(!p.hidden)); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") { $("#status-pop").hidden = true; $("#status-btn").setAttribute("aria-expanded", "false"); } });

  // ── speech output ──────────────────────────────────────────────────────────
  const Player = {
    audio: null, queue: [], utter: null, rate: 1, onend: null, el: null, _playId: 0,
    stop() {
      this._playId++;
      this._tailPending = false;
      if (this.audio) { this.audio.onended = null; this.audio.pause(); this.audio = null; }
      this.queue = [];
      this.utter = null;
      if ("speechSynthesis" in window) speechSynthesis.cancel();
      this._ui("idle");
    },
    _ui(state, customMsg) {
      if (!this.el) return;
      this.el.dataset.state = state;
      const p = $(".pp", this.el);
      if (p) p.textContent = state === "paused" ? t("resume") : t("pause");
      const vs = $(".voice-status", this.el);
      if (vs) {
        if (customMsg) vs.textContent = customMsg;
        else if (state === "loading") vs.textContent = "🔊 Generating neural voice...";
        else if (state === "playing") vs.textContent = "🔊 Speaking";
        else if (state === "paused") vs.textContent = "⏸ Paused";
        else vs.textContent = "";
      }
    },
    _detectClientLang(text, fallbackLang) {
      const s = text || "";
      const kn = (s.match(/[\u0C80-\u0CFF]/g) || []).length;
      const hi = (s.match(/[\u0900-\u097F]/g) || []).length;
      const lat = (s.match(/[A-Za-z]/g) || []).length;
      const tot = kn + hi + lat || 1;
      if ((kn / tot >= 0.25 || (kn >= 15 && lat < 40)) && kn >= hi) return "kn";
      if ((hi / tot >= 0.25 || (hi >= 15 && lat < 40)) && hi > kn) return "hi";
      return fallbackLang || "en";
    },
    _splitChunks(text, maxLen = 360) {
      const out = [];
      const sentences = String(text || "").trim().split(/(?<=[.!?।\n])\s+/);
      let cur = "";
      for (let s of sentences) {
        s = s.trim();
        if (!s) continue;
        while (s.length > maxLen) {
          let cut = s.lastIndexOf(",", maxLen);
          if (cut < maxLen * 0.4) cut = s.lastIndexOf(" ", maxLen);
          if (cut <= 0) cut = maxLen;
          out.push(s.slice(0, cut).trim());
          s = s.slice(cut).replace(/^,\s*/, "").trim();
        }
        if (cur && (cur.length + s.length + 1 > maxLen)) {
          out.push(cur);
          cur = s;
        } else {
          cur = cur ? cur + " " + s : s;
        }
      }
      if (cur) out.push(cur);
      return out.length ? out : [String(text || "").trim()].filter(Boolean);
    },
    async speak(text, lang, el, onend) {
      this.stop();
      const myId = this._playId;
      this.el = el; this.onend = onend; this._ui("loading");
      const effectiveLang = this._detectClientLang(text, lang || "auto");
      const voice = $("#opt-voice").value;
      const chunks = this._splitChunks(text, 360);
      if (!chunks.length) { this._ui("idle"); return; }

      const fetchOne = async (txt, addDisc) => {
        for (let attempt = 0; attempt < 2; attempt++) {
          try {
            return await api("/api/tts", {
              method: "POST", body: { text: txt, lang: effectiveLang, voice, add_disclaimer: addDisc }
            });
          } catch {
            if (attempt === 0) await new Promise(res => setTimeout(res, 250));
          }
        }
        const bLang = { en: "en-IN", hi: "hi-IN", kn: "kn-IN", hinglish: "hi-IN", kanglish: "kn-IN" }[effectiveLang] || "en-IN";
        return { backend: "browser", chunks: [txt], chunk_langs: [bLang], browser_lang: bLang };
      };

      // Stream chunks one-by-one sequentially with 1-chunk lookahead so Render never gets overloaded
      this._tailPending = chunks.length > 1;
      const r0 = await fetchOne(chunks[0], chunks.length === 1);
      if (myId !== this._playId) return;

      if (!(r0.audio_base64 && r0.audio_base64.length)) {
        // Server TTS unavailable for chunk 0: speak ALL chunks via browser speechSynthesis immediately
        this._tailPending = false;
        const bLang = r0.browser_lang || ({ en: "en-IN", hi: "hi-IN", kn: "kn-IN", hinglish: "hi-IN", kanglish: "kn-IN" }[effectiveLang] || "en-IN");
        await this._browser(chunks, bLang, chunks.map(c => {
          if (/[\u0C80-\u0CFF]{4,}/.test(c)) return "kn-IN";
          if (/[\u0900-\u097F]{4,}/.test(c)) return "hi-IN";
          return bLang;
        }), myId);
        return;
      }

      this.queue.push(...r0.audio_base64);
      this._next(myId);
      if (chunks.length === 1) {
        this._tailPending = false;
        return;
      }

      // Sequentially fetch remaining chunks in background while earlier chunks play
      (async () => {
        for (let i = 1; i < chunks.length; i++) {
          if (myId !== this._playId) return;
          const ri = await fetchOne(chunks[i], i === chunks.length - 1);
          if (myId !== this._playId) return;
          if (ri.audio_base64 && ri.audio_base64.length) {
            this.queue.push(...ri.audio_base64);
            if (!this.audio && this.queue.length) this._next(myId);
          } else {
            // Wait for current MP3 queue to finish, then speak remaining chunks via browser TTS
            const remaining = chunks.slice(i);
            const waitAudioEnd = () => {
              if (myId !== this._playId) return;
              if (this.audio || this.queue.length) { setTimeout(waitAudioEnd, 150); return; }
              this._tailPending = false;
              const bLang = ri.browser_lang || "en-IN";
              this._browser(remaining, bLang, null, myId);
            };
            waitAudioEnd();
            return;
          }
        }
        this._tailPending = false;
        if (!this.audio && !this.queue.length) { this._ui("idle"); this.onend && this.onend(); }
      })();
    },
    playBase64(list, el, onend) {
      this.stop();
      const myId = this._playId;
      this.el = el; this.onend = onend; this.queue = list.slice();
      this._next(myId);
    },
    _next(myId) {
      if (myId !== undefined && myId !== this._playId) return;
      if (!this.queue.length) {
        this.audio = null;
        if (this._tailPending) { this._ui("loading"); return; }
        this._ui("idle"); this.onend && this.onend();
        return;
      }
      this.audio = new Audio("data:audio/mpeg;base64," + this.queue.shift());
      this.audio.playbackRate = this.rate;
      this.audio.onended = () => this._next(myId);
      this.audio.onerror = () => this._next(myId);
      this.audio.play().catch(() => { this.audio = null; this._ui("idle"); });
      this._ui("playing");
    },
    _getVoices() {
      const v = speechSynthesis.getVoices();
      if (v && v.length) return Promise.resolve(v);
      return new Promise(resolve => {
        let done = false;
        const finish = () => { if (!done) { done = true; resolve(speechSynthesis.getVoices()); } };
        speechSynthesis.addEventListener("voiceschanged", finish, { once: true });
        setTimeout(finish, 600);
      });
    },
    _pickVoice(voices, lang) {
      const norm = s => (s || "").replace(/_/g, "-").toLowerCase();
      const target = norm(lang);
      const base = target.split("-")[0];
      return (
        voices.find(x => norm(x.lang) === target) ||
        voices.find(x => norm(x.lang).startsWith(base + "-")) ||
        voices.find(x => norm(x.lang) === base) ||
        null
      );
    },
    _splitForBrowser(text, maxLen = 220) {
      const out = [];
      const sentences = String(text || "").split(/(?<=[.!?।])\s+/);
      let cur = "";
      for (let s of sentences) {
        s = s.trim();
        if (!s) continue;
        while (s.length > maxLen) {
          let cut = s.lastIndexOf(",", maxLen);
          if (cut < maxLen * 0.4) cut = s.lastIndexOf(" ", maxLen);
          if (cut <= 0) cut = maxLen;
          out.push(s.slice(0, cut).trim());
          s = s.slice(cut).replace(/^,\s*/, "").trim();
        }
        if (cur && (cur.length + s.length + 1 > maxLen)) {
          out.push(cur);
          cur = s;
        } else {
          cur = cur ? cur + " " + s : s;
        }
      }
      if (cur) out.push(cur);
      return out;
    },
    async _browser(chunks, defaultLang, chunkLangs, myId) {
      if (!("speechSynthesis" in window)) { this._ui("idle"); return; }
      const voices = await this._getVoices();
      if (myId !== this._playId) return;

      // Build sequential sub-chunks preserving per-chunk language tags
      const items = [];
      chunks.forEach((c, i) => {
        const cLang = (chunkLangs && chunkLangs[i]) || defaultLang || "en-IN";
        this._splitForBrowser(c, 220).forEach(sub => items.push({ text: sub, lang: cLang }));
      });
      if (!items.length) { this._ui("idle"); return; }

      // Never silently fall back to an English voice for Kannada or Hindi
      const primaryBase = (defaultLang || "en-IN").split("-")[0].toLowerCase();
      const primaryVoice = this._pickVoice(voices, defaultLang || "en-IN");
      if (!primaryVoice && (primaryBase === "kn" || primaryBase === "hi")) {
        const label = primaryBase === "kn" ? "Kannada (kn-IN)" : "Hindi (hi-IN)";
        this._ui("idle", `⚠️ No browser ${label} voice installed`);
        return;
      }

      let idx = 0;
      const speakNext = () => {
        if (myId !== this._playId) return;
        if (idx >= items.length) {
          this.utter = null;
          this._ui("idle");
          this.onend && this.onend();
          return;
        }
        const item = items[idx++];
        const base = item.lang.split("-")[0].toLowerCase();
        const v = this._pickVoice(voices, item.lang);
        if (!v && (base === "kn" || base === "hi")) {
          // Skip or warn instead of speaking Kannada/Hindi with English voice
          const label = base === "kn" ? "Kannada (kn-IN)" : "Hindi (hi-IN)";
          this._ui("idle", `⚠️ No browser ${label} voice installed`);
          return;
        }
        const u = new SpeechSynthesisUtterance(item.text);
        u.lang = item.lang;
        u.rate = this.rate;
        if (v) u.voice = v;
        this.utter = u;
        u.onstart = () => { if (myId === this._playId) this._ui("playing"); };
        u.onend = () => speakNext();
        u.onerror = () => speakNext();
        speechSynthesis.speak(u);
      };
      speakNext();
    },
    toggle() {
      if (this.audio) { if (this.audio.paused) { this.audio.play(); this._ui("playing"); } else { this.audio.pause(); this._ui("paused"); } }
      else if ("speechSynthesis" in window) { if (speechSynthesis.paused) { speechSynthesis.resume(); this._ui("playing"); } else { speechSynthesis.pause(); this._ui("paused"); } }
    },
    setRate(r) { this.rate = r; if (this.audio) this.audio.playbackRate = r; }
  };
  function playerControls(getText, lang) {
    const d = document.createElement("div"); d.className = "player"; d.innerHTML =
      `<button class="btn" data-a="read"><svg width="18" height="18" aria-hidden="true"><use href="#i-speaker"/></svg>${t("read")}</button>
       <button class="btn" data-a="replay" title="Replay audio from beginning">🔁 Replay</button>
       <button class="btn pp" data-a="pp">${t("pause")}</button><button class="btn" data-a="stop">${t("stopread")}</button>
       <span class="voice-status" style="font-size:.82rem;color:var(--ink-2);margin-left:4px"></span>
       <label class="field" style="flex-direction:row;align-items:center;gap:6px">${t("speed")}
       <select class="select" data-a="rate" aria-label="${t("speed")}"><option>0.75</option><option selected>1</option><option>1.25</option><option>1.5</option></select></label>`;
    d.addEventListener("click", e => { const a = e.target.closest("[data-a]")?.dataset.a;
      if (a === "read" || a === "replay") Player.speak(getText(), lang, d, onSpokenEnd); if (a === "pp") Player.toggle(); if (a === "stop") Player.stop(); });
    $("[data-a=rate]", d).addEventListener("change", e => Player.setRate(parseFloat(e.target.value)));
    return d;
  }
  function onSpokenEnd() { if ($("#opt-conv").checked && location.hash.startsWith("#/ask")) setTimeout(() => Voice.start("ask"), 500); }

  // ── chat ───────────────────────────────────────────────────────────────────
  const STARTERS = {
    en: ["What is the role of Agni in digestion?", "What are the functions of Pitta dosha?", "What is Ojas?", "What does Ayurveda say about daily routine?"],
    hi: ["पित्त दोष के कार्य क्या हैं?", "अग्नि क्या है?", "ओजस क्या है?", "वात दोष के लक्षण क्या हैं?"],
    kn: ["ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?", "ಆಮ ದೋಷವನ್ನು ನಿವಾರಿಸುವುದು ಹೇಗೆ?", "ಅಗ್ನಿ ಎಂದರೇನು?", "ಓಜಸ್ಸು ಎಂದರೇನು?"],
    hinglish: ["Vata dosha ke lakshan kya hain?", "Pitta badhne se kya hota hai?", "Ashwagandha ke fayde kya hain?", "Agni kamzor ho to kya hota hai?"],
    kanglish: ["Agni mandya andre enu, adara lakshanagalu yavuvu?", "Vata dosha lakshanagalu enu?", "Ashwagandhada upayogagalu enu?", "Pitta hecchagidre yenu madabeku?"],
  };
  let QL = store.get("ayur.ql", "en");
  function renderStarters() {
    $$("#qlangs [data-ql]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.ql === QL)));
    $("#starters").innerHTML = (STARTERS[QL] || STARTERS.en).map(q => `<button type="button">${esc(q)}</button>`).join("");
  }
  $("#qlangs").addEventListener("click", e => { const b = e.target.closest("[data-ql]"); if (!b) return; QL = b.dataset.ql; store.set("ayur.ql", QL); renderStarters(); });
  $("#starters").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { $("#q").value = b.textContent; ask(); } });
  function enableAutoExpand(el, minHeight = 120) {
    if (!el) return;
    const adjust = () => {
      el.style.height = "auto";
      el.style.height = Math.max(minHeight, el.scrollHeight) + "px";
    };
    el.addEventListener("input", adjust);
    setTimeout(adjust, 60);
  }

  const q = $("#q");
  if (q) {
    enableAutoExpand(q, 120);
    q.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        ask();
      }
    });
  }
  $("#composer").addEventListener("submit", e => { e.preventDefault(); ask(); });

  const symQ = $("#sym-q");
  if (symQ) {
    enableAutoExpand(symQ, 120);
    symQ.addEventListener("keydown", e => {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        $("#sym-submit").click();
      }
    });
  }

  function addQuestion(text) { const d = document.createElement("div"); d.className = "q"; d.textContent = text; $("#thread").append(d); $("#starters-wrap").hidden = true; }
  function addSkeleton() { const d = document.createElement("div"); d.className = "a"; d.setAttribute("aria-busy", "true");
    d.innerHTML = `<span class="sr">${t("loading")}</span>
      <div style="display:flex;align-items:center;gap:8px;font-size:0.875rem;color:var(--ink-muted,#6b7280);margin-bottom:10px;">
        <span style="display:inline-block;width:12px;height:12px;border:2px solid #10b981;border-top-color:transparent;border-radius:50%;animation:spin 1s linear infinite;"></span>
        <span>🌿 Consulting classical Ayurvedic texts & Gemini foundational knowledge...</span>
      </div>
      <div class="skeleton" style="width:60%"></div><div class="skeleton"></div><div class="skeleton" style="width:80%"></div>`;
    $("#thread").append(d); d.scrollIntoView({ block: "nearest", behavior: "smooth" }); return d; }

  async function ask(textOverride) {
    if ($("#send").disabled && !textOverride) return;
    const text = (textOverride || q.value).trim(); if (!text) { q.focus(); return; }
    q.value = ""; q.style.height = "120px"; addQuestion(text); const sk = addSkeleton(); $("#send").disabled = true;
    try {
      const r = await api("/api/ask", { method: "POST", key: "ask", body: { query: text, mode: $("#opt-mode").value,
        target_lang: $("#opt-lang").value, web_fallback: $("#opt-web").checked, generator: $("#opt-gen").value, voice: $("#opt-voice").value } });
      renderAnswer(r, sk);
    } catch (e) {
      if (e.name !== "AbortError") {
        const safeText = esc(text).replace(/'/g, "\\'");
        sk.outerHTML = `<div class="err" role="alert" style="display:flex;flex-direction:column;gap:8px;">
          <div>⚠️ <strong>Response Issue:</strong> ${esc(e.message)}</div>
          <div><button type="button" class="btn btn-sm" onclick="window.ask('${safeText}')" style="cursor:pointer;padding:6px 12px;font-size:0.85rem;border-radius:4px;border:1px solid currentColor;">🔄 Retry Question</button></div>
        </div>`;
      }
    }
    finally { $("#send").disabled = false; }
  }
  window.ask = ask;

  const LANG_NAME = { en: "English", hi: "हिन्दी", kn: "ಕನ್ನಡ", hinglish: "Hinglish", kanglish: "Kanglish", unsupported: "Unsupported" };
  function displayAnswer(ans) {
    let clean = (ans || "")
      .replace(/\[[A-Za-z0-9_.\- :]+(?:CHUNK|EVID|WHO|NAMASTE|IMPPAT|CLASSIC|CI\.ASSIC|WEB|DOC)[^\]]*\]/gi, "")
      .replace(/\[[A-Z][A-Z0-9_.\-]{3,}[A-Z0-9]\]/g, "")
      .replace(/\n\*\*Sources:\*\*[\s\S]*?(?=\n\n\*\*|$)/, "")
      .replace(/\n\n\*\*Ayurvedic terms:\*\*[^\n]*/, "");
    return clean.replace(/[ \t]{2,}/g, " ").trim();
  }

  function renderAnswer(r, slot) {
    const card = document.createElement("article"); const lang = r.response_language || r.target_language || "en";
    card.className = "a" + (r.is_emergency ? " emergency" : r.abstained ? " abstain" : ""); card.lang = lang;
    const terms = (r.detected_terms || []).filter((x, i, a) => a.findIndex(y => y.canonical_term === x.canonical_term) === i);
    const cits = r.citations || [];
    const title = r.is_emergency ? `<h3>${t("emergency_title")}</h3>` : r.abstained ? `<h3>${t("abstain_title")}</h3>` : "";
    const routeCategory = r.route_category || "AYURVEDA_DOMAIN";
    let routeBadge = "";
    if (routeCategory === "GENERAL_KNOWLEDGE") {
      routeBadge = `<span class="badge" style="background:#023e8a;color:#fff">🌐 General AI Knowledge</span>`;
    } else if (routeCategory === "MIXED_DOMAIN") {
      routeBadge = `<span class="badge" style="background:#4a4e69;color:#fff">⚖️ Hybrid (Ayurveda + General AI)</span>`;
    } else if (routeCategory === "CURRENT_INFORMATION") {
      routeBadge = `<span class="badge" style="background:#0077b6;color:#fff">🕒 Current Information</span>`;
    } else if (routeCategory === "UNSAFE_OR_MEDICALLY_SENSITIVE") {
      routeBadge = `<span class="badge" style="background:#d90429;color:#fff">⚠️ Safety Guardrail</span>`;
    } else if (routeCategory === "UNCLEAR_QUERY") {
      routeBadge = `<span class="badge" style="background:#6c757d;color:#fff">❓ Clarification Needed</span>`;
    } else {
      routeBadge = `<span class="badge" style="background:#2d6a4f;color:#fff">🌿 AyurMitra Knowledge Base</span>`;
    }
    const sourceBadge = r.source_label ? `<span class="badge" style="background:var(--card-bg, #f4f1de);color:var(--ink-2);border:1px solid var(--line);font-size:.78rem">${esc(r.source_label)}</span>` : "";

    card.innerHTML = `
      <div class="meta" style="flex-wrap:wrap;gap:6px">
        <span class="badge">${LANG_NAME[lang] || lang}</span>
        ${routeBadge}
        <span class="badge">${esc(r.system_mode)}</span>
        ${sourceBadge}
        ${r.machine_translated ? `<span class="badge mt">${t("mt_badge")}</span>` : ""}
        ${r.answer_grounding === "evidence_sentence" && lang !== "en" && !r.machine_translated ? `<span class="badge">${t("english_src")}</span>` : ""}
        <span>${Math.round(r.latency_ms || 0)} ms</span>
      </div>
      ${title}<div class="answer-body">${md(displayAnswer(r.answer || ""))}</div>
      ${terms.length ? `<div class="terms">${terms.map(x => `<a class="seal" href="#/graph?center=${encodeURIComponent(x.canonical_term)}">${esc(x.canonical_term)}${x.matched_text && x.matched_text !== x.canonical_term ? ` <span class="alt">${esc(x.matched_text)}</span>` : ""}</a>`).join("")}</div>` : ""}
      ${!r.abstained || cits.length ? `<details class="fold"><summary>${t("sources")} (${cits.length})</summary>${renderSources(r)}</details>` : ""}
      <details class="fold"><summary>${t("how")}</summary>${renderTrace(r)}</details>
      <div class="actions"></div>`;
    const lead = $(".answer-body p", card); if (lead && !r.abstained) lead.classList.add("lead");
    const actions = $(".actions", card);
    actions.append(playerControls(() => {
      const bodyEl = $(".answer-body", card);
      return (bodyEl && bodyEl.innerText ? bodyEl.innerText.trim() : "") || displayAnswer(r.answer || "");
    }, lang));
    const mk = (label, fn) => { const b = document.createElement("button"); b.className = "btn ghost"; b.textContent = label; b.onclick = () => fn(b); actions.append(b); };
    mk(t("copy"), async b => { try { await navigator.clipboard.writeText(r.answer); b.textContent = t("copied"); } catch { /* clipboard blocked */ } });
    mk(t("share"), async () => { const txt = `${r.raw_query}\n\n${r.answer}`; if (navigator.share) { try { await navigator.share({ text: txt }); } catch { /* cancelled */ } } else { try { await navigator.clipboard.writeText(txt); } catch { } } });
    ["up", "down"].forEach(rt => mk(rt === "up" ? "👍 " + t("helpful") : "👎 " + t("not_helpful"), async b => {
      try { await api("/api/feedback", { method: "POST", body: { rating: rt, mode: r.system_mode } }); b.textContent = t("thanks"); } catch { } }));
    slot.replaceWith(card); card.scrollIntoView({ block: "nearest", behavior: "smooth" });
    const ctl = $(".player", card);
    if (r.tts && r.tts.audio_base64 && r.tts.audio_base64.length) Player.playBase64(r.tts.audio_base64, ctl, onSpokenEnd);
    else if (r.is_emergency || $("#opt-autoplay").checked || r._fromVoice) Player.speak(displayAnswer(r.answer || ""), lang, ctl, onSpokenEnd);
  }
  function renderSources(r) {
    const cits = r.citations || [], passages = r.retrieved_passages || [];
    const local = cits.filter(c => !c.is_web), web = cits.filter(c => c.is_web);
    let h = local.map(c => `<div class="src"><span class="badge">${esc(c.source_id)}</span><span>${esc(c.title || "")} — ${esc(c.locator || "")}</span></div>`).join("");
    if (web.length) h += web.map(c => `<div class="src ext"><span class="badge">${esc(c.source_id || "External API")}</span><span><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.title)}</a> (${esc(c.publisher || "")} ${esc(c.locator || c.year || "")})</span></div>`).join("");
    if (passages.length) h += `<details><summary class="muted" style="min-height:40px;display:flex;align-items:center;cursor:pointer">Retrieved passages (${passages.length})</summary>` +
      passages.map(p => `<blockquote style="margin:8px 0;padding-left:12px;border-left:3px solid var(--line)"><small><code class="mono">${esc(p.chunk_id)}</code> ${esc(p.source_id)} · ${esc(p.locator || "")}</small><br>${esc((p.text || "").slice(0, 420))}…</blockquote>`).join("") + "</details>";
    return h || `<p class="muted">No sources — the system did not answer.</p>`;
  }
  function renderTrace(r) {
    const b = r.backends || {}; const tm = r.translation_meta || {}; const ev = r.evidence_check || {};
    const sttBackend = r.transcript?.backend || (Voice.rec ? "browser Web Speech API" : (r._fromVoice ? "audio upload" : "none / text input"));
    const ttsBackend = (r.tts && r.tts.backend) ? r.tts.backend : "browser speechSynthesis";
    const rows = [
      ["Processing Route", `${esc(r.route_category || "AYURVEDA_DOMAIN")} · <strong>${esc(r.route_label || "AyurMitra Knowledge Base")}</strong>`],
      ["Knowledge Source", esc(r.source_label || "AyurMitra Knowledge Base (WHO / NAMASTE / IMPPAT)")],
      ["Generation Model", `<strong>${esc(r.generator_used || b.generator || "evidence_grounded_engine")}</strong>${r.generator_note ? ` <small>(${esc(r.generator_note)})</small>` : ""}`],
      ["Retrieved Passages", `${(r.retrieved_passages || []).length} relevant passage(s) Grounded`],
      ["Language Mode", `${esc(r.language_mode || r.target_language || "en")} (${LANG_NAME[r.language_mode || r.target_language] || r.target_language})`],
      ["Detected language", `${r.detected_language}${r.is_code_mixed ? ` (code-mixed: ${esc(r.code_mix_type)})` : ""}`],
      ["Segments", (r.segments || []).map(s => `${esc(s.text || s.segment || "")} <small>[${esc(s.lang || s.script || "")}]</small>`).join(" · ") || "—"],
      ["Protected terms", (r.detected_terms || []).map(x => `${esc(x.matched_text)} → ${esc(x.canonical_term)}`).join(", ") || "none"],
      ["Translation", `${esc(tm.method || "—")}${tm.translated_text ? `: <em>${esc(tm.translated_text)}</em>` : ""}${tm.warning ? `<br><small>${esc(tm.warning)}</small>` : ""}`],
      ["Canonical query", esc(r.canonical_query || "—")],
      ["Graph expansion", esc((r.graph_expansion_terms || []).join(", ") || "—")],
      ["Active Backends", `MT: <strong>${esc(b.translator || "rules fallback")}</strong> · Dense: <strong>${esc(b.dense_model || b.dense || "TF-IDF fallback")}</strong> · Generator: <strong>${esc(r.generator_used || b.generator || "extractive")}</strong> · Graph: <strong>${esc(b.kg_version || "v2")}</strong> · STT: <strong>${esc(sttBackend)}</strong> · TTS: <strong>${esc(ttsBackend)}</strong>`],
      ["Evidence check", ev.judgeable ? `coverage ${ev.coverage} (${esc((ev.matched || []).join(", "))})` : "—"],
      ["Abstention", r.abstained ? esc(r.abstention_reason) : "no"],
      ["Graph facts", (r.graph_facts || []).map(f => `${esc(f.concept)} — ${esc(f.relation)} — ${esc(f.target)} <small>(${esc(f.locator || "no locator")}; <span class="${f.is_verified ? "badge ok" : "badge unrev"}">${esc((f.verification_status || f.review_status || "").replace(/_/g, " "))}</span>)${f.provisional_notice ? ` <em>[${esc(f.provisional_notice)}]</em>` : ""}</small>`).join("<br>") || "—"],
      ["Latency", `${Math.round(r.latency_ms || 0)} ms`],
    ];
    return `<dl class="trace">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
  }

  // ── voice input ────────────────────────────────────────────────────────────
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const Voice = {
    active: null, target: null, rec: null, media: null, chunks: [], t0: 0, timer: null, ctx: null, silentSince: 0, heard: false,
    selectedVoiceLang() {
      if (this.target === "symptoms" && $("#sym-voice-lang")) return $("#sym-voice-lang").value;
      if (this.target === "herbs" && $("#herb-voice-lang")) return $("#herb-voice-lang").value;
      return ($("#voice-lang") && $("#voice-lang").value) || store.get("ayur.voiceLang", "auto");
    },
    langCode() {
      const v = this.selectedVoiceLang();
      if (v === "en-IN") return "en-IN";
      if (v === "hi-IN") return "hi-IN";
      if (v === "kn-IN") return "kn-IN";
      // Auto: respect active UI / starter language, then browser locale, else en-IN
      if (UI === "hi" || QL === "hi" || QL === "hinglish") return "hi-IN";
      if (UI === "kn" || QL === "kn" || QL === "kanglish") return "kn-IN";
      return navigator.language && navigator.language.startsWith("hi") ? "hi-IN" :
             navigator.language && navigator.language.startsWith("kn") ? "kn-IN" : "en-IN";
    },
    btn() {
      if (this.target === "symptoms") return $("#sym-mic");
      if (this.target === "herbs") return $("#herb-mic");
      return $("#mic");
    },
    input() {
      if (this.target === "symptoms") return $("#sym-q");
      if (this.target === "herbs") return $("#herb-q");
      return $("#q");
    },
    toggle(target) { if (this.active) this.stop(); else this.start(target); },
    async start(target) {
      this.target = target; Player.stop();
      if (!window.isSecureContext) return this.fail(t("mic_insecure"));
      this._ui(true);
      const isAuto = this.selectedVoiceLang() === "auto";
      const serverSttLive = !!(HEALTH && HEALTH.backends && HEALTH.backends.stt && HEALTH.backends.stt.live);
      // Use server-side Whisper for Auto when available; otherwise use browser Web Speech API so voice works on Render
      if (SR && (!isAuto || !serverSttLive) && store.get("ayur.forceServerSTT", false) !== true) return this._webSpeech();
      if (!navigator.mediaDevices || !window.MediaRecorder) {
        if (SR) return this._webSpeech();
        this._ui(false); return this.fail(t("no_mic"));
      }
      try { this.media = await navigator.mediaDevices.getUserMedia({ audio: true }); }
      catch (e) {
        if (SR) return this._webSpeech();
        this._ui(false); return this.fail(e.name === "NotAllowedError" ? t("mic_denied") : t("no_mic"));
      }
      this.chunks = []; this.active = new MediaRecorder(this.media);
      this.active.ondataavailable = e => e.data.size && this.chunks.push(e.data);
      this.active.onstop = () => this._send(); this.active.start(); this._meter();
    },
    _webSpeech() {
      const r = new SR(); this.rec = r; this.active = r; r.lang = this.langCode(); r.interimResults = true; r.maxAlternatives = 1;
      let final = ""; const inp = this.input();
      r.onresult = e => { let interim = ""; for (let i = e.resultIndex; i < e.results.length; i++) { const x = e.results[i]; if (x.isFinal) final += x[0].transcript; else interim += x[0].transcript; } inp.value = (final + interim).trim(); };
      r.onerror = e => { this._ui(false); this.active = null; if (e.error === "not-allowed") this.fail(t("mic_denied"));
        else if (e.error === "network" || e.error === "service-not-allowed") { store.set("ayur.forceServerSTT", true); this.start(this.target); } };
      r.onend = () => {
        this._ui(false); this.active = null;
        if (inp && inp.value.trim()) {
          inp.focus();
          Voice._lastFromVoice = true;
          const msg = this.target === "symptoms" ? "Transcript ready. Review or edit your symptom description, then click Explore Evidence." :
                      this.target === "herbs" ? "Transcript ready. Review or edit your search, then press Enter or click Search." :
                      (t("edit_transcript") || "Transcript ready. You can review or edit your question, then click Ask.");
          note(msg);
        }
      };
      r.start(); this.t0 = Date.now(); this._tick();
    },
    _meter() {
      try {
        this.ctx = new (window.AudioContext || window.webkitAudioContext)(); const src = this.ctx.createMediaStreamSource(this.media);
        const an = this.ctx.createAnalyser(); an.fftSize = 512; src.connect(an); const buf = new Uint8Array(an.fftSize);
        this.t0 = Date.now(); this.silentSince = Date.now(); this.heard = false;
        const loop = () => { if (!this.active || this.rec) return; an.getByteTimeDomainData(buf); let s = 0; for (const v of buf) s += (v - 128) ** 2;
          const lvl = Math.min(1, Math.sqrt(s / buf.length) / 40); $("#rec-level").style.width = (lvl * 100) + "%";
          if (lvl > 0.12) { this.heard = true; this.silentSince = Date.now(); }
          if (this.heard && Date.now() - this.silentSince > 2200) return this.stop();
          requestAnimationFrame(loop); }; loop();
      } catch { /* no AudioContext: no meter */ }
      this._tick();
    },
    _tick() { clearInterval(this.timer); this.timer = setInterval(() => { const s = Math.floor((Date.now() - this.t0) / 1000);
      $("#rec-time").textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`; if (s >= 60) this.stop(); }, 250); },
    stop(cancel) {
      clearInterval(this.timer); const a = this.active; this.active = null; this.cancelled = !!cancel;
      if (this.rec) { try { cancel ? this.rec.abort() : this.rec.stop(); } catch { } this.rec = null; }
      else if (a && a.state !== "inactive") a.stop();
      if (this.media) this.media.getTracks().forEach(tr => tr.stop()); this.media = null;
      if (this.ctx) { this.ctx.close().catch(() => {}); this.ctx = null; } this._ui(false);
    },
    async _send() {
      if (this.cancelled || !this.chunks.length) return;
      const blob = new Blob(this.chunks, { type: this.chunks[0].type || "audio/webm" });
      const fd = new FormData();
      fd.append("audio", blob, "clip." + (blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "m4a" : "webm"));

      const v = this.selectedVoiceLang();
      let hint = "auto";
      if (v === "en-IN") hint = "en";
      else if (v === "hi-IN") hint = "hi";
      else if (v === "kn-IN") hint = "kn";
      fd.append("lang_hint", hint);

      try {
        const r = await api("/api/voice/transcribe", { method: "POST", form: fd });
        if (!r.ok) {
          return this.fail(r.message || "Speech recognition failed. Please try again or type your question.");
        }
        const inp = this.input();
        inp.value = r.text || r.raw_text || "";
        inp.focus();
        inp.dispatchEvent(new Event("input"));
        Voice._lastFromVoice = true;

        const badge = this.target === "symptoms" ? $("#sym-transcript-badge") :
                      this.target === "herbs" ? $("#herb-transcript-badge") :
                      $("#voice-transcript-badge");
        if (badge) {
          badge.style.display = "inline-flex";
          setTimeout(() => { badge.style.display = "none"; }, 8000);
        }

        const msg = this.target === "symptoms" ? "Transcript ready. Review or edit your symptom description, then click Explore Evidence." :
                    this.target === "herbs" ? "Transcript ready. Review or edit your search, then press Enter or click Search." :
                    (t("edit_transcript") || "Transcript ready. You can review or edit your question, then click Ask.");
        note(r.needs_confirmation ? t("low_conf") : msg);
      } catch (e) {
        this.fail(e.message);
      }
    },
    _ui(on) { const b = this.btn(); if (b) { b.classList.toggle("rec", on); b.setAttribute("aria-pressed", String(on)); b.setAttribute("aria-label", on ? t("stop") : t("mic")); }
      $("#rec-bar").hidden = !(on && this.target === "ask"); },
    fail(msg) { note(msg, true); }
  };
  function note(msg, isErr) { const d = document.createElement("div"); d.className = isErr ? "err" : "notice"; d.setAttribute("role", isErr ? "alert" : "status"); d.textContent = msg;
    const host = Voice.target === "symptoms" ? $("#sym-out") : Voice.target === "herbs" ? $("#herb-results") : $("#thread"); (host || $("#main")).prepend(d); setTimeout(() => d.remove(), 9000); }
  $("#mic") && $("#mic").addEventListener("click", () => Voice.toggle("ask"));
  $("#sym-mic") && $("#sym-mic").addEventListener("click", () => Voice.toggle("symptoms"));
  $("#herb-mic") && $("#herb-mic").addEventListener("click", () => Voice.toggle("herbs"));
  $("#rec-cancel") && $("#rec-cancel").addEventListener("click", () => Voice.stop(true));
  document.addEventListener("keydown", e => {
    if (e.altKey && (e.key === "m" || e.key === "M")) {
      e.preventDefault();
      const target = location.hash.startsWith("#/herbs") ? "herbs" : location.hash.startsWith("#/symptoms") ? "symptoms" : "ask";
      Voice.toggle(target);
    }
  });

  // Synchronize Voice Input Language Selectors across Ask, Symptoms, and Herbs
  function syncVoiceLang(val) {
    store.set("ayur.voiceLang", val);
    ["#voice-lang", "#sym-voice-lang", "#herb-voice-lang"].forEach(sel => {
      const el = $(sel);
      if (el && el.value !== val) el.value = val;
    });
  }
  const initVoiceLang = store.get("ayur.voiceLang", "auto");
  syncVoiceLang(initVoiceLang);
  ["#voice-lang", "#sym-voice-lang", "#herb-voice-lang"].forEach(sel => {
    const el = $(sel);
    if (el) el.addEventListener("change", e => syncVoiceLang(e.target.value));
  });

  // Synchronize Quick Response Language Selectors
  if ($("#opt-lang-quick") && $("#opt-lang")) {
    $("#opt-lang-quick").value = $("#opt-lang").value;
    $("#opt-lang-quick").addEventListener("change", e => {
      $("#opt-lang").value = e.target.value;
    });
    $("#opt-lang").addEventListener("change", e => {
      $("#opt-lang-quick").value = e.target.value;
    });
  }

  // ── knowledge graph ────────────────────────────────────────────────────────
  let graph = null, GDATA = null, CENTER = "Tridosha"; const TYPES = Object.keys(KG_TYPE_COLORS);
  let activeTypes = new Set(TYPES.filter(x => x !== "TherapeuticUse"));
  function initGraph(params) {
    graph = new ForceGraph($("#kg-canvas"), { onSelect: id => showNode(id) });
    $("#kg-types").innerHTML += TYPES.map(x => `<label class="check" style="min-height:32px"><input type="checkbox" value="${x}" ${activeTypes.has(x) ? "checked" : ""}><span><i style="background:${KG_TYPE_COLORS[x]}"></i> ${x.replace(/([a-z])([A-Z])/g, "$1 $2")}</span></label>`).join("") +
      `<span><i style="background:transparent;border:1px dashed var(--clay);border-radius:0;height:0;width:18px"></i> needs review</span>`;
    $("#kg-types").addEventListener("change", e => { if (e.target.checked) activeTypes.add(e.target.value); else activeTypes.delete(e.target.value); loadGraph(CENTER); });
    $("#kg-depth").addEventListener("input", e => { $("#kg-depth-v").textContent = e.target.value; });
    $("#kg-depth").addEventListener("change", () => loadGraph(CENTER));
    const zi = $("#kg-zoomin"); if (zi) zi.onclick = () => graph.zoomIn();
    const zo = $("#kg-zoomout"); if (zo) zo.onclick = () => graph.zoomOut();
    $("#kg-fit").onclick = () => graph.fit(); $("#kg-reset").onclick = () => { graph.reset(); graph.fit(); };
    $("#kg-full").onclick = () => { const w = $("#kg-wrap"); document.fullscreenElement ? document.exitFullscreen() : w.requestFullscreen && w.requestFullscreen(); };
    $("#kg-png").onclick = () => download(graph.toPNG(), `ayurmitra-graph-${CENTER}.png`);
    $("#kg-json").onclick = () => download(URL.createObjectURL(new Blob([JSON.stringify(GDATA, null, 1)], { type: "application/json" })), `ayurmitra-graph-${CENTER}.json`);
    $("#kg-listbtn").onclick = () => { const on = $("#kg-list").hidden; $("#kg-list").hidden = !on; $("#kg-wrap").hidden = on; $("#kg-listbtn").setAttribute("aria-pressed", String(on)); $("#kg-listbtn").textContent = on ? t("graph_view") : t("list_view"); };
    $("#kg-path").onclick = findPath;
    setupAutocomplete($("#kg-q"), $("#kg-ac"), id => { location.hash = "#/graph?center=" + encodeURIComponent(id); });
    api("/api/graph/stats").then(s => {
      $("#kg-stats").innerHTML = `<div><b>${s.nodes.toLocaleString()}</b>nodes</div><div><b>${s.edges.toLocaleString()}</b>links</div>
        <div><b>${s.pct_verified}%</b>links with a source row/page locator</div>` +
        Object.entries(s.node_types).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([k, v]) => `<div><b>${v.toLocaleString()}</b>${k}</div>`).join("");
    }).catch(() => {});
    if (window.matchMedia("(max-width: 640px)").matches) $("#kg-listbtn").click();
    if (!params.get("center")) loadGraph(CENTER);
  }
  function download(href, name) { const a = document.createElement("a"); a.href = href; a.download = name; document.body.append(a); a.click(); a.remove(); }
  async function loadGraph(center) {
    CENTER = center;
    try {
      GDATA = await api("/api/graph", { key: "graph", params: { center, depth: $("#kg-depth").value, limit: 150, types: [...activeTypes].join(",") } });
      graph.setData(GDATA.nodes, GDATA.edges, GDATA.center); showNode(GDATA.center); renderList();
    } catch (e) { if (e.name !== "AbortError") $("#kg-panel").innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  }
  function renderList() {
    const byId = Object.fromEntries(GDATA.nodes.map(n => [n.id, n]));
    $("#kg-list").innerHTML = `<table><caption class="sr">Graph neighbourhood as a table</caption><thead><tr><th>From</th><th>Relation</th><th>To</th><th>Source &amp; locator</th></tr></thead><tbody>` +
      GDATA.edges.map(e => `<tr><td><button class="btn ghost" data-n="${esc(e.source)}">${esc(byId[e.source]?.label_en || e.source)}</button></td><td>${esc(e.relation)}</td>
        <td><button class="btn ghost" data-n="${esc(e.target)}">${esc(byId[e.target]?.label_en || e.target)}</button></td><td><small>${esc(e.source_id)} — ${esc(e.locator || "no locator")}</small> ${e.verified ? "" : `<span class="badge unrev">${t("unreviewed")}</span>`}</td></tr>`).join("") +
      `</tbody></table>${GDATA.truncated ? `<p class="muted">Showing the first ${GDATA.nodes.length} nodes.</p>` : ""}`;
    $("#kg-list").onclick = e => { const b = e.target.closest("[data-n]"); if (b) showNode(b.dataset.n); };
  }
  async function showNode(id) {
    graph && graph.select(id);
    try {
      const d = await api("/api/graph/node/" + encodeURIComponent(id), { key: "node" }); const n = d.node;
      const labels = [["IAST", n.label_iast], ["देवनागरी", n.label_sa_deva], ["हिन्दी", n.label_hi], ["ಕನ್ನಡ", n.label_kn || n.label_kn_script_sanskrit]].filter(x => x[1]);
      const edge = (e, dir) => `<li><b>${esc(e.relation)}</b> ${dir} <button class="btn ghost" style="min-height:32px;padding:2px 6px" data-n="${esc(e.other.id)}">${esc(e.other.label_en || e.other.id)}</button>
        <br><small>${esc(e.source_id)} — ${esc(e.locator || "no locator")}${e.row_count ? ` · ${e.row_count} source rows` : ""}</small>
        <span class="badge ${e.verified ? "ok" : "unrev"}">${e.verified ? t("verified") : esc((e.review_status || "").replace(/_/g, " "))}</span>${e.ambiguity_note ? `<br><small>${esc(e.ambiguity_note)}</small>` : ""}</li>`;
      $("#kg-panel").innerHTML = `<p class="muted" style="margin:0">${esc(n.node_type)}</p><h2>${esc(n.label_en || n.id)}</h2>
        ${labels.length ? `<p>${labels.map(([k, v]) => `<span class="seal" style="margin:0 6px 6px 0">${esc(v)} <span class="alt">${k}</span></span>`).join("")}</p>` : ""}
        ${n.label_source ? `<p><small>${esc(n.label_source)}</small></p>` : ""}
        ${n.definition ? `<p>${esc(n.definition)}</p>` : ""}${n.project_definition && !n.definition ? `<p>${esc(n.project_definition)} <span class="badge unrev">project text</span></p>` : ""}
        <p><small>${esc(n.source_id)} — ${esc(n.locator || "")}</small></p>
        <div class="actions"><a class="btn primary" href="#/ask" data-ask="${esc(n.label_en || "")}">${t("ask_about")}</a>
        ${n.node_type === "Plant" ? `<a class="btn" href="#/herbs?herb=${encodeURIComponent(n.id)}">${t("nav_herbs")}</a>` : ""}
        <button class="btn" data-center="${esc(n.id)}">Centre graph here</button></div>
        <h3 style="margin-top:14px">${t("outgoing")} (${d.n_outgoing})</h3><ul class="edge-list">${d.outgoing.slice(0, 40).map(e => edge(e, "→")).join("") || "<li>—</li>"}</ul>
        <h3 style="margin-top:14px">${t("incoming")} (${d.n_incoming})</h3><ul class="edge-list">${d.incoming.slice(0, 40).map(e => edge(e, "←")).join("") || "<li>—</li>"}</ul>`;
      $("#kg-panel").onclick = e => {
        const b = e.target.closest("[data-n]"); if (b) return showNode(b.dataset.n);
        const c = e.target.closest("[data-center]"); if (c) return (location.hash = "#/graph?center=" + encodeURIComponent(c.dataset.center));
        const a = e.target.closest("[data-ask]"); if (a) { e.preventDefault(); location.hash = "#/ask"; setTimeout(() => ask(`What is ${a.dataset.ask}?`), 50); }
      };
    } catch (e) { if (e.name !== "AbortError") $("#kg-panel").innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  }
  async function findPath() {
    const out = $("#kg-path-out"); out.innerHTML = `<div class="skeleton"></div>`;
    try {
      const p = await api("/api/graph/path", { params: { a: $("#kg-from").value, b: $("#kg-to").value } });
      if (!p.found) { out.innerHTML = `<p class="muted">No path found (${esc(p.reason)}).</p>`; return; }
      out.innerHTML = `<ol>${p.edges.map((e, i) => `<li>${esc(p.nodes[i].label_en || p.nodes[i].id)} — <b>${esc(e.relation)}</b> — ${esc(p.nodes[i + 1].label_en || p.nodes[i + 1].id)}<br><small>${esc(e.source_id)}: ${esc(e.locator || "no locator")} (${esc((e.review_status || "").replace(/_/g, " "))})</small></li>`).join("")}</ol>`;
      const missing = p.nodes.some(n => !graph.byId[n.id]);
      if (missing) { GDATA = { center: p.nodes[0].id, nodes: p.nodes.map((n, i) => ({ ...n, hop: i })), edges: p.edges }; graph.setData(GDATA.nodes, GDATA.edges, GDATA.center); renderList(); }
      graph.highlightPath(p.nodes.map(n => n.id));
    } catch (e) { out.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  }
  function setupAutocomplete(input, list, onPick) {
    let items = [], idx = -1;
    const render = () => { list.hidden = !items.length; input.setAttribute("aria-expanded", String(!!items.length));
      list.innerHTML = items.map((x, i) => `<li role="option" id="ac-${i}" aria-selected="${i === idx}" data-id="${esc(x.id)}"><span>${esc(x.label_en || x.id)}${x.label_hi ? ` · ${esc(x.label_hi)}` : ""}${x.label_kn ? ` · ${esc(x.label_kn)}` : ""}</span><small>${esc(x.node_type)}</small></li>`).join("");
      input.setAttribute("aria-activedescendant", idx >= 0 ? "ac-" + idx : ""); };
    const run = debounce(async () => { const v = input.value.trim(); if (!v) { items = []; return render(); }
      try { items = (await api("/api/graph/search", { key: "ac", params: { q: v, limit: 10 } })).results; idx = -1; render(); } catch { } }, 200);
    input.addEventListener("input", run);
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { idx = Math.min(items.length - 1, idx + 1); render(); e.preventDefault(); }
      else if (e.key === "ArrowUp") { idx = Math.max(0, idx - 1); render(); e.preventDefault(); }
      else if (e.key === "Enter") { const x = items[idx >= 0 ? idx : 0]; if (x) { onPick(x.id); items = []; render(); } e.preventDefault(); }
      else if (e.key === "Escape") { items = []; render(); }
    });
    list.addEventListener("click", e => { const li = e.target.closest("li"); if (li) { onPick(li.dataset.id); items = []; render(); } });
    document.addEventListener("click", e => { if (!list.contains(e.target) && e.target !== input) { items = []; render(); } });
  }

  // ── symptoms ───────────────────────────────────────────────────────────────
  const SYM_STARTERS = {
    en: [
      "I have a headache.",
      "I feel tired after eating.",
      "I have dry skin and stiff joints in cold weather.",
      "I feel bloated after meals.",
      "I have difficulty sleeping at night."
    ],
    hi: [
      "मुझे सिरदर्द है।",
      "मुझे भोजन के बाद भारीपन महसूस होता है।",
      "सर्दियों में रूखी त्वचा और जोड़ों में अकड़न।",
      "मुझे पेट फूलने और गैस की समस्या है।",
      "मुझे रात में नींद नहीं आती।"
    ],
    kn: [
      "ನನಗೆ ತಲೆನೋವು ಇದೆ.",
      "ಊಟದ ನಂತರ ಹೊಟ್ಟೆ ಭಾರವಾಗುತ್ತದೆ.",
      "ಚಳಿಗಾಲದಲ್ಲಿ ಒಣ ಚರ್ಮ ಮತ್ತು ಕೀಲು ನೋವು.",
      "ಊಟದ ನಂತರ ಹೊಟ್ಟೆ ಉಬ್ಬರ ಮತ್ತು ಆಲಸ್ಯ.",
      "ನನಗೆ ರಾತ್ರಿ ಸರಿಯಾಗಿ ನಿದ್ರೆ ಬರುತ್ತಿಲ್ಲ."
    ],
    hinglish: [
      "Mujhe khana khane ke baad heaviness hoti hai.",
      "Sar dard aur thakan rehti hai.",
      "Skin dry ho rahi hai aur digestion slow hai."
    ],
    kanglish: [
      "Oota aadmele hotte heavy aagutte.",
      "Tale novu ide mathu niddhe baralla."
    ]
  };
  function renderSymStarters() {
    const el = $("#sym-starters"); if (!el) return;
    const list = SYM_STARTERS[UI] || SYM_STARTERS.en;
    el.innerHTML = list.map(s => `<button type="button" data-sym="${esc(s)}">${esc(s)}</button>`).join("");
  }
  const ssw = $("#sym-starters");
  if (ssw) ssw.addEventListener("click", e => {
    const b = e.target.closest("[data-sym]");
    if (b) { $("#sym-q").value = b.dataset.sym; $("#sym-form").dispatchEvent(new Event("submit")); }
  });

  // Local session history for symptom exploration
  const SYM_HIST_KEY = "ayur_sym_history";
  function loadSymHistory() {
    try { return JSON.parse(localStorage.getItem(SYM_HIST_KEY)) || []; } catch { return []; }
  }
  function saveSymHistory(entry) {
    let hist = loadSymHistory();
    hist = [entry, ...hist.filter(x => x.text !== entry.text)].slice(0, 15);
    try { localStorage.setItem(SYM_HIST_KEY, JSON.stringify(hist)); } catch {}
    renderSymHistory();
  }
  function renderSymHistory() {
    const list = $("#sym-history-list"); if (!list) return;
    const hist = loadSymHistory();
    if (!hist.length) {
      list.innerHTML = `<p class="muted" style="margin:4px 0">No prior queries in this session.</p>`;
      return;
    }
    list.innerHTML = `<ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px">` +
      hist.map(h => `
        <li style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--surface);border:1px solid var(--line);border-radius:8px;gap:8px">
          <div>
            <strong>${esc(h.text)}</strong>
            <div style="font-size:.78rem;color:var(--ink-3);margin-top:2px">
              <span>${esc(h.time)}</span> · <span>Lang: ${esc(h.lang || "auto")}</span>
              ${h.topConcept ? ` · <span class="badge">${esc(h.topConcept)}</span>` : ""}
            </div>
          </div>
          <button type="button" class="btn ghost" data-sym-rerun="${esc(h.text)}" style="padding:3px 10px;font-size:.8rem">Run Again</button>
        </li>
      `).join("") + `</ul>`;
  }

  const clrBtn = $("#sym-clear-history");
  if (clrBtn) {
    clrBtn.addEventListener("click", () => {
      localStorage.removeItem(SYM_HIST_KEY);
      renderSymHistory();
    });
  }
  const histList = $("#sym-history-list");
  if (histList) {
    histList.addEventListener("click", e => {
      const b = e.target.closest("[data-sym-rerun]");
      if (b) {
        $("#sym-q").value = b.dataset.symRerun;
        $("#sym-form").dispatchEvent(new Event("submit"));
      }
    });
  }
  renderSymHistory();

  function renderSymptomAnalysis(r) {
    const u = r.understood || {};
    const concepts = r.concepts || r.mappings || [];
    const evidence = r.evidence || [];
    const graphConn = r.graph_connections || [];
    const limits = r.limitations || {};

    // SECTION 1: What AyurMitra Understood
    const extractedPills = (u.extracted_symptoms || []).map(s => `<span class="pill">${esc(s)}</span>`).join(" ");
    const recognizedPills = (u.recognized_terms || []).map(t => `<span class="pill" style="border-color:var(--turmeric)">${esc(t)}</span>`).join(" ");
    const s1 = `
      <section class="sym-section panel">
        <h3 style="display:flex;align-items:center;gap:8px;margin-top:0">
          <span class="score-badge">1</span> What AyurMitra Understood
        </h3>
        <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:12px;margin-top:10px">
          <div><small class="muted">Original Query</small><div style="font-weight:600">${esc(u.original_query || r.raw_query || "—")}</div></div>
          <div><small class="muted">Language / Script</small><div><span class="badge">${esc(u.detected_language || r.detected_language || "en")}</span> <small>${esc(u.script || "")}</small></div></div>
          ${u.normalized_description ? `<div><small class="muted">Normalized Description</small><div style="font-style:italic">"${esc(u.normalized_description)}"</div></div>` : ""}
        </div>
        <div style="margin-top:12px">
          <small class="muted">Extracted Sensations / Phrases:</small>
          <div class="sym-pills" style="margin-top:4px">${extractedPills || '<span class="muted">None isolated</span>'}</div>
        </div>
        ${recognizedPills ? `
        <div style="margin-top:10px">
          <small class="muted">Recognized Classical Ayurvedic Terms:</small>
          <div class="sym-pills" style="margin-top:4px">${recognizedPills}</div>
        </div>` : ""}
      </section>`;

    // SECTION 2: Related Traditional Concepts
    const conceptsCards = concepts.map(c => {
      const dosha = c.associated_dosha || c.dosha || "Tridosha";
      const scorePct = Math.round((c.relevance_score || 0.85) * 100);
      const isVerified = (c.review_status === "grounded_by_code_text" || c.locator_review_status === "grounded_by_code_text");
      const statusBadge = isVerified
        ? `<span class="badge ok" style="font-size:.72rem">Source Verified</span>`
        : `<span class="badge unrev" style="font-size:.72rem">Needs Review</span>`;
      return `
        <div class="panel" style="background:var(--surface);border:1px solid var(--line);margin-bottom:12px;border-left:4px solid var(--turmeric)">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
            <div>
              <h4 style="margin:0 0 4px 0;font-size:1.1rem">
                ${esc(c.concept_name || c.symptom_phrase)}
                ${c.classical_term ? `<small class="muted" style="font-weight:normal;margin-left:6px">(${esc(c.classical_term)})</small>` : ""}
              </h4>
              <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                <span>Dosha Tendency:</span>
                <a class="seal" href="#/graph?center=${encodeURIComponent(dosha)}" title="Inspect in Knowledge Graph">${esc(dosha)}</a>
                ${statusBadge}
              </div>
            </div>
            <div style="text-align:right">
              <span class="score-badge" title="Classical Textual Heuristic Match (Not a clinical probability)">${scorePct}% textual alignment</span>
              <small class="muted" style="display:block;font-size:.72rem;margin-top:2px">Textual match score · Not a clinical diagnosis</small>
            </div>
          </div>
          <p style="margin:10px 0 6px 0;line-height:1.5">${esc(c.educational_note || "")}</p>
          <div style="font-size:.82rem;color:var(--ink-3);display:flex;gap:12px;flex-wrap:wrap;border-top:1px dashed var(--line);padding-top:6px;margin-top:6px">
            <span><strong>Authority:</strong> ${esc(c.source_id || "WHO / NAMASTE")}</span>
            <span><strong>Locator:</strong> ${esc(c.locator || "Classical Ayurvedic Benchmarks")}</span>
          </div>
        </div>`;
    }).join("");
    const s2 = `
      <section class="sym-section panel">
        <h3 style="display:flex;align-items:center;gap:8px;margin-top:0">
          <span class="score-badge">2</span> Related Traditional Concepts &amp; Dosha Tendencies (Non-Diagnostic)
        </h3>
        <p class="muted" style="font-size:.88rem;margin-bottom:14px">
          Classical Ayurveda classifies bodily sensations according to dosha balance (Vata, Pitta, Kapha) and digestive metabolic state (Agni/Ama). These correlations represent classical pedagogical theory, not medical diagnoses.
        </p>
        ${conceptsCards || '<p class="muted">No direct classical concepts matched.</p>'}
      </section>`;

    // SECTION 3: Retrieved Source Evidence
    const evidenceCards = evidence.map((ev, idx) => {
      const score = typeof ev.relevance_score === "number" ? ev.relevance_score.toFixed(3) : "—";
      return `
        <details class="evidence-card" ${idx < 2 ? "open" : ""}>
          <summary>
            <div style="display:flex;align-items:center;gap:8px;flex:1;min-width:0">
              <span class="badge" style="background:var(--sage);color:#fff">Rank #${ev.rank || (idx + 1)}</span>
              <strong style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${esc(ev.title || ev.source_id)}</strong>
              <small class="muted" style="white-space:nowrap">${esc(ev.locator || "")}</small>
            </div>
            <span class="score-badge" style="margin-left:auto">RRF: ${score}</span>
          </summary>
          <div class="evidence-card-body">
            <div style="margin-bottom:6px;font-size:.78rem;color:var(--ink-3)">
              Source Chunk: <code class="mono">${esc(ev.chunk_id)}</code> · Authority: <strong>${esc(ev.source_id)}</strong>
            </div>
            <p style="margin:0;line-height:1.55;font-size:.9rem">${esc(ev.snippet || ev.text || "")}</p>
          </div>
        </details>`;
    }).join("");
    const s3 = `
      <section class="sym-section panel">
        <h3 style="display:flex;align-items:center;gap:8px;margin-top:0">
          <span class="score-badge">3</span> Retrieved Source Evidence (WHO &amp; Classical Literature)
        </h3>
        <p class="muted" style="font-size:.88rem;margin-bottom:12px">
          Authoritative text passages retrieved via hybrid dense-sparse RRF ranking from peer-reviewed training benchmarks and classical treatises.
        </p>
        ${evidenceCards || '<p class="muted">No related corpus passages retrieved for this query.</p>'}
      </section>`;

    // SECTION 4: Knowledge Graph Connections
    const graphRows = graphConn.map(gc => {
      const revClass = gc.review_status === "grounded_by_code_text" ? "ok" : "unrev";
      const revLabel = (gc.review_status || "unreviewed").replace(/_/g, " ");
      return `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--surface);border:1px solid var(--line);border-radius:8px;gap:10px;flex-wrap:wrap">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
            <strong>${esc(gc.source_concept)}</strong>
            <span class="mono" style="font-size:.8rem;color:var(--clay)">—[${esc(gc.relationship)}]→</span>
            <strong>${esc(gc.target_concept)}</strong>
            <span class="badge ${revClass}" style="font-size:.72rem">${esc(revLabel)}</span>
          </div>
          <div>
            <a href="#/graph?center=${encodeURIComponent(gc.target_node_id || gc.target_concept)}" class="btn ghost" style="padding:2px 10px;font-size:.8rem">Explore in Graph →</a>
          </div>
        </div>`;
    }).join("");
    const s4 = `
      <section class="sym-section panel">
        <h3 style="display:flex;align-items:center;gap:8px;margin-top:0">
          <span class="score-badge">4</span> Knowledge Graph Connections
        </h3>
        <p class="muted" style="font-size:.88rem;margin-bottom:12px">
          Ontological relationships traced within AyurMitra's verified Knowledge Graph v2 (9,530 nodes, 72,341 edges).
        </p>
        <div style="display:flex;flex-direction:column;gap:8px">
          ${graphRows || '<p class="muted">No direct graph edges connected to detected concepts.</p>'}
        </div>
      </section>`;

    // SECTION 5: Evidence Limitations & Boundaries
    const s5 = `
      <section class="sym-section panel" style="background:var(--sand-wash);border:1px solid var(--clay)">
        <h3 style="display:flex;align-items:center;gap:8px;margin-top:0;color:var(--clay)">
          <span class="score-badge" style="background:var(--clay)">5</span> Evidence Limitations &amp; Clinical Boundaries
        </h3>
        <p style="margin:6px 0;line-height:1.55;font-size:.92rem">
          ${esc(r.disclaimer || limits.disclaimer || "AyurMitra is an educational exploration tool, not a clinical diagnostic system.")}
        </p>
        <ul style="margin:8px 0 0 18px;padding:0;font-size:.88rem;line-height:1.5">
          <li><strong>No Medical Diagnosis:</strong> Concepts presented reflect classical Ayurvedic textual taxonomy, not biomedical pathology or laboratory diagnosis.</li>
          <li><strong>No Prescriptions:</strong> AyurMitra does not recommend personalized drug dosages, commercial products, or clinical interventions.</li>
          <li><strong>Physician Consultation:</strong> Consult a qualified Ayurvedic physician (BAMS / MD) or biomedical practitioner for health evaluation.</li>
        </ul>
      </section>`;

    // SECTION 6: Personalized Herbal & Lifestyle Exploration
    const primaryDosha = (concepts[0] && (concepts[0].associated_dosha || concepts[0].dosha)) || (r.mappings && r.mappings[0] && r.mappings[0].associated_dosha) || "Vata";
    const symptomQuery = u.original_text || u.normalized_description || r.raw_query || ($("#sym-q") ? $("#sym-q").value : "") || "symptoms";
    const sHerbsCTA = `
      <section class="sym-section panel" style="background:var(--sage-soft);border:1px solid var(--sage-border);margin-top:16px;border-radius:8px">
        <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px">
          <div>
            <h3 style="margin:0 0 4px 0;font-size:1.05rem;color:var(--sage-dark)">🌿 Personalized Herbal &amp; Lifestyle Recommendations</h3>
            <p style="margin:0;font-size:.88rem;color:var(--ink-2)">
              Explore classical herbs (botanical names, IMPPAT records, API single-herb formulations) and daily routine (Dinacharya / Ahara) historically correlated with <strong>${esc(primaryDosha)}</strong> tendencies and these sensations.
            </p>
          </div>
          <div style="display:flex;gap:10px;flex-wrap:wrap">
            <a href="#/herbs?q=${encodeURIComponent(symptomQuery)}&context=${encodeURIComponent(symptomQuery)}&dosha=${encodeURIComponent(primaryDosha)}" class="btn primary" style="text-decoration:none;display:inline-flex;align-items:center;gap:6px">
              <span>🌿 Explore Related Herbs</span> →
            </a>
            <a href="#/herbs?tab=lifestyle&q=${encodeURIComponent(symptomQuery)}&context=${encodeURIComponent(symptomQuery)}" class="btn" style="text-decoration:none;display:inline-flex;align-items:center;gap:6px">
              <span>☀️ Explore Lifestyle Guidance</span> →
            </a>
          </div>
        </div>
      </section>`;

    return `
      <div class="symptom-explorer">
        ${r.summary ? `
        <div class="panel" style="border-left:4px solid var(--sage);margin-bottom:14px">
          <p class="lead" style="margin:0 0 8px 0;font-size:1.08rem">${esc(r.summary)}</p>
          <div class="sym-actions" style="margin-top:10px"></div>
        </div>` : ""}
        ${s1}
        ${s2}
        ${s3}
        ${s4}
        ${sHerbsCTA}
        ${s5}
      </div>`;
  }

  $("#sym-form").addEventListener("submit", async e => {
    e.preventDefault();
    const text = $("#sym-q").value.trim();
    if (!text) return;
    const out = $("#sym-out");
    out.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>`;
    const target_lang = ($("#sym-lang") && $("#sym-lang").value !== "auto") ? $("#sym-lang").value : $("#opt-lang").value;
    try {
      const r = await api("/api/symptoms", { method: "POST", key: "sym", body: { text, target_lang } });

      // Save query to session history
      const topConcept = (r.concepts && r.concepts[0]) ? r.concepts[0].concept_name : (r.mappings && r.mappings[0] ? r.mappings[0].associated_dosha : null);
      saveSymHistory({
        text,
        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        lang: r.detected_language || target_lang,
        topConcept
      });

      // Handle emergency
      if (r.reason === "emergency_symptom_detected" || r.is_emergency) {
        out.innerHTML = `
          <article class="a emergency" role="alert" style="border-left:4px solid var(--berry);padding:18px">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
              <span class="badge" style="background:var(--berry);color:#fff;font-weight:700">EMERGENCY RED-FLAG</span>
              <h3 style="margin:0;color:var(--berry)">${t("emergency_title") || "Urgent Medical Care Required"}</h3>
            </div>
            <p style="font-size:1.05rem;line-height:1.5;margin-bottom:12px">${esc(r.message || r.educational_boundary)}</p>
            <div class="notice" style="background:rgba(180,40,40,.08);border-color:var(--berry)">
              <strong>Clinical Action:</strong> Please contact emergency medical services (such as 112 / 108 in India or 911 / 999 internationally) or visit the nearest acute care facility immediately.
            </div>
            <div class="actions" style="margin-top:12px"></div>
          </article>`;
        const ctl = playerControls(() => r.message, (r.target_language || "en").slice(0, 2));
        $(".actions", out).append(ctl);
        if (r.tts && r.tts.audio_base64?.length) Player.playBase64(r.tts.audio_base64, ctl);
        else Player.speak(r.message, (r.target_language || "en").slice(0, 2), ctl);
        return;
      }

      // Handle graceful abstention
      if (r.abstained) {
        out.innerHTML = `
          <article class="a abstain" style="border-left:4px solid var(--clay);padding:18px">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
              <span class="badge" style="background:var(--clay);color:#fff">CLINICAL ABSTENTION</span>
              <h3 style="margin:0">${t("abstain_title") || "Outside Classical AyurMitra Boundaries"}</h3>
            </div>
            <p style="font-size:1.02rem;margin-bottom:10px">${esc(r.message || r.educational_boundary)}</p>
            <div class="notice">
              <strong>How to explore:</strong> Describe physical sensations such as joint dryness, digestive heaviness, feeling cold, throat irritation, burning sensations, or sleep patterns in English, Hindi, Kannada, or code-mixed terms.
            </div>
          </article>`;
        return;
      }

      // Render 5 RAG-Powered Sections
      out.innerHTML = renderSymptomAnalysis(r);

      // Render audio player for summary if available
      if (r.summary) {
        const act = $(".sym-actions", out);
        if (act) act.append(playerControls(() => r.summary, (r.target_language || "en").slice(0, 2)));
      }
    } catch (e2) {
      if (e2.name !== "AbortError") out.innerHTML = `<div class="err">${esc(e2.message)}</div>`;
    }
  });

  // ── herbs ──────────────────────────────────────────────────────────────────
  async function loadHerbContext(context, dosha) {
    const banner = $("#herb-context-banner");
    if (banner) {
      banner.hidden = false;
      const cs = $("#herb-context-symptom"); if (cs) cs.textContent = context || "Symptom Context";
      const cd = $("#herb-context-dosha"); if (cd) cd.textContent = dosha || "Vata";
    }

    const results = $("#herb-results");
    if (results) results.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div>`;

    try {
      const r = await api("/api/herbs/context", { key: "herb_ctx", params: { q: context || "", dosha: dosha || "" } });
      if (results && r.recommended_herbs && r.recommended_herbs.length) {
        results.innerHTML = r.recommended_herbs.map(h => `
          <button class="herb" data-id="${esc(h.graph_id || h.name)}" style="border-top:3px solid var(--sage);text-align:left">
            <i>${esc(h.botanical_name)}</i><br>
            <span class="seal" style="margin:6px 0">${esc(h.name)} ${h.label_sa_deva ? `<span class="alt">${esc(h.label_sa_deva)}</span>` : ""}</span><br>
            <p style="margin:6px 0;font-size:.82rem;line-height:1.4;color:var(--ink-1)"><strong>Classical rationale:</strong> ${esc(h.dosha_rationale)}</p>
            <small style="color:var(--ink-3)">${h.sample_uses && h.sample_uses.length ? `Recorded uses: ${esc(h.sample_uses.join(", "))}` : `Associated with ${esc(h.associated_dosha)} balance`}</small>
          </button>
        `).join("");
      } else if (results) {
        results.innerHTML = `<div class="empty">No specific herbs found for this context. Use the search bar above.</div>`;
      }

      if (r.lifestyle_guidelines && r.lifestyle_guidelines.length) {
        const topOut = $("#topic-out");
        if (topOut) {
          topOut.innerHTML = `
            <div class="panel notice" style="margin-top:14px">
              <h3 style="margin:0 0 6px 0">🌿 Aligned Daily &amp; Seasonal Regimen (${esc(r.dosha || "Traditional")})</h3>
              <p style="margin:0;font-size:.88rem;color:var(--ink-2)">${esc(r.classical_principle || "")}</p>
            </div>
            ${r.lifestyle_guidelines.map(lg => `
              <div class="panel" style="margin-top:10px">
                <h4 style="margin:0 0 6px 0">${esc(lg.title || lg.key)}</h4>
                ${(lg.passages || []).map(p => `
                  <blockquote style="margin:8px 0;padding-left:12px;border-left:3px solid var(--sage);font-size:.88rem">
                    <small class="muted">${esc(p.source_id)} · ${esc(p.locator || "")}</small><br>
                    ${esc(p.text || "")}
                  </blockquote>
                `).join("")}
              </div>
            `).join("")}
          `;
        }
      }
    } catch (e) {
      if (results) results.innerHTML = `<div class="err">${esc(e.message)}</div>`;
    }
  }

  function initHerbs() {
    const filters = [
      { label: "Ashwagandha", q: "ashwagandha" },
      { label: "Tulsi", q: "ocimum" },
      { label: "Neem", q: "azadirachta" },
      { label: "Amalaki (Amla)", q: "emblica" },
      { label: "Haritaki", q: "chebula" },
      { label: "Surana (Piles/Arshas)", q: "amorphophallus" },
      { label: "Brahmi", q: "bacopa" },
      { label: "Guggulu", q: "commiphora" },
      { label: "Shatavari", q: "asparagus" },
      { label: "Ginger (Shunthi)", q: "zingiber" }
    ];
    const hf = $("#herb-filters");
    if (hf) {
      hf.innerHTML = filters.map((f, i) => `<button type="button" class="chip-btn" data-q="${esc(f.q)}">${esc(f.label)}</button>`).join("");
      hf.addEventListener("click", e => {
        const b = e.target.closest("[data-q]");
        if (!b) return;
        $$("#herb-filters [data-q]").forEach(x => x.classList.toggle("active", x === b));
        $("#herb-q").value = b.dataset.q;
        $("#herb-q").dispatchEvent(new Event("input"));
        run();
      });
    }

    const hq = $("#herb-q");
    if (hq) enableAutoExpand(hq);

    const run = debounce(async () => {
      const v = $("#herb-q").value.trim();
      const searchMsg = $("#herb-search-msg");
      const lifeSec = $("#lifestyle-search-section");
      const lifeOut = $("#lifestyle-search-out");

      if (!v) {
        if (searchMsg) searchMsg.innerHTML = `<p class="muted">Showing popular classical Ayurvedic medicinal plants. Enter any symptom, health concern, or plant name above to search.</p>`;
        if (lifeSec) lifeSec.hidden = true;
        try {
          const r = await api("/api/herbs/search", { key: "herbs", params: { q: "Withania somnifera", limit: 12 } });
          $("#herb-results").innerHTML = (r.results || []).map(h => `
            <button class="herb" data-id="${esc(h.id)}" style="cursor:pointer;text-align:left">
              <i>${esc(h.botanical_name)}</i><br>
              ${h.api_names && h.api_names.length ? `<span class="seal" style="margin:6px 0">${esc(h.api_names[0].replace(/_\d+$/, ""))}${h.label_sa_deva ? ` <span class="alt">${esc(h.label_sa_deva)}</span>` : ""}</span><br>` : ""}
              <small>${esc(h.family || "")} · ${h.n_recorded_uses} recorded uses · ${h.n_formulations} formulations</small>
            </button>
          `).join("");
          if (r.results && r.results.length) showHerb(r.results[0].id);
        } catch (e0) {}
        return;
      }

      $("#herb-results").innerHTML = `<div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div>`;
      if (searchMsg) searchMsg.innerHTML = `<div class="skeleton" style="width:60%"></div>`;

      try {
        const [r, lifeR] = await Promise.all([
          api("/api/herbs/search", { key: "herbs", params: { q: v, limit: 18 } }),
          api("/api/lifestyle/search", { key: "life_search", params: { q: v, limit: 4 } }).catch(() => null)
        ]);

        if (searchMsg) {
          searchMsg.innerHTML = `<p style="margin:0 0 10px 0;line-height:1.5;font-size:.95rem">${esc(r.explanation || "")}</p>`;
        }

        if (r.results && r.results.length) {
          $("#herb-results").innerHTML = r.results.map(h => `
            <button class="herb" data-id="${esc(h.id)}" style="border-top:3px solid var(--sage);cursor:pointer;position:relative;text-align:left">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
                <i>${esc(h.botanical_name)}</i>
                <span class="badge ok" style="font-size:.7rem">${esc(h.match_type === "direct_name" ? "Plant Match" : (h.match_type === "therapeutic_use" ? "Traditional Use" : "Corpus Hit"))}</span>
              </div>
              ${h.api_names && h.api_names.length ? `<span class="seal" style="margin:6px 0">${esc(h.api_names[0].replace(/_\d+$/, ""))}${h.label_sa_deva ? ` <span class="alt">${esc(h.label_sa_deva)}</span>` : ""}</span><br>` : ""}
              <div class="herb-card-meta">
                <p style="margin:4px 0;font-size:.84rem;color:var(--sage-ink)"><b>Why this appeared:</b> ${esc(h.match_reason || "")}</p>
                <small style="color:var(--ink-2)">${h.common_names && h.common_names.length ? `Common: ${esc(h.common_names.join(", "))} · ` : ""}${esc(h.family || "")} · ${h.n_recorded_uses} recorded uses · ${h.n_formulations} formulations</small>
              </div>
            </button>
          `).join("");
          showHerb(r.results[0].id);
        } else {
          $("#herb-results").innerHTML = `<div class="empty">No verified Ayurvedic plant records found for “${esc(v)}”.<br><small>Try searching by clinical symptom (e.g., piles, digestion, sleep, joint stiffness) or Sanskrit name.</small></div>`;
          $("#herb-detail").innerHTML = `<div class="empty">No herb records for “${esc(v)}”. Choose or search another term.</div>`;
        }

        // Query-driven Lifestyle RAG passages
        if (lifeR && lifeR.passages && lifeR.passages.length) {
          if (lifeSec) lifeSec.hidden = false;
          if (lifeOut) {
            lifeOut.innerHTML = `
              <p class="lead" style="margin:0 0 10px 0;font-size:.95rem">${esc(lifeR.explanation)}</p>
              ${lifeR.who_terms && lifeR.who_terms.length ? `
                <h4 style="margin:10px 0 6px">Classical Terminology</h4>
                <ul class="edge-list">${lifeR.who_terms.map(w => `<li><b>${esc(w.term)}</b> ${w.iast ? `<span class="seal">${esc(w.iast)}</span>` : ""}<p style="margin:4px 0">${esc(w.definition || "")}</p><small class="muted">${esc(w.locator || "")}</small></li>`).join("")}</ul>
              ` : ""}
              <h4 style="margin:14px 0 6px">Classical Literature Passages</h4>
              ${lifeR.passages.map(p => `
                <blockquote style="margin:10px 0;padding:10px 14px;border-left:3px solid var(--sage);background:var(--surface-2);border-radius:0 6px 6px 0">
                  <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                    <strong>${esc(p.source_id)}</strong>
                    <small class="muted">${esc(p.locator || "")} <code class="mono">${esc(p.chunk_id)}</code></small>
                  </div>
                  <p style="margin:0 0 6px 0;font-size:.9rem;line-height:1.5">${esc(p.text)}…</p>
                  <small class="muted" style="display:block"><b>Relevance:</b> ${esc(p.match_reason || "")}</small>
                  <small class="muted" style="display:block;font-style:italic">${esc(p.caution || "")}</small>
                </blockquote>
              `).join("")}
            `;
          }
        } else {
          if (lifeSec) lifeSec.hidden = true;
        }

      } catch (e) {
        if (e.name !== "AbortError") $("#herb-results").innerHTML = `<div class="err">${esc(e.message)}</div>`;
      }
    }, 240);

    $("#herb-q").addEventListener("input", run);
    $("#herb-submit") && $("#herb-submit").addEventListener("click", run);
    $("#herb-search-form") && $("#herb-search-form").addEventListener("submit", e => { e.preventDefault(); run(); });
    $("#herb-clear-btn") && $("#herb-clear-btn").addEventListener("click", () => {
      $("#herb-q").value = "";
      $("#herb-q").dispatchEvent(new Event("input"));
      run();
    });

    $("#herb-results").addEventListener("click", e => {
      const b = e.target.closest("[data-id]");
      if (b) showHerb(b.dataset.id);
    });

    $("#herb-context-clear") && $("#herb-context-clear").addEventListener("click", () => {
      const banner = $("#herb-context-banner");
      if (banner) banner.hidden = true;
      location.hash = "#/herbs";
      $("#herb-q").value = "";
      $("#herb-q").dispatchEvent(new Event("input"));
      run();
    });

    // Lifestyle topic buttons
    api("/api/lifestyle").then(r => {
      $("#topics").innerHTML = r.topics.map(x => `<button class="chip-btn" data-k="${x.key}">${esc(x["title_" + UI] || x.title_en)}</button>`).join("");
    }).catch(() => {});

    $("#topics").addEventListener("click", async e => {
      const b = e.target.closest("[data-k]");
      if (!b) return;
      $$("#topics [data-k]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
      const out = $("#topic-out");
      out.innerHTML = `<div class="skeleton"></div>`;
      try {
        const r = await api("/api/lifestyle/" + b.dataset.k);
        out.innerHTML = `<p class="muted">${esc(r.note)}</p>` + (r.who_terms.length ? `<h3>WHO terminology</h3><ul class="edge-list">${r.who_terms.map(w => `<li><b>${esc(w.term)}</b> ${w.iast ? `<span class="seal">${esc(w.iast)}</span>` : ""}<p style="margin:4px 0">${esc(w.definition || "")}</p><small>${esc(w.locator)}</small></li>`).join("")}</ul>` : "") +
          `<h3 style="margin-top:14px">Passages from the corpus</h3>` + r.passages.map(p => `<blockquote style="margin:10px 0;padding-left:12px;border-left:3px solid var(--line)"><small>${esc(p.source_id)} · ${esc(p.locator || "")} <code class="mono">${esc(p.chunk_id)}</code></small><br>${esc(p.text)}…</blockquote>`).join("");
      } catch (e2) {
        out.innerHTML = `<div class="err">${esc(e2.message)}</div>`;
      }
    });

    run();
  }
  async function showHerb(id) {
    const p = $("#herb-detail"); p.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div>`;
    try {
      const d = await api("/api/herbs/" + encodeURIComponent(id), { key: "herb" });
      p.innerHTML = `<p class="muted" style="margin:0">${esc(d.family || "")}</p><h2><i>${esc(d.botanical_name)}</i></h2>
        ${d.api_names.length ? `<p>${d.api_names.map(a => `<span class="seal" style="margin:0 6px 6px 0">${esc(a.replace(/_\d+$/, ""))}</span>`).join("")}${d.label_sa_deva ? `<span class="seal">${esc(d.label_sa_deva)} <span class="alt">${esc(d.label_kn_script_sanskrit || "")}</span></span>` : ""}</p><p><small>${esc(d.script_label_note || "")}</small></p>` : ""}
        <div class="notice">${esc(d.traditional_records_note)}</div>
        ${d.common_names.length ? `<p><b>${t("common")}:</b> ${esc(d.common_names.join(", "))}</p>` : ""}
        ${d.synonyms.length ? `<p><b>${t("synonyms")}:</b> <i>${esc(d.synonyms.slice(0, 8).join(", "))}</i></p>` : ""}
        <p><small>${esc(d.source_id)} — ${esc(d.locator)}</small></p>
        <h3>${t("recorded_uses")} (${d.n_recorded_uses})</h3>
        <ul class="edge-list">${d.recorded_traditional_uses.slice(0, 25).map(u => `<li>${esc(u.use)}${u.plant_parts.length ? ` <small>(${esc(u.plant_parts.join(", "))})</small>` : ""}<br><small>${esc(u.locator)}</small></li>`).join("") || "<li>—</li>"}</ul>
        ${d.formulations.length ? `<h3 style="margin-top:14px">${t("formulations")}</h3><ul class="edge-list">${d.formulations.map(f => `<li><b>${esc(f.name)}</b> ${f.name_deva ? `<span class="alt">${esc(f.name_deva)}</span>` : ""} — ${esc(f.plant_part || "")}<br><small>API (Sanskrit): ${esc(f.api_uses_sanskrit || "")}</small><br><small>${esc(f.locator)}</small></li>`).join("")}</ul>` : ""}
        <p class="muted" style="margin-top:12px">${esc(d.disclaimer)}</p>
        <div class="actions"><a class="btn" href="#/graph?center=${encodeURIComponent(d.id)}">${t("nav_graph")}</a></div>`;
      p.scrollIntoView({ block: "nearest" });
    } catch (e) { if (e.name !== "AbortError") p.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  }

  // ── research lab ───────────────────────────────────────────────────────────
  $("#cmp-form").addEventListener("submit", async e => {
    e.preventDefault(); const out = $("#cmp-out"); out.innerHTML = ["B0", "B1", "P1", "P2"].map(() => `<div class="panel"><div class="skeleton"></div><div class="skeleton"></div></div>`).join("");
    try {
      const r = await api("/api/research/compare", { key: "cmp", params: { query: $("#cmp-q").value } });
      out.innerHTML = Object.entries(r.modes).map(([m, x]) => `<div class="panel"><h3>${m}</h3>
        <p><small>Query sent to retrieval:</small><br><em>${esc(x.retrieval_query || x.canonical_query || "—")}</em></p>
        <p><small>Translation: ${esc(x.translation_meta?.method || "—")}</small></p>
        ${x.abstained ? `<p><span class="badge">abstained: ${esc(x.abstention_reason)}</span></p>` : ""}
        <ol style="padding-left:18px;font-size:.88rem">${x.retrieved.map(p => `<li><code class="mono">${esc(p.chunk_id)}</code> <small>${esc(p.locator || "")}</small></li>`).join("")}</ol>
        <details class="fold"><summary>Answer</summary><div class="answer-body">${md(displayAnswer(x.answer || ""))}</div></details></div>`).join("");
    } catch (e2) { out.innerHTML = `<div class="err">${esc(e2.message)}</div>`; }
  });
  function bars(rows, { max = 1, fmt = v => (v * 100).toFixed(1) + "%" } = {}) {
    // rows: [{label, value, ci:[lo,hi]}]
    const W = 520, rowH = 30, L = 44, H = rows.length * rowH + 24, sx = v => L + (W - L - 170) * Math.max(0, Math.min(1, v / max));
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(rows.map(r => r.label + " " + fmt(r.value)).join(", "))}">` + rows.map((r, i) => {
      const y = 10 + i * rowH; const ci = r.ci && r.ci.length === 2;
      return `<text x="0" y="${y + 15}">${esc(r.label)}</text><rect x="${L}" y="${y + 4}" width="${Math.max(1, sx(r.value) - L)}" height="14" rx="3" fill="${r.color || "var(--sage)"}"/>` +
        (ci ? `<line x1="${sx(r.ci[0])}" x2="${sx(r.ci[1])}" y1="${y + 11}" y2="${y + 11}" stroke="var(--ink)" stroke-width="1.4"/><line x1="${sx(r.ci[0])}" x2="${sx(r.ci[0])}" y1="${y + 6}" y2="${y + 16}" stroke="var(--ink)"/><line x1="${sx(r.ci[1])}" x2="${sx(r.ci[1])}" y1="${y + 6}" y2="${y + 16}" stroke="var(--ink)"/>` : "") +
        `<text x="${Math.max(sx(r.value), ci ? sx(r.ci[1]) : 0) + 6}" y="${y + 15}">${fmt(r.value)}${ci ? ` [${fmt(r.ci[0])}, ${fmt(r.ci[1])}]` : ""}</text>`;
    }).join("") + `</svg>`;
  }
  async function initResearch() {
    const out = $("#res-out");
    try {
      const [res, probe, kgStats] = await Promise.all([
        api("/api/research/results"),
        api("/api/research/probe"),
        api("/api/graph/stats").catch(() => null)
      ]);
      const v2 = res.v2; let h = "";
      const kgNodes = kgStats?.nodes ? Number(kgStats.nodes).toLocaleString() : "9,530";
      const kgEdges = kgStats?.edges ? Number(kgStats.edges).toLocaleString() : "72,341";
      h += `<div class="stat-row panel" style="margin-bottom:14px">
        <div><b>2,887</b><span>Corpus text chunks</span></div>
        <div><b>8</b><span>Authoritative raw datasets</span></div>
        <div><b>${kgNodes}</b><span>Knowledge graph nodes</span></div>
        <div><b>${kgEdges}</b><span>Typed &amp; provenance edges</span></div>
        <div><b>3</b><span>Evaluation languages (EN, HI, KN)</span></div>
      </div>`;
      if (!v2) h += `<div class="empty">No re-run results yet. Run <code class="mono">python -m app.evaluation.evaluator_v2</code>.</div>`;
      else {
        const sys = v2.systems || {}; const main = Object.entries(sys).filter(([, s]) => s.kind === "main");
        const dec = v => v.toFixed(3);
        const metric = (k, label, fmt) => `<div class="panel chart"><h3>${label}</h3>${bars(main.map(([n, s]) => ({ label: n, value: s.metrics[k]?.mean ?? 0, ci: s.metrics[k]?.ci })), fmt ? { fmt } : {})}</div>`;
        h += `<div class="panel"><h2>Measured results — ${esc(v2.meta?.split || "")} split</h2><p class="muted">${esc(v2.meta?.summary || "")}</p>
          <p><small>${esc(v2.meta?.n_seeds)} seed questions × ${esc((v2.meta?.languages || []).length)} language variants · CIs: ${esc(v2.meta?.ci_method || "")} · backends: ${esc(JSON.stringify(v2.meta?.backends || {}))}</small></p></div>`;
        h += `<div class="charts">${metric("recall_at_5", "Recall@5")}${metric("mrr", "MRR", dec)}${metric("ndcg_at_5", "nDCG@5", dec)}${metric("false_abstention_rate", "False-abstention rate")}</div>`;
        const langs = v2.meta?.languages || [];
        h += `<div class="panel" style="margin-top:12px"><h3>Recall@5 by language</h3><div class="table-wrap"><table><thead><tr><th>System</th>${langs.map(l => `<th>${esc(l)}</th>`).join("")}</tr></thead><tbody>` +
          main.map(([n, s]) => `<tr><td>${n}</td>${langs.map(l => `<td>${((s.by_language?.[l]?.recall_at_5 ?? 0) * 100).toFixed(1)}%</td>`).join("")}</tr>`).join("") + `</tbody></table></div></div>`;
        if (v2.paired) h += `<div class="panel" style="margin-top:12px"><h3>Paired differences (bootstrap over seed questions)</h3><div class="table-wrap"><table><thead><tr><th>Comparison</th><th>Recall@5 Δ</th><th>MRR Δ</th><th>95% CI (Recall@5)</th><th>Verdict</th></tr></thead><tbody>` +
          Object.entries(v2.paired).map(([k, p]) => `<tr><td>${esc(k)}</td><td>${(p.recall_at_5.diff * 100).toFixed(1)} pts</td><td>${p.mrr.diff.toFixed(3)}</td><td>[${(p.recall_at_5.ci[0] * 100).toFixed(1)}, ${(p.recall_at_5.ci[1] * 100).toFixed(1)}]</td><td>${esc(p.verdict || "")}</td></tr>`).join("") + `</tbody></table></div></div>`;
        const abl = Object.entries(sys).filter(([, s]) => s.kind !== "main");
        if (abl.length) h += `<div class="panel" style="margin-top:12px"><h3>Ablations and baselines</h3><div class="table-wrap"><table><thead><tr><th>Configuration</th><th>What changes</th><th>Recall@5</th><th>MRR</th><th>False abstention</th></tr></thead><tbody>` +
          abl.map(([n, s]) => `<tr><td>${esc(n)}</td><td>${esc(s.description || "")}</td><td>${((s.metrics.recall_at_5?.mean ?? 0) * 100).toFixed(1)}%</td><td>${(s.metrics.mrr?.mean ?? 0).toFixed(3)}</td><td>${((s.metrics.false_abstention_rate?.mean ?? 0) * 100).toFixed(1)}%</td></tr>`).join("") + `</tbody></table></div></div>`;
        if (v2.error_analysis) h += `<div class="panel" style="margin-top:12px"><h3>Stage-wise error analysis (${esc(v2.error_analysis.system || "P1")})</h3><div class="table-wrap"><table><thead><tr><th>First failing stage</th>${langs.map(l => `<th>${esc(l)}</th>`).join("")}<th>Example</th></tr></thead><tbody>` +
          v2.error_analysis.stages.map(s => `<tr><td>${esc(s.stage)}</td>${langs.map(l => `<td>${s.by_language?.[l] ?? 0}</td>`).join("")}<td><small>${esc((s.examples || [])[0] || "")}</small></td></tr>`).join("") + `</tbody></table></div></div>`;
        if (v2.limitations) h += `<div class="panel notice" style="margin-top:12px"><h3>Pilot study — limitations</h3><ul>${v2.limitations.map(x => `<li>${esc(x)}</li>`).join("")}</ul></div>`;
      }
      if (probe.v2) h += `<div class="panel" style="margin-top:12px"><h2>Go/No-Go terminology probe (re-run)</h2><p class="muted">${esc(probe.v2.note || "")}</p><div class="table-wrap"><table><thead><tr><th>Probe</th><th>Source query</th><th>Unprotected output</th><th>Status</th><th>Protected output</th><th>Status</th></tr></thead><tbody>` +
        probe.v2.items.map(x => `<tr><td>${esc(x.probe_id)}<br><small>${esc(x.concept)}</small></td><td lang="${esc(x.lang)}">${esc(x.source_query)}</td><td>${esc(x.unprotected_output)}<br><small>${esc(x.unprotected_method)}</small></td><td>${esc(x.unprotected_status)}</td><td>${esc(x.protected_output)}</td><td>${esc(x.protected_status)}</td></tr>`).join("") + `</tbody></table></div></div>`;
      h += `<div class="panel" style="margin-top:12px"><h3>Research Data &amp; Export Downloads</h3>
        <p class="muted">Download peer-reviewable experiment outputs, benchmark predictions, and error traces:</p>
        <div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px">` +
        (res.files || []).map(f => `<a class="btn" href="/api/research/files/${encodeURIComponent(f)}" download style="font-size:.85rem"><svg width="14" height="14" style="margin-right:6px"><use href="#i-lab"/></svg>${esc(f)}</a>`).join("") +
        `</div><p class="muted" style="margin-top:12px"><small>The original <code class="mono">experiment_results_v1.json</code> is kept unchanged for comparison; its metric definitions are documented as flawed in docs/AUDIT.md (F17, F18).</small></p></div>`;
      out.innerHTML = h;
    } catch (e) { out.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  }

  // ── about ──────────────────────────────────────────────────────────────────
  async function initAbout() {
    const out = $("#about-out");
    out.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div>`;
    try {
      const a = await api("/api/about");
      const stages = a.architecture_stages || [];
      const sources = a.sources || [];
      const safetyCases = a.safety_cases || [];

      out.innerHTML = `
        <!-- PART 1: Interactive Architecture Explorer -->
        <div class="panel arch" style="margin-bottom:20px">
          <h2 style="margin-top:0">1. Interactive 11-Stage RAG Pipeline Explorer</h2>
          <p class="muted" style="margin-bottom:14px">
            Inspect each stage of AyurMitra's multilingual retrieval-augmented architecture. Click any stage to inspect its responsible Python module, input/output contracts, active neural model, and deterministic fallback.
          </p>
          <div class="stage-flow" id="stage-buttons" role="group" aria-label="Pipeline Stages">
            ${stages.map((st, i) => `
              <button type="button" class="stage-btn${i === 0 ? " active" : ""}" data-stage-id="${st.id}">
                <span class="stage-num">${st.step}</span>
                <span>${esc(st.name)}</span>
              </button>
            `).join("")}
          </div>
          <div id="arch-inspector" class="stage-inspector" aria-live="polite"></div>
        </div>

        <!-- PART 2: Live RAG Demonstration -->
        <div class="panel" style="margin-bottom:20px">
          <h2 style="margin-top:0">2. Live RAG Demonstration: Trace Evidence in Real-Time</h2>
          <p class="muted" style="margin-bottom:12px">
            Watch AyurMitra execute the complete 7-step pipeline trace for any research query. The system tracks term protection, translation, hybrid retrieval scoring, knowledge graph facts, and evidence coverage.
          </p>
          <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
            <button type="button" class="btn ghost trace-demo-btn" data-q="What is Ayurveda?">"What is Ayurveda?"</button>
            <button type="button" class="btn ghost trace-demo-btn" data-q="What are the functions of Pitta dosha?">"What are the functions of Pitta dosha?"</button>
            <button type="button" class="btn ghost trace-demo-btn" data-q="How does Agni affect digestion?">"How does Agni affect digestion?"</button>
            <button type="button" class="btn ghost trace-demo-btn" data-q="ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?">"ಪಿತ್ತಕ್ಕೆ ಸಂಬಂಧಿಸಿದ ಲಕ್ಷಣಗಳು ಯಾವುವು?"</button>
          </div>
          <form id="trace-form" class="toolbar" style="margin-bottom:14px">
            <label for="trace-q" class="sr">Enter question to trace</label>
            <input class="input" id="trace-q" style="flex:1;min-width:260px" value="What is Ayurveda?" placeholder="Enter any question to inspect pipeline...">
            <button class="btn primary" type="submit">Run Live Trace</button>
          </form>
          <div id="trace-out" aria-live="polite"></div>
        </div>

        <!-- PART 3: Data Sources & Evidence Explorer -->
        <div class="panel" style="margin-bottom:20px">
          <h2 style="margin-top:0">3. Data Sources &amp; Evidence Explorer (8 Authoritative Datasets)</h2>
          <p class="muted" style="margin-bottom:12px">
            AyurMitra grounds all responses in 8 curated, authoritative Ayurvedic datasets. Every record is cryptographically verified against SHA-256 baseline hashes.
          </p>
          <div class="langs" id="source-filters" style="margin-bottom:14px">
            <button type="button" class="chip-btn active" data-cat="all">All Sources (8)</button>
            <button type="button" class="chip-btn" data-cat="Corpus">Corpus</button>
            <button type="button" class="chip-btn" data-cat="Knowledge Graph">Knowledge Graph</button>
            <button type="button" class="chip-btn" data-cat="Pharmacopoeia">Pharmacopoeia</button>
            <button type="button" class="chip-btn" data-cat="Evaluation">Evaluation</button>
          </div>
          <div id="sources-grid" style="display:grid;grid-template-columns:repeat(auto-fit, minmax(300px, 1fr));gap:14px"></div>
        </div>

        <!-- PART 4: Interactive Safety Centre -->
        <div class="panel" style="margin-bottom:20px">
          <h2 style="margin-top:0">4. Interactive Safety &amp; Governance Centre</h2>
          <p class="muted" style="margin-bottom:14px">
            AyurMitra enforces 10 strict clinical governance principles. Test the safety gates with real demonstration cases below.
          </p>
          <div style="background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:18px">
            <h3 style="margin-top:0;font-size:1.05rem">10 Core Safety Principles</h3>
            <ol style="margin:0 0 0 20px;padding:0;line-height:1.6;font-size:.9rem">
              <li><strong>Pre-retrieval emergency red-flag triage:</strong> Acute life-threatening symptoms trigger an immediate referral before any retrieval or RAG processing.</li>
              <li><strong>Strict dosage &amp; prescription refusal:</strong> Specific milligram dosages, schedules, and custom prescription requests are strictly rejected.</li>
              <li><strong>Non-diagnostic educational boundary:</strong> All outputs are conceptual education; no patient-specific diagnosis is ever formulated.</li>
              <li><strong>Extractive evidence grounding:</strong> Answers quote or strictly paraphrase verified passages; ungrounded hallucinations are prohibited.</li>
              <li><strong>Mandatory provenance citations:</strong> Every factual claim carries an authoritative source ID, chapter, or section locator.</li>
              <li><strong>Explicit abstention over hallucination:</strong> If the corpus lacks relevant passages, AyurMitra clearly states missing evidence rather than guessing.</li>
              <li><strong>Transparent fallback disclosure:</strong> When neural backends (IndicTrans2, Sentence-Transformers, Faster-Whisper) use local fallbacks, the system discloses this explicitly.</li>
              <li><strong>Classical correlation vs. biomedical causation:</strong> Dosha and Agni concepts are explained as classical taxonomy, not biomedical pathology.</li>
              <li><strong>Zero panacea / miracle claims:</strong> Exaggerated claims of guaranteed disease cure are rejected.</li>
              <li><strong>Human practitioner primacy:</strong> Clear guidance to consult licensed Ayurvedic doctors (BAMS/MD) or biomedical specialists.</li>
            </ol>
          </div>

          <h3 style="font-size:1.05rem;margin-bottom:10px">Live Safety Demonstration Cases</h3>
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(280px, 1fr));gap:12px" id="safety-cases-grid"></div>
        </div>

        <!-- PART 5: Privacy & Data Handling Disclosures -->
        <div class="panel" style="margin-bottom:20px">
          <h2 style="margin-top:0">5. Privacy &amp; Data Handling Policy</h2>
          <p style="line-height:1.6;font-size:.92rem">${esc(a.privacy || "")}</p>
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(260px, 1fr));gap:12px;margin-top:12px">
            <div class="notice" style="background:var(--surface)">
              <strong>Ephemeral Processing:</strong> AyurMitra does not persist user queries, session transcripts, or IP addresses in any database. Processing occurs strictly in-memory during request execution.
            </div>
            <div class="notice" style="background:var(--surface)">
              <strong>Zero Tracking:</strong> No tracking cookies, third-party analytics pixels, or telemetry beacons are embedded in this application.
            </div>
            <div class="notice" style="background:var(--surface)">
              <strong>Voice Privacy:</strong> Voice inputs are transcribed either in-browser (via browser Web Speech API) or processed in-memory via Faster-Whisper. Audio streams are immediately discarded after transcription.
            </div>
          </div>
        </div>

        <!-- PART 6: Research Team & Academic Context -->
        <div class="panel">
          <h2 style="margin-top:0">6. Academic Team &amp; Project Provenance</h2>
          <p style="line-height:1.6;font-size:.92rem">
            <strong>Project:</strong> AyurMitra Multilingual Clinical RAG &amp; Ontological Graph Assistant<br>
            <strong>Team Members:</strong> ${(a.team?.members || []).map(esc).join(", ")}<br>
            <strong>Project Guide:</strong> ${esc(a.team?.guide || "")}<br>
            <strong>Institution:</strong> ${esc(a.team?.institution || "")} (${esc(a.team?.team || "")})<br>
            <strong>Course:</strong> NLP-CIE3 Final Submission Project
          </p>
        </div>
      `;

      // Wire Stage Inspector
      function selectStage(stId) {
        const stage = stages.find(s => s.id === stId) || stages[0];
        if (!stage) return;
        $$("#stage-buttons .stage-btn").forEach(b => b.classList.toggle("active", b.dataset.stageId === stage.id));
        const insp = $("#arch-inspector");
        const statusClass = stage.status?.includes("Active") ? "ok" : (stage.status?.includes("Enforced") ? "seal" : "warn");
        insp.innerHTML = `
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;margin-bottom:12px">
            <div>
              <span class="badge" style="background:var(--forest);color:#fff">Stage ${stage.step} of 11</span>
              <h3 style="margin:4px 0 0 0;font-size:1.2rem">${esc(stage.name)}</h3>
            </div>
            <span class="status-pill ${statusClass}">${esc(stage.status || "Active")}</span>
          </div>
          <p style="font-size:1rem;line-height:1.55;margin-bottom:14px">${esc(stage.purpose)}</p>
          <div style="display:grid;grid-template-columns:repeat(auto-fit, minmax(220px, 1fr));gap:12px;background:var(--surface);padding:14px;border:1px solid var(--line);border-radius:8px">
            <div><small class="muted">Responsible Module / Code</small><br><code class="mono" style="font-size:.82rem">${esc(stage.module)}</code></div>
            <div><small class="muted">Input Contract</small><br><span style="font-size:.88rem">${esc(stage.input)}</span></div>
            <div><small class="muted">Output Contract</small><br><span style="font-size:.88rem">${esc(stage.output)}</span></div>
            <div><small class="muted">Active Neural Backend</small><br><strong style="font-size:.88rem">${esc(stage.backend)}</strong></div>
            <div><small class="muted">Fallback Strategy</small><br><span style="font-size:.88rem">${esc(stage.fallback)}</span></div>
            <div><small class="muted">Key Limitations / Caveats</small><br><span style="font-size:.88rem;color:var(--ink-2)">${esc(stage.limitations || "None noted")}</span></div>
          </div>
        `;
      }
      $("#stage-buttons").addEventListener("click", e => {
        const b = e.target.closest("[data-stage-id]");
        if (b) selectStage(b.dataset.stageId);
      });
      if (stages.length) selectStage(stages[0].id);

      // Wire Live Trace
      async function runTrace(query) {
        const outDiv = $("#trace-out");
        outDiv.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div>`;
        try {
          const r = await api("/api/research/trace?query=" + encodeURIComponent(query));
          outDiv.innerHTML = `
            <div style="background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:16px;margin-top:10px">
              <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:12px">
                <div>
                  <strong>Query:</strong> "${esc(r.query)}"
                  <span class="badge" style="margin-left:8px">${esc(r.detected_language)}</span>
                  ${r.is_code_mixed ? `<span class="badge warn">Code-mixed: ${esc(r.code_mix_type)}</span>` : ""}
                </div>
                <div style="font-size:.85rem;color:var(--ink-3)">
                  Total Latency: <strong>${Math.round(r.latency_ms || 0)} ms</strong> · Retrievable Chunks: <strong>${r.retrieved_passages?.length || 0}</strong>
                </div>
              </div>
              <div class="trace-steps">
                ${(r.trace_steps || []).map(st => `
                  <div class="trace-step">
                    <div class="trace-step-header">
                      <span class="score-badge">${st.step}</span>
                      <strong>${esc(st.name)}</strong>
                      <span class="badge" style="margin-left:auto">${esc(st.module)}</span>
                    </div>
                    <div style="font-size:.88rem;margin:4px 0 6px 0">${esc(st.details)}</div>
                    ${st.data ? `<pre class="mono" style="background:var(--bg);padding:8px;border-radius:6px;font-size:.76rem;overflow-x:auto;margin:0">${esc(JSON.stringify(st.data, null, 2))}</pre>` : ""}
                  </div>
                `).join("")}
              </div>
            </div>
          `;
        } catch (eTrace) {
          outDiv.innerHTML = `<div class="err">Trace failed: ${esc(eTrace.message)}</div>`;
        }
      }
      $("#trace-form").addEventListener("submit", e => {
        e.preventDefault();
        const q = $("#trace-q").value.trim();
        if (q) runTrace(q);
      });
      $$(".trace-demo-btn").forEach(btn => {
        btn.addEventListener("click", () => {
          $("#trace-q").value = btn.dataset.q;
          runTrace(btn.dataset.q);
        });
      });

      // Wire Sources Grid & Category Filters
      function renderSources(category) {
        const grid = $("#sources-grid");
        const filtered = category === "all" ? sources : sources.filter(s => s.category.toLowerCase().includes(category.toLowerCase()));
        grid.innerHTML = filtered.map(s => `
          <div class="source-card">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
              <span class="badge" style="background:var(--clay);color:#fff">${esc(s.category)}</span>
              <span class="badge ok" style="font-size:.72rem">SHA-256 Verified</span>
            </div>
            <h4 style="margin:8px 0 4px 0;font-size:1.05rem">${esc(s.title || s.name || "Ayurvedic Source")}</h4>
            <div style="font-size:.8rem;color:var(--ink-3);margin-bottom:8px">
              <strong>${esc(s.publisher || "Academic / Authority Source")}</strong> · ${esc(s.format || s.type || "Text Corpus")}
            </div>
            <p style="font-size:.86rem;line-height:1.5;margin:0 0 10px 0;flex:1">${esc(s.description || s.usage || "")}</p>
            <div style="font-size:.78rem;border-top:1px dashed var(--line);padding-top:8px;margin-top:auto;display:flex;justify-content:space-between;color:var(--ink-3);flex-wrap:wrap;gap:6px">
              <span>Records: <strong>${esc(String(s.records || "—"))}</strong></span>
              <span>Licence: <strong>${esc(s.license || s.licence || "Research Access")}</strong></span>
            </div>
          </div>
        `).join("");
      }
      renderSources("all");
      $("#source-filters").addEventListener("click", e => {
        const b = e.target.closest("[data-cat]");
        if (b) {
          $$("#source-filters .chip-btn").forEach(x => x.classList.toggle("active", x === b));
          renderSources(b.dataset.cat);
        }
      });

      // Wire Safety Cases
      const casesGrid = $("#safety-cases-grid");
      casesGrid.innerHTML = safetyCases.map((sc, i) => `
        <div class="panel" style="background:var(--surface);border:1px solid var(--line);display:flex;flex-direction:column;justify-content:space-between">
          <div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
              <span class="badge" style="background:var(--turmeric);color:var(--ink)">Test Case ${i+1}</span>
              <small class="muted">${esc(sc.expected_outcome)}</small>
            </div>
            <h4 style="margin:4px 0 8px 0;font-size:1rem">${esc(sc.title)}</h4>
            <blockquote style="margin:0 0 8px 0;padding:6px 10px;border-left:3px solid var(--turmeric);font-style:italic;font-size:.88rem">
              "${esc(sc.query)}"
            </blockquote>
            <p style="font-size:.82rem;color:var(--ink-2);margin:0 0 10px 0">${esc(sc.description)}</p>
          </div>
          <button type="button" class="btn ghost run-safety-case-btn" data-query="${esc(sc.query)}" style="font-size:.82rem">Run Live Safety Test →</button>
        </div>
      `).join("");
      casesGrid.addEventListener("click", async e => {
        const b = e.target.closest(".run-safety-case-btn");
        if (!b) return;
        const q = b.dataset.query;
        b.disabled = true;
        b.textContent = "Testing...";
        try {
          const r = await api("/api/ask", { method: "POST", body: { query: q, system_mode: "P2" } });
          b.disabled = false;
          b.textContent = "Test Completed";
          alert(`Safety Case Result for: "${q}"\n\nAbstained: ${r.abstained}\nReason: ${r.abstention_reason || "None (Answered)"}\nEmergency: ${r.is_emergency}\nAnswer Summary:\n${(r.answer || "").slice(0, 200)}...`);
        } catch (eSc) {
          b.disabled = false;
          b.textContent = "Test Failed";
          alert(`Test failed: ${eSc.message}`);
        }
      });

    } catch (e) {
      out.innerHTML = `<div class="err">${esc(e.message)}</div>`;
    }
  }

  // ── boot ───────────────────────────────────────────────────────────────────
  window.AyurMitra = { ask, Voice, Player };
  applyI18n(); route(); loadHealth(); setInterval(loadHealth, 60000);
})();
