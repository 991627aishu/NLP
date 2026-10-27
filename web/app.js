/**
 * AyurMitra — Interactive Frontend Logic
 * Supports multilingual query analysis, citation anchoring, XAI rendering,
 * and live dataset/graph status.
 */

// DOM Elements
const queryBox = document.getElementById('query');
const searchButton = document.getElementById('search-button');
const responsePanel = document.getElementById('response');
const errorBox = document.getElementById('input-error');
const languageHint = document.getElementById('language-hint');
const emergencyBanner = document.getElementById('emergency-banner');
const emergencyText = document.getElementById('emergency-text');
const clarificationBanner = document.getElementById('clarification-banner');
const clarificationText = document.getElementById('clarification-text');

let selectedCategory = 'general';

const categoryPrompts = {
    general: ['Ask a general Ayurveda question', 'Try: What does Agni mean in Ayurveda?'],
    herbs: ['Search for an Ayurvedic herb or botanical use', 'Try: Tulsi traditional uses / Withania somnifera'],
    disease: ['Explore symptoms or conditions in the sources', 'Try: fever and cough / Explore evidence for digestion']
};

// Initialize Category Tabs
document.querySelectorAll('.category-card').forEach(btn => {
    btn.addEventListener('click', () => {
        selectedCategory = btn.dataset.category;
        document.querySelectorAll('.category-card').forEach(b => {
            b.classList.toggle('active', b === btn);
            b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
        });
        const promptLabel = document.getElementById('query-label');
        if (promptLabel) promptLabel.textContent = categoryPrompts[selectedCategory][0];
        if (queryBox) queryBox.placeholder = categoryPrompts[selectedCategory][1];
    });
});

// Example Chips Handler
document.querySelectorAll('.chip-btn').forEach(chip => {
    chip.addEventListener('click', () => {
        const query = chip.dataset.query;
        const cat = chip.dataset.cat;
        if (cat) {
            const targetTab = document.getElementById(`tab-${cat}`);
            if (targetTab) targetTab.click();
        }
        if (queryBox) {
            queryBox.value = query;
            detectScriptAndLang(query);
            runSearch();
        }
    });
});

// HTML Escape Utility
function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
    }[c]));
}

// Script & Language Detection on Keyup
function detectScriptAndLang(text) {
    if (!languageHint) return;
    if (/[\u0C80-\u0CFF]/.test(text)) {
        languageHint.textContent = 'Kannada script detected (ಕನ್ನಡ) · Multilingual pipeline active';
        return;
    }
    if (/[\u0900-\u097F]/.test(text)) {
        languageHint.textContent = 'Devanagari script detected (हिन्दी / संस्कृत) · Multilingual pipeline active';
        return;
    }
    if (/[\u0C00-\u0C7F]/.test(text)) {
        languageHint.textContent = 'Telugu script detected (తెలుగు) · Multilingual pipeline active';
        return;
    }
    const low = ' ' + text.toLowerCase().replace(/[^a-z ]/g, ' ') + ' ';
    const kannada_hints = ['enu', 'alla', 'hege', 'nanna', 'beku', 'yenu', 'aagide', 'thumba', 'mathu', 'roga', 'sari', 'thale', 'novu', 'nanage', 'nange', 'yake', 'illa', 'agutte', 'aaytu', 'kemmu', 'hotte', 'inda', 'upayoga', 'upayogagalu'];
    const hindi_hints = ['kya', 'hai', 'hain', 'mujhe', 'mera', 'meri', 'kaise', 'bukhar', 'dard', 'pet', 'chahiye', 'kyun', 'fayde', 'fayda', 'labh', 'khansi', 'upayog', 'upyog', 'ke', 'ki', 'ka', 'hote'];
    const telugu_hints = ['upayogalu', 'upayogam', 'prayojanam', 'emiti', 'yemiti', 'ela', 'gurinchi', 'naaku', 'naku', 'undi', 'unnadi', 'daggu', 'jwaram', 'mandulu', 'aushadham', 'cheyali', 'kavali', 'enti', 'gunde', 'noppi', 'vepa'];
    const words = new Set(low.split(/\s+/));
    
    let kHits = 0;
    kannada_hints.forEach(w => { if (words.has(w)) kHits++; });
    if (kHits >= 1) {
        languageHint.textContent = 'Possible Romanized Kannada (Kanglish) detected · Concept normalization active';
        return;
    }

    let tHits = 0;
    telugu_hints.forEach(w => { if (words.has(w)) tHits++; });
    if (tHits >= 1) {
        languageHint.textContent = 'Possible Romanized Telugu detected · Concept normalization active';
        return;
    }

    let hHits = 0;
    hindi_hints.forEach(w => { if (words.has(w)) hHits++; });
    if (hHits >= 1) {
        languageHint.textContent = 'Possible Romanized Hindi (Hinglish) detected · Concept normalization active';
        return;
    }

    languageHint.textContent = 'English or Latin-script input · Concept normalization & script detection active';
}

if (queryBox) {
    queryBox.addEventListener('input', () => detectScriptAndLang(queryBox.value));
    queryBox.addEventListener('keydown', e => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') runSearch();
    });
}

if (searchButton) {
    searchButton.addEventListener('click', runSearch);
}

// Highlight Citation in Evidence Records
function highlightCitation(evidenceId) {
    const targetCard = document.getElementById(`evidence-card-${evidenceId}`);
    if (targetCard) {
        targetCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
        targetCard.classList.add('highlighted');
        targetCard.open = true;
        setTimeout(() => targetCard.classList.remove('highlighted'), 2000);
    }
}

// Format Answer with Interactive Clickable Citation Badges
function formatAnswerWithCitations(text) {
    if (!text) return '';
    const escaped = escapeHtml(text);
    return escaped.replace(/\[E(\d+)\]/g, (match, num) => {
        return `<span class="citation-pill" onclick="highlightCitation('${num}')" title="Inspect supporting record E${num}">[E${num}]</span>`;
    });
}

// Render Retrieved Evidence Records
function renderResults(data) {
    const holder = document.getElementById('results');
    const recordsCount = document.getElementById('records-count');
    if (!holder) return;
    holder.innerHTML = '';

    const sections = data.sections || [];
    let totalItems = 0;
    let evidenceIndex = 1;

    sections.forEach(section => {
        const sectionHeader = document.createElement('h3');
        sectionHeader.style.fontSize = '1.05rem';
        sectionHeader.style.color = 'var(--text-muted)';
        sectionHeader.style.margin = '1.25rem 0 0.5rem';
        sectionHeader.textContent = section.title;
        holder.appendChild(sectionHeader);

        (section.items || []).forEach(item => {
            totalItems++;
            const card = document.createElement('details');
            card.className = 'evidence-card';
            card.id = `evidence-card-${evidenceIndex}`;

            const summary = document.createElement('summary');
            summary.className = 'evidence-summary';
            summary.innerHTML = `
                <div class="evidence-title-group">
                    <span class="evidence-id-pill">E${evidenceIndex}</span>
                    <span>${escapeHtml(item.title)}</span>
                </div>
                <span style="font-size: 0.8rem; color: var(--text-dim);">${escapeHtml(item.detail || '')}</span>
            `;

            const body = document.createElement('div');
            body.className = 'evidence-body';
            body.innerHTML = `
                <p>${escapeHtml(item.summary || '')}</p>
                <div class="evidence-detail-meta">${escapeHtml(item.detail || '')}</div>
                <a class="evidence-source-link" href="${escapeHtml(item.source?.url || '#')}" target="_blank" rel="noopener">
                    Source: ${escapeHtml(item.source?.name || 'Reference Repository')} ↗
                </a>
            `;

            card.appendChild(summary);
            card.appendChild(body);
            holder.appendChild(card);
            evidenceIndex++;
        });
    });

    if (recordsCount) {
        recordsCount.textContent = `${totalItems} evidence passage(s) retrieved`;
    }
}

// Render Explainable AI (XAI) Panel
function renderXAI(data) {
    const panel = document.getElementById('xai-panel');
    const container = document.getElementById('xai-cards-container');
    const mlCard = document.getElementById('ml-classifier-card');
    const mlList = document.getElementById('ml-predictions-list');
    const mlStatus = document.getElementById('ml-abstain-status');

    if (!panel || !container) return;

    if (!data.xai_data || data.xai_data.length === 0) {
        panel.hidden = true;
        return;
    }

    panel.hidden = false;
    container.innerHTML = '';

    // Render ML Classifier comparison if present
    if (data.ml_classification && mlCard && mlList) {
        mlCard.hidden = false;
        const ml = data.ml_classification;
        if (ml.abstain) {
            mlStatus.textContent = 'Abstained (Low Confidence)';
            mlStatus.style.background = 'rgba(239, 68, 68, 0.2)';
            mlStatus.style.color = '#fca5a5';
            mlList.innerHTML = `<span style="font-size:0.85rem; color:var(--text-muted);">${escapeHtml(ml.reason || 'Model abstained.')}</span>`;
        } else {
            mlStatus.textContent = `Model Active (${(ml.max_confidence * 100).toFixed(1)}%)`;
            mlStatus.style.background = 'rgba(16, 185, 129, 0.2)';
            mlStatus.style.color = 'var(--primary-400)';
            mlList.innerHTML = (ml.predictions || []).slice(0, 3).map(p => `
                <div class="ml-pred-pill">
                    <span>${escapeHtml(p.condition)}</span>
                    <span class="ml-prob">${p.probability_pct}</span>
                </div>
            `).join('');
        }
    } else if (mlCard) {
        mlCard.hidden = true;
    }

    data.xai_data.forEach(item => {
        const card = document.createElement('div');
        card.className = 'xai-card';

        const symptomTags = (item.matched_symptoms || []).map(s => 
            `<span class="xai-symptom-tag">${escapeHtml(s)}</span>`
        ).join('');

        const coverageVal = item.coverage_pct || 'N/A';
        const numVal = parseFloat(coverageVal) || 50;

        card.innerHTML = `
            <div class="xai-header">
                <span class="xai-condition-name">${escapeHtml(item.condition)}</span>
                <span class="xai-score-badge">Score: ${item.score} [${item.evidence_id}]</span>
            </div>
            <div class="xai-coverage-bar-wrapper">
                <span>Coverage: ${coverageVal}</span>
                <div class="xai-progress-track">
                    <div class="xai-progress-fill" style="width: ${Math.min(numVal, 100)}%;"></div>
                </div>
            </div>
            <div class="xai-symptoms-tags">
                <span style="font-size:0.75rem; color:var(--text-dim);">Matched:</span>
                ${symptomTags || '<span style="font-size:0.75rem; color:var(--text-dim);">None</span>'}
            </div>
            <div class="xai-explanation-text">${escapeHtml(item.explanation || 'Rule-based text association rank from Columbia clinical KB.')}</div>
        `;
        container.appendChild(card);
    });
}

// Render Knowledge Graph Context Panel
function renderKGContext(kgEntities) {
    const panel = document.getElementById('kg-context-panel');
    const container = document.getElementById('kg-entities-container');
    if (!panel || !container) return;

    if (!kgEntities || kgEntities.length === 0) {
        panel.hidden = true;
        return;
    }

    panel.hidden = false;
    container.innerHTML = '';

    kgEntities.forEach(ent => {
        const card = document.createElement('div');
        card.className = 'kg-entity-card';

        const relationsHtml = (ent.relations || []).slice(0, 3).map(r => `
            <div class="kg-rel-item">
                <span class="kg-rel-arrow">${r.direction === 'out' ? '➔' : '⬅'}</span>
                <span>${escapeHtml(r.relation.replace(/_/g, ' '))}: <strong>${escapeHtml(r.target_label || r.source_label || '')}</strong></span>
            </div>
        `).join('');

        card.innerHTML = `
            <div class="kg-entity-header">
                <span class="kg-entity-label">${escapeHtml(ent.label)}</span>
                <span class="kg-entity-kind">${escapeHtml(ent.kind.replace(/_/g, ' '))}</span>
            </div>
            <div class="kg-relations-list">${relationsHtml || '<span style="font-size:0.75rem; color:var(--text-dim);">No direct connections</span>'}</div>
        `;
        container.appendChild(card);
    });
}

// Render Sources Used Catalog
function renderSources(sources) {
    const holder = document.getElementById('source-list');
    if (!holder) return;
    holder.innerHTML = '';
    (sources || []).forEach(src => {
        const item = document.createElement('div');
        item.className = 'source-catalog-card';
        item.innerHTML = `
            <a href="${escapeHtml(src.url)}" target="_blank" rel="noopener">${escapeHtml(src.name)} ↗</a>
            <p>${escapeHtml(src.detail || '')}</p>
        `;
        holder.appendChild(item);
    });
}

// Main Search Execution
async function runSearch() {
    const query = (queryBox ? queryBox.value : '').trim();
    const mode = document.getElementById('answer-mode') ? document.getElementById('answer-mode').value : 'extractive';

    if (errorBox) errorBox.hidden = true;
    if (emergencyBanner) emergencyBanner.hidden = true;
    if (clarificationBanner) clarificationBanner.hidden = true;

    if (!query) {
        if (errorBox) {
            errorBox.textContent = 'Please enter a search query or click an example chip.';
            errorBox.hidden = false;
        }
        return;
    }

    if (searchButton) {
        searchButton.disabled = true;
        searchButton.querySelector('.btn-text').textContent = 'Retrieving Evidence…';
    }

    try {
        const res = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, category: selectedCategory, answer_mode: mode })
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Search request failed.');

        if (responsePanel) responsePanel.hidden = false;

        // Populate Badges & Summary
        const catBadge = document.getElementById('answer-category-badge');
        const langBadge = document.getElementById('result-language-badge');
        const modeBadge = document.getElementById('answer-mode-badge');
        const summaryText = document.getElementById('summary-text');

        if (catBadge) catBadge.textContent = data.category_label || 'GENERAL AYURVEDA';
        if (langBadge) langBadge.textContent = data.answer_language || 'English';
        if (modeBadge) modeBadge.textContent = data.answer_mode || 'Grounded Extractive';
        if (summaryText) summaryText.textContent = data.summary || '';

        // Emergency Triage
        if (data.emergency_warning && emergencyBanner && emergencyText) {
            emergencyText.textContent = data.emergency_warning;
            emergencyBanner.hidden = false;
        }

        // Clarification prompt
        if (data.clarification_needed && clarificationBanner && clarificationText) {
            clarificationText.textContent = data.clarification_needed;
            clarificationBanner.hidden = false;
        }

        // Answer Prose with Clickable Citations
        const answerBox = document.getElementById('answer');
        if (answerBox) {
            answerBox.innerHTML = formatAnswerWithCitations(data.answer);
        }

        // Recognized Entities
        const entitiesBar = document.getElementById('detected-entities-bar');
        const entitiesContainer = document.getElementById('entities-tags');
        if (entitiesBar && entitiesContainer && data.detected_entities) {
            const ent = data.detected_entities;
            const allEnts = [...(ent.herbs || []), ...(ent.concepts || []), ...(ent.symptoms || [])];
            if (allEnts.length > 0) {
                entitiesBar.hidden = false;
                entitiesContainer.innerHTML = allEnts.map(e => `<span class="entity-tag">${escapeHtml(e)}</span>`).join('');
            } else {
                entitiesBar.hidden = true;
            }
        }

        // Limitations List
        const limitsBox = document.getElementById('limitations');
        if (limitsBox) {
            limitsBox.innerHTML = data.limitations?.length
                ? `<ul>${data.limitations.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>`
                : '<p>No specific limitations noted for this record.</p>';
        }

        // Render Results, XAI, and KG
        renderResults(data);
        renderXAI(data);
        renderKGContext(data.knowledge_graph_entities);
        renderSources(data.sources || []);

        if (responsePanel) {
            responsePanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    } catch (err) {
        if (errorBox) {
            errorBox.textContent = err.message;
            errorBox.hidden = false;
        }
    } finally {
        if (searchButton) {
            searchButton.disabled = false;
            searchButton.querySelector('.btn-text').textContent = 'Search Sources';
        }
    }
}

// Fetch System Status & KG Stats on page load
async function loadSystemMetadata() {
    try {
        const kgRes = await fetch('/api/knowledge-graph');
        if (kgRes.ok) {
            const kg = await kgRes.json();
            const nodesEl = document.getElementById('kg-nodes-count');
            const edgesEl = document.getElementById('kg-edges-count');
            if (nodesEl && kg.nodes) nodesEl.textContent = Number(kg.nodes).toLocaleString();
            if (edgesEl && kg.edges) edgesEl.textContent = Number(kg.edges).toLocaleString();
        }
    } catch (e) {
        // Fallback default stats are already present in HTML
    }
}

// Run on page load
document.addEventListener('DOMContentLoaded', () => {
    loadSystemMetadata();
});