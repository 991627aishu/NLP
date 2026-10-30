// Minimal dependency-free force-directed graph on <canvas> (≤ 300 nodes).
(function () {
  const TYPE_COLORS = {
    Dosha: "#B8860B", Concept: "#4F6F52", WHOTerm: "#2F6F8F", WHOSection: "#7FA3B5", NAMASTETerm: "#6B5B95",
    Plant: "#3E8E5A", Formulation: "#8A5A44", TherapeuticUse: "#9AA39C", SymptomPhrase: "#34477A",
  };
  window.KG_TYPE_COLORS = TYPE_COLORS;

  class ForceGraph {
    constructor(canvas, opts = {}) {
      this.c = canvas; this.ctx = canvas.getContext("2d"); this.opts = opts;
      this.nodes = []; this.edges = []; this.byId = {}; this.selected = null; this.hover = null; this.highlight = new Set();
      this.view = { x: 0, y: 0, k: 1 }; this.alpha = 0; this.raf = null;
      this.reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      this._bind(); this._resize(); new ResizeObserver(() => this._resize()).observe(canvas.parentElement);
    }
    _resize() {
      const r = this.c.parentElement.getBoundingClientRect(), d = window.devicePixelRatio || 1;
      this.w = r.width; this.h = r.height; this.c.width = r.width * d; this.c.height = r.height * d;
      this.ctx.setTransform(d, 0, 0, d, 0, 0); this.draw();
    }
    setData(nodes, edges, center) {
      const prev = this.byId; this.byId = {};
      this.nodes = nodes.map((n, i) => {
        const p = prev[n.id]; const a = (i / Math.max(1, nodes.length)) * Math.PI * 2, rad = 40 + 30 * (n.hop || 1);
        const o = Object.assign({}, n, { x: p ? p.x : Math.cos(a) * rad, y: p ? p.y : Math.sin(a) * rad, vx: 0, vy: 0 });
        if (n.id === center) { o.x = 0; o.y = 0; o.fixed = true; }
        this.byId[n.id] = o; return o;
      });
      this.edges = edges.filter(e => this.byId[e.source] && this.byId[e.target]);
      this.center = center; this.highlight = new Set(); this.alpha = 1;
      if (this.reduce) { for (let i = 0; i < 300; i++) this._tick(); this.alpha = 0; this.fit(); }
      else { this._run(); setTimeout(() => this.fit(), 650); }
    }
    _run() { if (this.raf) return; const step = () => { this._tick(); this.draw(); if (this.alpha > 0.02) this.raf = requestAnimationFrame(step); else this.raf = null; }; this.raf = requestAnimationFrame(step); }
    _tick() {
      const N = this.nodes, a = this.alpha;
      for (let i = 0; i < N.length; i++) for (let j = i + 1; j < N.length; j++) {
        const p = N[i], q = N[j]; let dx = q.x - p.x, dy = q.y - p.y; let d2 = dx * dx + dy * dy || 0.01;
        if (d2 > 90000) continue; const f = 900 / d2 * a; const d = Math.sqrt(d2); dx /= d; dy /= d;
        p.vx -= dx * f; p.vy -= dy * f; q.vx += dx * f; q.vy += dy * f;
      }
      for (const e of this.edges) {
        const s = this.byId[e.source], t = this.byId[e.target]; const dx = t.x - s.x, dy = t.y - s.y, d = Math.sqrt(dx * dx + dy * dy) || 1;
        const k = (d - 70) * 0.04 * a; s.vx += dx / d * k; s.vy += dy / d * k; t.vx -= dx / d * k; t.vy -= dy / d * k;
      }
      for (const n of N) { n.vx -= n.x * 0.004 * a; n.vy -= n.y * 0.004 * a; if (!n.fixed && n !== this.drag) { n.x += n.vx; n.y += n.vy; } n.vx *= 0.6; n.vy *= 0.6; }
      this.alpha *= 0.985;
    }
    _toScreen(n) { return [n.x * this.view.k + this.view.x + this.w / 2, n.y * this.view.k + this.view.y + this.h / 2]; }
    _toWorld(px, py) { return [(px - this.w / 2 - this.view.x) / this.view.k, (py - this.h / 2 - this.view.y) / this.view.k]; }
    _css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
    draw() {
      const ctx = this.ctx; if (!this.w) return; ctx.clearRect(0, 0, this.w, this.h);
      const ink = this._css("--ink"), line = this._css("--line"), clay = this._css("--clay"), focus = this._css("--focus");
      ctx.lineWidth = 1;
      for (const e of this.edges) {
        const s = this.byId[e.source], t = this.byId[e.target]; const [x1, y1] = this._toScreen(s), [x2, y2] = this._toScreen(t);
        const hl = this.highlight.has(e.source + "|" + e.target) || this.highlight.has(e.target + "|" + e.source);
        const sel = this.selected && (e.source === this.selected.id || e.target === this.selected.id);
        ctx.strokeStyle = hl ? focus : e.verified ? (sel ? ink : line) : clay; ctx.globalAlpha = hl || sel ? 1 : 0.75;
        ctx.lineWidth = hl ? 3 : sel ? 1.6 : 1; ctx.setLineDash(e.verified ? [] : [4, 3]);
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      }
      ctx.setLineDash([]); ctx.globalAlpha = 1;
      const showLabels = this.view.k > 0.7 || this.nodes.length < 60;
      for (const n of this.nodes) {
        const [x, y] = this._toScreen(n); const r = (n.id === this.center ? 9 : 5 + Math.min(4, Math.log2(1 + (n.degree || 1)) / 2)) * Math.max(0.7, Math.min(1.4, this.view.k));
        ctx.fillStyle = TYPE_COLORS[n.node_type] || "#888"; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
        if (n === this.selected || n === this.hover || this.highlight.has(n.id)) { ctx.strokeStyle = focus; ctx.lineWidth = 2.5; ctx.stroke(); }
        if (showLabels || n === this.hover || n === this.selected || n.id === this.center) {
          ctx.fillStyle = ink; ctx.font = (n.id === this.center ? "600 " : "") + "12px " + this._css("--sans");
          const lab = (n.label_en || n.id).slice(0, 34); ctx.fillText(lab, x + r + 4, y + 4);
        }
      }
    }
    fit() {
      if (!this.nodes.length) return; let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const n of this.nodes) { x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y); x1 = Math.max(x1, n.x); y1 = Math.max(y1, n.y); }
      const k = Math.min(2, 0.85 * Math.min(this.w / (x1 - x0 + 120), this.h / (y1 - y0 + 60)));
      this.view = { k, x: -((x0 + x1) / 2) * k, y: -((y0 + y1) / 2) * k }; this.draw();
    }
    reset() { this.view = { x: 0, y: 0, k: 1 }; this.selected = null; this.highlight = new Set(); this.draw(); }
    select(id) { this.selected = this.byId[id] || null; this.draw(); }
    highlightPath(nodeIds) {
      this.highlight = new Set(nodeIds); for (let i = 0; i + 1 < nodeIds.length; i++) this.highlight.add(nodeIds[i] + "|" + nodeIds[i + 1]); this.draw();
    }
    _hit(px, py) { let best = null, bd = 196; for (const n of this.nodes) { const [x, y] = this._toScreen(n); const d = (x - px) ** 2 + (y - py) ** 2; if (d < bd) { bd = d; best = n; } } return best; }
    _bind() {
      const c = this.c; let panning = null, moved = false; const pts = new Map();
      c.addEventListener("pointerdown", e => {
        c.setPointerCapture(e.pointerId); pts.set(e.pointerId, [e.offsetX, e.offsetY]); moved = false;
        const n = this._hit(e.offsetX, e.offsetY); if (n) { this.drag = n; } else panning = [e.offsetX - this.view.x, e.offsetY - this.view.y];
      });
      c.addEventListener("pointermove", e => {
        const prev = pts.get(e.pointerId);
        if (pts.size === 2 && prev) { // pinch zoom
          const other = [...pts.entries()].find(([k]) => k !== e.pointerId)[1];
          const d0 = Math.hypot(prev[0] - other[0], prev[1] - other[1]), d1 = Math.hypot(e.offsetX - other[0], e.offsetY - other[1]);
          if (d0 > 0) { this.view.k = Math.max(0.2, Math.min(4, this.view.k * d1 / d0)); this.draw(); }
          pts.set(e.pointerId, [e.offsetX, e.offsetY]); return;
        }
        if (prev) pts.set(e.pointerId, [e.offsetX, e.offsetY]);
        if (this.drag) { const [wx, wy] = this._toWorld(e.offsetX, e.offsetY); this.drag.x = wx; this.drag.y = wy; moved = true; this.draw(); }
        else if (panning) { this.view.x = e.offsetX - panning[0]; this.view.y = e.offsetY - panning[1]; moved = true; this.draw(); }
        else { const h = this._hit(e.offsetX, e.offsetY); if (h !== this.hover) { this.hover = h; c.style.cursor = h ? "pointer" : "grab"; this.draw(); } }
      });
      const up = e => {
        pts.delete(e.pointerId);
        if (this.drag && !moved) { this.selected = this.drag; this.opts.onSelect && this.opts.onSelect(this.drag.id); }
        this.drag = null; panning = null; this.draw();
      };
      c.addEventListener("pointerup", up); c.addEventListener("pointercancel", up);
      c.addEventListener("wheel", e => {
        e.preventDefault(); const f = Math.exp(-e.deltaY * 0.0015), k = Math.max(0.2, Math.min(4, this.view.k * f));
        const mx = e.offsetX - this.w / 2, my = e.offsetY - this.h / 2;
        this.view.x = mx - (mx - this.view.x) * k / this.view.k; this.view.y = my - (my - this.view.y) * k / this.view.k; this.view.k = k; this.draw();
      }, { passive: false });
    }
    toPNG() {
      const tmp = document.createElement("canvas"); tmp.width = this.c.width; tmp.height = this.c.height; const t = tmp.getContext("2d");
      t.fillStyle = this._css("--surface") || "#fff"; t.fillRect(0, 0, tmp.width, tmp.height); t.drawImage(this.c, 0, 0); return tmp.toDataURL("image/png");
    }
  }
  window.ForceGraph = ForceGraph;
})();
