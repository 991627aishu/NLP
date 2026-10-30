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
    if (!res.ok) throw new Error(data.message || `Request failed (${res.status})`);
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
    $("#ui-lang").value = UI; renderStarters();
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
    if (v === "herbs" && params.get("herb")) showHerb(params.get("herb"));
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
    audio: null, queue: [], utter: null, rate: 1, onend: null, el: null,
    stop() { if (this.audio) { this.audio.pause(); this.audio = null; } this.queue = []; if ("speechSynthesis" in window) speechSynthesis.cancel(); this._ui("idle"); },
    _ui(state) { if (!this.el) return; this.el.dataset.state = state; const p = $(".pp", this.el); if (p) p.textContent = state === "paused" ? t("resume") : t("pause"); },
    async speak(text, lang, el, onend) {
      this.stop(); this.el = el; this.onend = onend; this._ui("loading");
      let r; try { r = await api("/api/tts", { method: "POST", body: { text, lang, voice: $("#opt-voice").value } }); }
      catch { r = { backend: "browser", chunks: [text], browser_lang: { en: "en-IN", hi: "hi-IN", kn: "kn-IN" }[lang] || "en-IN" }; }
      if (r.audio_base64 && r.audio_base64.length) { this.queue = r.audio_base64.slice(); this._next(); }
      else this._browser(r.chunks || [r.spoken_text || text], r.browser_lang || "en-IN");
    },
    playBase64(list, el, onend) { this.stop(); this.el = el; this.onend = onend; this.queue = list.slice(); this._next(); },
    _next() {
      if (!this.queue.length) { this._ui("idle"); this.onend && this.onend(); return; }
      this.audio = new Audio("data:audio/mpeg;base64," + this.queue.shift()); this.audio.playbackRate = this.rate;
      this.audio.onended = () => this._next(); this.audio.play().catch(() => this._ui("idle")); this._ui("playing");
    },
    _browser(chunks, lang) {
      if (!("speechSynthesis" in window)) { this._ui("idle"); return; }
      const voices = speechSynthesis.getVoices(); const v = voices.find(x => x.lang === lang) || voices.find(x => x.lang.startsWith(lang.slice(0, 2)));
      chunks.forEach((c, i) => {
        const u = new SpeechSynthesisUtterance(c); u.lang = lang; u.rate = this.rate; if (v) u.voice = v;
        u.onstart = () => this._ui("playing");
        if (i === chunks.length - 1) u.onend = () => { this._ui("idle"); this.onend && this.onend(); };
        speechSynthesis.speak(u);
      });
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
       <button class="btn pp" data-a="pp">${t("pause")}</button><button class="btn" data-a="stop">${t("stopread")}</button>
       <label class="field" style="flex-direction:row;align-items:center;gap:6px">${t("speed")}
       <select class="select" data-a="rate" aria-label="${t("speed")}"><option>0.75</option><option selected>1</option><option>1.25</option><option>1.5</option></select></label>`;
    d.addEventListener("click", e => { const a = e.target.closest("[data-a]")?.dataset.a;
      if (a === "read") Player.speak(getText(), lang, d, onSpokenEnd); if (a === "pp") Player.toggle(); if (a === "stop") Player.stop(); });
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
  };
  let QL = store.get("ayur.ql", "en");
  function renderStarters() {
    $$("#qlangs [data-ql]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.ql === QL)));
    $("#starters").innerHTML = (STARTERS[QL] || STARTERS.en).map(q => `<button type="button">${esc(q)}</button>`).join("");
  }
  $("#qlangs").addEventListener("click", e => { const b = e.target.closest("[data-ql]"); if (!b) return; QL = b.dataset.ql; store.set("ayur.ql", QL); renderStarters(); });
  $("#starters").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { $("#q").value = b.textContent; ask(); } });
  const q = $("#q");
  q.addEventListener("input", () => { q.style.height = "auto"; q.style.height = Math.min(180, q.scrollHeight) + "px"; });
  q.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(); } });
  $("#composer").addEventListener("submit", e => { e.preventDefault(); ask(); });

  function addQuestion(text) { const d = document.createElement("div"); d.className = "q"; d.textContent = text; $("#thread").append(d); $("#starters-wrap").hidden = true; }
  function addSkeleton() { const d = document.createElement("div"); d.className = "a"; d.setAttribute("aria-busy", "true");
    d.innerHTML = `<span class="sr">${t("loading")}</span><div class="skeleton" style="width:60%"></div><div class="skeleton"></div><div class="skeleton" style="width:80%"></div>`;
    $("#thread").append(d); d.scrollIntoView({ block: "nearest", behavior: "smooth" }); return d; }

  async function ask(textOverride) {
    const text = (textOverride || q.value).trim(); if (!text) { q.focus(); return; }
    q.value = ""; q.style.height = ""; addQuestion(text); const sk = addSkeleton(); $("#send").disabled = true;
    try {
      const r = await api("/api/ask", { method: "POST", key: "ask", body: { query: text, mode: $("#opt-mode").value,
        target_lang: $("#opt-lang").value, web_fallback: $("#opt-web").checked, generator: $("#opt-gen").value, voice: $("#opt-voice").value } });
      renderAnswer(r, sk);
    } catch (e) { if (e.name !== "AbortError") sk.outerHTML = `<div class="err" role="alert">${esc(e.message)}</div>`; }
    finally { $("#send").disabled = false; }
  }

  const LANG_NAME = { en: "English", hi: "हिन्दी", kn: "ಕನ್ನಡ" };
  function displayAnswer(ans) { return ans.replace(/\n\*\*Sources:\*\*[\s\S]*?(?=\n\n\*\*|$)/, "").replace(/\n\n\*\*Ayurvedic terms:\*\*[^\n]*/, ""); }

  function renderAnswer(r, slot) {
    const card = document.createElement("article"); const lang = r.target_language || "en";
    card.className = "a" + (r.is_emergency ? " emergency" : r.abstained ? " abstain" : ""); card.lang = lang;
    const terms = (r.detected_terms || []).filter((x, i, a) => a.findIndex(y => y.canonical_term === x.canonical_term) === i);
    const cits = r.citations || [];
    const title = r.is_emergency ? `<h3>${t("emergency_title")}</h3>` : r.abstained ? `<h3>${t("abstain_title")}</h3>` : "";
    card.innerHTML = `
      <div class="meta"><span class="badge">${LANG_NAME[lang] || lang}</span><span class="badge">${esc(r.system_mode)}</span>
        ${r.machine_translated ? `<span class="badge mt">${t("mt_badge")}</span>` : ""}
        ${r.answer_grounding === "evidence_sentence" && lang !== "en" && !r.machine_translated ? `<span class="badge">${t("english_src")}</span>` : ""}
        <span>${Math.round(r.latency_ms || 0)} ms</span></div>
      ${title}<div class="answer-body">${md(displayAnswer(r.answer || ""))}</div>
      ${terms.length ? `<div class="terms">${terms.map(x => `<a class="seal" href="#/graph?center=${encodeURIComponent(x.canonical_term)}">${esc(x.canonical_term)}${x.matched_text && x.matched_text !== x.canonical_term ? ` <span class="alt">${esc(x.matched_text)}</span>` : ""}</a>`).join("")}</div>` : ""}
      ${!r.abstained || cits.length ? `<details class="fold"><summary>${t("sources")} (${cits.length})</summary>${renderSources(r)}</details>` : ""}
      <details class="fold"><summary>${t("how")}</summary>${renderTrace(r)}</details>
      <div class="actions"></div>`;
    const lead = $(".answer-body p", card); if (lead && !r.abstained) lead.classList.add("lead");
    const actions = $(".actions", card);
    actions.append(playerControls(() => r.answer, lang));
    const mk = (label, fn) => { const b = document.createElement("button"); b.className = "btn ghost"; b.textContent = label; b.onclick = () => fn(b); actions.append(b); };
    mk(t("copy"), async b => { try { await navigator.clipboard.writeText(r.answer); b.textContent = t("copied"); } catch { /* clipboard blocked */ } });
    mk(t("share"), async () => { const txt = `${r.raw_query}\n\n${r.answer}`; if (navigator.share) { try { await navigator.share({ text: txt }); } catch { /* cancelled */ } } else { try { await navigator.clipboard.writeText(txt); } catch { } } });
    ["up", "down"].forEach(rt => mk(rt === "up" ? "👍 " + t("helpful") : "👎 " + t("not_helpful"), async b => {
      try { await api("/api/feedback", { method: "POST", body: { rating: rt, mode: r.system_mode } }); b.textContent = t("thanks"); } catch { } }));
    slot.replaceWith(card); card.scrollIntoView({ block: "nearest", behavior: "smooth" });
    const ctl = $(".player", card);
    if (r.tts && r.tts.audio_base64 && r.tts.audio_base64.length) Player.playBase64(r.tts.audio_base64, ctl, onSpokenEnd);
    else if (r.is_emergency || $("#opt-autoplay").checked || r._fromVoice) Player.speak(r.answer, lang, ctl, onSpokenEnd);
  }
  function renderSources(r) {
    const cits = r.citations || [], passages = r.retrieved_passages || [];
    const local = cits.filter(c => !c.is_web), web = cits.filter(c => c.is_web);
    let h = local.map(c => `<div class="src"><span class="badge">${esc(c.source_id)}</span><span>${esc(c.title || "")} — ${esc(c.locator || "")} <code class="mono">${esc(c.chunk_id)}</code></span></div>`).join("");
    if (web.length) h += web.map(c => `<div class="src ext"><span class="badge">External</span><span><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.title)}</a> (${esc(c.publisher || "")} ${esc(c.year || "")})</span></div>`).join("");
    if (passages.length) h += `<details><summary class="muted" style="min-height:40px;display:flex;align-items:center;cursor:pointer">Retrieved passages (${passages.length})</summary>` +
      passages.map(p => `<blockquote style="margin:8px 0;padding-left:12px;border-left:3px solid var(--line)"><small><code class="mono">${esc(p.chunk_id)}</code> ${esc(p.source_id)} · ${esc(p.locator || "")}</small><br>${esc((p.text || "").slice(0, 420))}…</blockquote>`).join("") + "</details>";
    return h || `<p class="muted">No sources — the system did not answer.</p>`;
  }
  function renderTrace(r) {
    const b = r.backends || {}; const tm = r.translation_meta || {}; const ev = r.evidence_check || {};
    const rows = [
      ["Detected language", `${r.detected_language}${r.is_code_mixed ? ` (code-mixed: ${esc(r.code_mix_type)})` : ""}`],
      ["Segments", (r.segments || []).map(s => `${esc(s.text || s.segment || "")} <small>[${esc(s.lang || s.script || "")}]</small>`).join(" · ") || "—"],
      ["Protected terms", (r.detected_terms || []).map(x => `${esc(x.matched_text)} → ${esc(x.canonical_term)}`).join(", ") || "none"],
      ["Translation", `${esc(tm.method || "—")}${tm.translated_text ? `: <em>${esc(tm.translated_text)}</em>` : ""}${tm.warning ? `<br><small>${esc(tm.warning)}</small>` : ""}`],
      ["Canonical query", esc(r.canonical_query || "—")],
      ["Graph expansion", esc((r.graph_expansion_terms || []).join(", ") || "—")],
      ["Backends", `MT: ${esc(b.translator)}, dense: ${esc(b.dense_model || b.dense)}, writer: ${esc(r.generator_used || b.generator)}, graph: ${esc(b.kg_version)}`],
      ["Evidence check", ev.judgeable ? `coverage ${ev.coverage} (${esc((ev.matched || []).join(", "))})` : "—"],
      ["Abstention", r.abstained ? esc(r.abstention_reason) : "no"],
      ["Graph facts", (r.graph_facts || []).map(f => `${esc(f.concept)} — ${esc(f.relation)} — ${esc(f.target)} <small>(${esc(f.locator || "no locator")}; <span class="${f.review_status === "extracted_from_source" ? "" : "badge unrev"}">${esc((f.review_status || "").replace(/_/g, " "))}</span>)</small>`).join("<br>") || "—"],
      ["Latency", `${Math.round(r.latency_ms || 0)} ms`],
    ];
    return `<dl class="trace">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("")}</dl>`;
  }

  // ── voice input ────────────────────────────────────────────────────────────
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const Voice = {
    active: null, target: null, rec: null, media: null, chunks: [], t0: 0, timer: null, ctx: null, silentSince: 0, heard: false,
    langCode() { return { en: "en-IN", hi: "hi-IN", kn: "kn-IN", hinglish: "hi-IN" }[QL] || "en-IN"; },
    btn() { return this.target === "symptoms" ? $("#sym-mic") : $("#mic"); },
    input() { return this.target === "symptoms" ? $("#sym-q") : $("#q"); },
    toggle(target) { if (this.active) this.stop(); else this.start(target); },
    async start(target) {
      this.target = target; Player.stop();
      if (!window.isSecureContext) return this.fail(t("mic_insecure"));
      this._ui(true);
      if (SR && store.get("ayur.forceServerSTT", false) !== true) return this._webSpeech();
      if (!navigator.mediaDevices || !window.MediaRecorder) { this._ui(false); return this.fail(t("no_mic")); }
      try { this.media = await navigator.mediaDevices.getUserMedia({ audio: true }); }
      catch (e) { this._ui(false); return this.fail(e.name === "NotAllowedError" ? t("mic_denied") : t("no_mic")); }
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
        if (inp.value.trim()) {
          inp.focus();
          Voice._lastFromVoice = true;
          note(t("edit_transcript") || "Transcript ready. You can review or edit your question, then click Ask.");
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
      fd.append("lang_hint", QL === "hinglish" ? "hi" : QL);
      const isSym = this.target === "symptoms";
      try {
        const r = await api("/api/voice/transcribe", { method: "POST", form: fd });
        if (!r.ok) {
          return this.fail(r.message || "Speech recognition failed. Please try again or type your question.");
        }
        const inp = this.input();
        inp.value = r.text || r.raw_text || "";
        inp.focus();
        Voice._lastFromVoice = true;
        note(r.needs_confirmation ? t("low_conf") : (t("edit_transcript") || "Transcript ready. You can review or edit your question, then click Ask."));
      } catch (e) {
        this.fail(e.message);
      }
    },
    _ui(on) { const b = this.btn(); b.classList.toggle("rec", on); b.setAttribute("aria-pressed", String(on)); b.setAttribute("aria-label", on ? t("stop") : t("mic"));
      $("#rec-bar").hidden = !(on && this.target === "ask"); },
    fail(msg) { note(msg, true); }
  };
  function note(msg, isErr) { const d = document.createElement("div"); d.className = isErr ? "err" : "notice"; d.setAttribute("role", isErr ? "alert" : "status"); d.textContent = msg;
    const host = Voice.target === "symptoms" ? $("#sym-out") : $("#thread"); host.append(d); setTimeout(() => d.remove(), 9000); }
  $("#mic").addEventListener("click", () => Voice.toggle("ask"));
  $("#sym-mic").addEventListener("click", () => Voice.toggle("symptoms"));
  $("#rec-cancel").addEventListener("click", () => Voice.stop(true));
  document.addEventListener("keydown", e => { if (e.altKey && (e.key === "m" || e.key === "M")) { e.preventDefault(); Voice.toggle(location.hash.startsWith("#/symptoms") ? "symptoms" : "ask"); } });

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
  $("#sym-form").addEventListener("submit", async e => {
    e.preventDefault(); const text = $("#sym-q").value.trim(); if (!text) return; const out = $("#sym-out"); out.innerHTML = `<div class="skeleton"></div><div class="skeleton"></div>`;
    try {
      const r = await api("/api/symptoms", { method: "POST", key: "sym", body: { text, target_lang: $("#opt-lang").value } });
      if (r.reason === "emergency_symptom_detected") {
        out.innerHTML = `<article class="a emergency" role="alert"><h3>${t("emergency_title")}</h3><p>${esc(r.message)}</p><div class="actions"></div></article>`;
        const ctl = playerControls(() => r.message, (r.target_language || "en").slice(0, 2)); $(".actions", out).append(ctl);
        if (r.tts && r.tts.audio_base64?.length) Player.playBase64(r.tts.audio_base64, ctl); else Player.speak(r.message, (r.target_language || "en").slice(0, 2), ctl);
        return;
      }
      if (r.abstained) { out.innerHTML = `<article class="a abstain"><h3>${t("abstain_title")}</h3><p>${esc(r.message || "")}</p></article>`; return; }
      out.innerHTML = `<article class="a">${r.summary ? `<p class="lead" style="font-family:var(--serif);font-size:1.1rem">${esc(r.summary)}</p>` : ""}
        <ul class="edge-list">${(r.mappings || []).map(m => `<li><b>${esc(m.symptom_phrase)}</b> — conceptual tendency:
          <a class="seal" href="#/graph?center=${encodeURIComponent(m.associated_dosha)}">${esc(m.associated_dosha)}</a>
          <p style="margin:6px 0">${esc(m.educational_note || "")}</p><small>${esc(m.source_id || "")} ${esc(m.locator || "")}</small>
          <span class="badge unrev">${t("unreviewed")}</span><br><small class="muted">${esc(m.locator_review_status || "")}</small></li>`).join("")}</ul>
        <p class="muted" style="margin-top:10px">${esc(r.disclaimer || "")}</p></article>`;
    } catch (e2) { if (e2.name !== "AbortError") out.innerHTML = `<div class="err">${esc(e2.message)}</div>`; }
  });

  // ── herbs ──────────────────────────────────────────────────────────────────
  function initHerbs() {
    const run = debounce(async () => { const v = $("#herb-q").value.trim() || "ashwagandha";
      try { const r = await api("/api/herbs/search", { key: "herbs", params: { q: v, limit: 18 } });
        $("#herb-results").innerHTML = r.results.length ? r.results.map(h => `<button class="herb" data-id="${esc(h.id)}"><i>${esc(h.botanical_name)}</i><br>
          ${h.api_names.length ? `<span class="seal" style="margin:6px 0">${esc(h.api_names[0].replace(/_\d+$/, ""))}${h.label_sa_deva ? ` <span class="alt">${esc(h.label_sa_deva)}</span>` : ""}</span><br>` : ""}
          <small>${esc(h.family || "")} · ${h.n_recorded_uses} recorded uses · ${h.n_formulations} formulations</small></button>`).join("")
          : `<div class="empty">No herb matches “${esc(v)}”. Try a botanical or Sanskrit name.</div>`;
      } catch (e) { if (e.name !== "AbortError") $("#herb-results").innerHTML = `<div class="err">${esc(e.message)}</div>`; } }, 220);
    $("#herb-q").addEventListener("input", run); run();
    $("#herb-results").addEventListener("click", e => { const b = e.target.closest("[data-id]"); if (b) showHerb(b.dataset.id); });
    api("/api/lifestyle").then(r => { $("#topics").innerHTML = r.topics.map(x => `<button class="chip-btn" data-k="${x.key}">${esc(x["title_" + UI] || x.title_en)}</button>`).join(""); }).catch(() => {});
    $("#topics").addEventListener("click", async e => { const b = e.target.closest("[data-k]"); if (!b) return;
      $$("#topics [data-k]").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
      const out = $("#topic-out"); out.innerHTML = `<div class="skeleton"></div>`;
      try { const r = await api("/api/lifestyle/" + b.dataset.k);
        out.innerHTML = `<p class="muted">${esc(r.note)}</p>` + (r.who_terms.length ? `<h3>WHO terminology</h3><ul class="edge-list">${r.who_terms.map(w => `<li><b>${esc(w.term)}</b> ${w.iast ? `<span class="seal">${esc(w.iast)}</span>` : ""}<p style="margin:4px 0">${esc(w.definition || "")}</p><small>${esc(w.locator)}</small></li>`).join("")}</ul>` : "") +
          `<h3 style="margin-top:14px">Passages from the corpus</h3>` + r.passages.map(p => `<blockquote style="margin:10px 0;padding-left:12px;border-left:3px solid var(--line)"><small>${esc(p.source_id)} · ${esc(p.locator || "")} <code class="mono">${esc(p.chunk_id)}</code></small><br>${esc(p.text)}…</blockquote>`).join("");
      } catch (e2) { out.innerHTML = `<div class="err">${esc(e2.message)}</div>`; } });
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
      const [res, probe] = await Promise.all([api("/api/research/results"), api("/api/research/probe")]);
      const v2 = res.v2; let h = "";
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
      h += `<div class="panel" style="margin-top:12px"><h3>Downloads</h3><ul>${(res.files || []).map(f => `<li><a href="/api/research/files/${encodeURIComponent(f)}" download>${esc(f)}</a></li>`).join("") || "<li>None yet</li>"}</ul>
        <p class="muted">The original <code class="mono">experiment_results_v1.json</code> is kept unchanged for comparison; its metric definitions are documented as flawed in docs/AUDIT.md (F17, F18).</p></div>`;
      out.innerHTML = h;
    } catch (e) { out.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  }

  // ── about ──────────────────────────────────────────────────────────────────
  const ARCH = `<svg viewBox="0 0 900 300" role="img" aria-label="Pipeline: question or voice, language detection, term detection and protection, translation, hybrid retrieval, optional graph, evidence-grounded answer, restoration and speech">
    ${[["Question / voice", "STT · language ID"], ["Term detection", "NAMASTE · WHO · suffixes"], ["Protect & translate", "IndicTrans2 or rules"], ["Hybrid retrieval", "BM25 + dense · RRF k=60"],
       ["Graph grounding", "P2 only · provenance"], ["Grounded answer", "citations or abstain"], ["Restore & speak", "native script · TTS"]].map(([a, b], i) => {
      const x = 10 + (i % 4) * 222, y = i < 4 ? 30 : 170;
      return `<rect x="${x}" y="${y}" width="200" height="90" rx="12" fill="var(--surface)" stroke="${i === 1 || i === 2 ? "var(--turmeric)" : "var(--line)"}" stroke-width="${i === 1 || i === 2 ? 2 : 1}"/>
        <text x="${x + 16}" y="${y + 40}" style="font-family:var(--serif);font-size:16px">${a}</text><text x="${x + 16}" y="${y + 64}" style="fill:var(--ink-3)">${b}</text>`; }).join("")}
    <path d="M210 75h22M432 75h22M654 75h22M876 75v20H120v55M210 215h22M432 215h22" fill="none" stroke="var(--ink-3)" stroke-width="1.5" marker-end="url(#ar)"/>
    <defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="var(--ink-3)"/></marker></defs>
    <rect x="676" y="170" width="200" height="90" rx="12" fill="var(--calm-wash)" stroke="var(--calm)"/><text x="692" y="210" style="font-family:var(--serif);font-size:16px">Safety gate</text><text x="692" y="234" style="fill:var(--ink-3)">emergency · dose · cure claims</text></svg>`;
  async function initAbout() {
    const out = $("#about-out");
    try {
      const a = await api("/api/about");
      out.innerHTML = `<div class="panel arch"><h2>How AyurMitra works</h2>${ARCH}<p class="muted">The safety gate runs before retrieval in every configuration. Terms highlighted in turmeric are protected through translation and restored afterwards.</p></div>
        <div class="panel" style="margin-top:14px"><h2>Safety</h2><p>${esc(a.disclaimer)}</p><ul><li>No doses, prescriptions or diagnoses — those questions are declined.</li>
        <li>Sudden or severe symptoms get an emergency referral, which is also read aloud.</li><li>Answers quote retrieved passages; when evidence is missing, AyurMitra says so instead of guessing.</li>
        <li>Recorded traditional uses are not proof that anything is effective or safe.</li></ul></div>
        <div class="panel" style="margin-top:14px"><h2>Data sources and licences</h2><div class="table-wrap"><table><thead><tr><th>Source</th><th>Licence / status</th></tr></thead><tbody>${Object.entries(a.licences).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("")}</tbody></table></div>
        <p class="muted">Entries marked "to be verified" have not been cleared for redistribution. This site does not claim redistribution rights.</p></div>
        <div class="panel" style="margin-top:14px"><h2>Privacy</h2><p>${esc(a.privacy)}</p><p class="muted">Voice recordings are converted to text on the server and are not kept. In Chrome and Edge, in-browser recognition is handled by the browser vendor's speech service.</p></div>
        <div class="panel" style="margin-top:14px"><h2>Team</h2><p>${a.team.members.map(esc).join(", ")}<br>Guide: ${esc(a.team.guide)} · ${esc(a.team.institution)} (${esc(a.team.team)})</p>
        <p class="muted">Hindi and Kannada interface text is project-written and awaiting native-speaker review.</p></div>`;
    } catch (e) { out.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
  }

  // ── boot ───────────────────────────────────────────────────────────────────
  window.AyurMitra = { ask, Voice, Player };
  applyI18n(); route(); loadHealth(); setInterval(loadHealth, 60000);
})();
