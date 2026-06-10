let papersData = null;
let liveSotaData = null;
let feedbackData = null;
let currentFilter = 'all';
let currentSort = 'stars';

async function loadData() {
    const [papersRes, sotaRes, feedbackRes] = await Promise.all([
        fetch('data/papers.json'),
        fetch('data/sota.json').catch(() => null),
        fetch('data/feedback.json').catch(() => null)
    ]);
    papersData = await papersRes.json();
    liveSotaData = sotaRes && sotaRes.ok ? await sotaRes.json() : null;
    feedbackData = feedbackRes && feedbackRes.ok ? await feedbackRes.json() : null;
    renderAll();
    restoreHashPosition();
}

function restoreHashPosition() {
    if (!window.location.hash) return;
    const target = document.querySelector(window.location.hash);
    if (!target) return;
    requestAnimationFrame(() => {
        target.scrollIntoView({ block: 'start' });
    });
    window.setTimeout(() => {
        target.scrollIntoView({ block: 'start' });
    }, 350);
}

function renderAll() {
    renderStats();
    renderTaxonomy();
    renderTimeline();
    renderSOTA();
    renderFeedback();
    renderPapers();
    renderDatasets();
    renderReadingList();
    renderTrendChart();
    renderLeaderboard();
    renderActivity();
}

function renderStats() {
    const papers = papersData.papers;
    const stats = {
        papers: papers.length,
        stars: papers.reduce((a, b) => a + b.stars, 0)
    };
    
    document.getElementById('stat-papers').textContent = stats.papers;
    document.getElementById('stat-stars').textContent = (stats.stars / 1000).toFixed(1) + 'K';
}

function renderPapers() {
    let papers = [...papersData.papers];
    
    // Filter
    if (currentFilter !== 'all') {
        papers = papers.filter(p => p.category === currentFilter || p.tags.includes(currentFilter));
    }
    
    // Search
    const search = document.getElementById('searchInput').value.toLowerCase();
    if (search) {
        papers = papers.filter(p => 
            p.title.toLowerCase().includes(search) ||
            p.authors.toLowerCase().includes(search) ||
            p.tags.some(t => t.toLowerCase().includes(search))
        );
    }
    
    // Sort
    papers.sort((a, b) => b[currentSort] - a[currentSort]);
    
    const container = document.getElementById('papersContainer');
    document.getElementById('paperCount').textContent = `${papers.length} papers`;
    container.innerHTML = papers.map(p => `
        <div class="paper-card" data-id="${p.id}">
            <div class="paper-header">
                <div class="paper-title">${p.title}</div>
                <span class="paper-year">${p.year}</span>
            </div>
            <div class="paper-authors">${p.authors}</div>
            <div class="paper-meta">
                <span class="paper-venue">${p.venue}</span>
                ${p.stars ? `<span class="paper-stars">${p.stars >= 1000 ? (p.stars/1000).toFixed(1)+'K' : p.stars} stars</span>` : ''}
            </div>
            <div class="paper-tags">
                ${p.tags.map(t => `<span class="paper-tag">${t}</span>`).join('')}
            </div>
            <div class="paper-actions">
                ${p.arxiv ? `<a href="https://arxiv.org/abs/${p.arxiv}" target="_blank" class="paper-btn primary">arXiv</a>` : ''}
                ${p.github ? `<a href="${p.github}" target="_blank" class="paper-btn secondary">GitHub</a>` : ''}
            </div>
        </div>
    `).join('');
}

function getTrendColor(trend) {
    const colors = { hot: '#9a5b45', rising: '#a4713f', stable: '#647f71' };
    return colors[trend] || '#8b7f73';
}

function renderSOTA() {
    if (liveSotaData && Array.isArray(liveSotaData.benchmarks)) {
        renderLiveSOTA(liveSotaData);
        return;
    }

    const sotaData = papersData.sota_history;
    const container = document.getElementById('sotaContainer');
    
    if (!sotaData || Object.keys(sotaData).length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:40px;color:var(--text-muted)">SOTA data will be added when verified benchmark results are available.</div>';
        return;
    }
    
    const colors = ['#9a5b45', '#c07a5a', '#647f71', '#8f6b3f', '#4f6f82'];
    
    container.innerHTML = Object.entries(sotaData).map(([benchmark, history], idx) => {
        const color = colors[idx % colors.length];
        const latest = history[history.length - 1];
        const scores = history.map(h => h.score);
        const minScore = Math.min(...scores) - 5;
        const maxScore = Math.max(...scores) + 2;
        
        const width = 400;
        const height = 200;
        const padding = { top: 20, right: 20, bottom: 40, left: 50 };
        const chartW = width - padding.left - padding.right;
        const chartH = height - padding.top - padding.bottom;
        
        const points = history.map((h, i) => {
            const x = padding.left + (i / (history.length - 1)) * chartW;
            const y = padding.top + chartH - ((h.score - minScore) / (maxScore - minScore)) * chartH;
            return `${x},${y}`;
        }).join(' ');
        
        const areaPoints = `${padding.left},${padding.top + chartH} ${points} ${padding.left + chartW},${padding.top + chartH}`;
        
        const labels = history.map((h, i) => {
            const x = padding.left + (i / (history.length - 1)) * chartW;
            const y = padding.top + chartH - ((h.score - minScore) / (maxScore - minScore)) * chartH;
            return `<text x="${x}" y="${y - 10}" text-anchor="middle" font-size="10" fill="${color}" font-weight="700">${h.score}</text>
                    <circle cx="${x}" cy="${y}" r="5" fill="${color}" stroke="#fffaf2" stroke-width="2"/>
                    <text x="${x}" y="${height - 10}" text-anchor="middle" font-size="10" fill="var(--text-muted)">${h.year}</text>`;
        }).join('');
        
        return `
            <div class="sota-card">
                <div class="sota-card-header">
                    <div class="sota-card-title">${benchmark}</div>
                    <div class="sota-card-current">
                        <div class="sota-label">Current SOTA</div>
                        <div class="sota-value">${latest.score}</div>
                        <div class="sota-model">${latest.model}</div>
                    </div>
                </div>
                <svg class="sota-chart" viewBox="0 0 ${width} ${height}">
                    <defs>
                        <linearGradient id="grad-${idx}" x1="0%" y1="0%" x2="0%" y2="100%">
                            <stop offset="0%" style="stop-color:${color};stop-opacity:0.3" />
                            <stop offset="100%" style="stop-color:${color};stop-opacity:0" />
                        </linearGradient>
                    </defs>
                    <polygon points="${areaPoints}" fill="url(#grad-${idx})" />
                    <polyline points="${points}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                    ${labels}
                </svg>
                <div class="sota-legend">
                    ${history.map(h => `
                        <div class="sota-legend-item">
                            <div class="sota-legend-dot" style="background:${color}"></div>
                            ${h.model} (${h.year})
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }).join('');
}

function renderLiveSOTA(data) {
    const container = document.getElementById('sotaContainer');
    const colors = ['#9a5b45', '#c07a5a', '#647f71', '#8f6b3f', '#4f6f82'];
    const meta = `
        <div class="sota-update-panel">
            <div>
                <div class="sota-update-label">SOTA tracker</div>
                <div class="sota-update-title">${data.status || 'Source-backed snapshot'}</div>
                <p>${data.note || 'Benchmark data is periodically refreshed from source pages.'}</p>
            </div>
            <div class="sota-update-meta">
                <span>Last checked: ${data.lastChecked || 'Unknown'}</span>
                <span>Cadence: ${data.updateCadence || 'manual'}</span>
                <span>Next check: ${data.nextScheduledCheck || 'TBD'}</span>
            </div>
        </div>
    `;

    const cards = data.benchmarks.map((benchmark, idx) => {
        const color = colors[idx % colors.length];
        const history = benchmark.history || [];
        const topRows = [...history]
            .filter(row => Number.isFinite(Number(row.score)))
            .sort((a, b) => Number(b.score) - Number(a.score))
            .slice(0, 5);
        const latest = benchmark.leader || topRows[0] || {};
        const scores = history.map(h => Number(h.score)).filter(Number.isFinite);
        const width = 400;
        const height = 180;
        const padding = { top: 20, right: 22, bottom: 36, left: 48 };
        const chartW = width - padding.left - padding.right;
        const chartH = height - padding.top - padding.bottom;
        let chart = '<div class="sota-empty-chart">Not enough historical points yet</div>';

        if (scores.length > 1) {
            const minScore = Math.min(...scores) - 2;
            const maxScore = Math.max(...scores) + 2;
            const points = history.map((h, i) => {
                const x = padding.left + (i / (history.length - 1)) * chartW;
                const y = padding.top + chartH - ((Number(h.score) - minScore) / (maxScore - minScore)) * chartH;
                return `${x},${y}`;
            }).join(' ');
            const labels = history.map((h, i) => {
                const x = padding.left + (i / (history.length - 1)) * chartW;
                const y = padding.top + chartH - ((Number(h.score) - minScore) / (maxScore - minScore)) * chartH;
                return `<circle cx="${x}" cy="${y}" r="4.5" fill="${color}" stroke="#fffaf2" stroke-width="2"/>
                        <text x="${x}" y="${height - 10}" text-anchor="middle" font-size="10" fill="#8b7f73">#${i + 1}</text>`;
            }).join('');
            chart = `
                <svg class="sota-chart" viewBox="0 0 ${width} ${height}">
                    <polyline points="${points}" fill="none" stroke="${color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
                    ${labels}
                </svg>
            `;
        }

        return `
            <div class="sota-card">
                <div class="sota-card-header">
                    <div>
                        <div class="sota-card-title">${benchmark.name}</div>
                        <div class="sota-card-subtitle">${benchmark.task} · ${benchmark.metric}</div>
                    </div>
                    <div class="sota-card-current">
                        <div class="sota-label">Current leader</div>
                        <div class="sota-value">${latest.score ?? '-'}</div>
                        <div class="sota-model">${latest.model || 'Unknown'}</div>
                    </div>
                </div>
                ${chart}
                <div class="sota-source-row">
                    <span>${benchmark.updateMode || 'manual'}</span>
                    <span>Checked ${benchmark.lastChecked || data.lastChecked || 'Unknown'}</span>
                    <a href="${benchmark.sourceUrl}" target="_blank" rel="noreferrer">${benchmark.sourceName || 'Source'}</a>
                </div>
                <div class="sota-mini-table">
                    ${topRows.map(row => `
                        <div class="sota-mini-row">
                            <span>${row.model}</span>
                            <strong>${row.score}</strong>
                            <em>${row.type || ''}</em>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = meta + cards;
}

function renderFeedback() {
    const container = document.getElementById('feedbackContainer');
    if (!container) return;

    if (!feedbackData) {
        container.innerHTML = `
            <div class="feedback-card">
                <h3>Submit benchmark updates</h3>
                <p>Use GitHub Issues to submit missing or corrected benchmark results.</p>
                <a class="feedback-link" href="https://github.com/Yang-Jiashu/document-intelligence-survey/issues/new?template=benchmark-update.yml" target="_blank" rel="noreferrer">Open update issue</a>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="feedback-card feedback-card-wide">
            <div>
                <div class="feedback-kicker">Feedback loop</div>
                <h3>${feedbackData.title}</h3>
                <p>${feedbackData.policy}</p>
            </div>
            <div class="feedback-cadence">
                <span>Auto refresh: ${feedbackData.autoRefreshCadence}</span>
                <span>Manual review: ${feedbackData.reviewCadence}</span>
            </div>
            <a class="feedback-link" href="${feedbackData.githubIssueUrl}" target="_blank" rel="noreferrer">Submit benchmark update</a>
        </div>
        <div class="feedback-card">
            <h3>Evidence checklist</h3>
            <div class="feedback-pill-list">
                ${(feedbackData.requestedEvidence || []).map(item => `<span>${item}</span>`).join('')}
            </div>
        </div>
        <div class="feedback-card feedback-card-wide">
            <h3>Tracked community candidates</h3>
            <div class="candidate-list">
                ${(feedbackData.trackedCandidates || []).map(item => `
                    <div class="candidate-row">
                        <div>
                            <strong>${item.model}</strong>
                            <span>${item.benchmark}</span>
                            <p>${item.reason}</p>
                        </div>
                        <em>${item.status}</em>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function renderTrendChart() {
    const trends = papersData.trends;
    const svg = document.getElementById('trendChart');
    const width = svg.clientWidth || 800;
    const height = 300;
    const padding = { top: 20, right: 30, bottom: 40, left: 50 };
    
    const maxVal = Math.max(...trends.layout, ...trends.ocr, ...trends.table, ...trends.rag, ...trends.vlm);
    const chartW = width - padding.left - padding.right;
    const chartH = height - padding.top - padding.bottom;
    
    const colors = { layout: '#9a5b45', ocr: '#c07a5a', table: '#647f71', rag: '#8f6b3f', vlm: '#4f6f82' };
    
    let paths = '';
    const categories = ['layout', 'ocr', 'table', 'rag', 'vlm'];
    
    categories.forEach(cat => {
        const data = trends[cat];
        const points = data.map((v, i) => {
            const x = padding.left + (i / (data.length - 1)) * chartW;
            const y = padding.top + chartH - (v / maxVal) * chartH;
            return `${x},${y}`;
        }).join(' ');
        
        paths += `<polyline points="${points}" fill="none" stroke="${colors[cat]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>`;
        
        data.forEach((v, i) => {
            const x = padding.left + (i / (data.length - 1)) * chartW;
            const y = padding.top + chartH - (v / maxVal) * chartH;
            paths += `<circle cx="${x}" cy="${y}" r="5" fill="${colors[cat]}" stroke="#fffaf2" stroke-width="2"/>`;
        });
    });
    
    // Axes
    const xAxisY = padding.top + chartH;
    paths += `<line x1="${padding.left}" y1="${xAxisY}" x2="${width - padding.right}" y2="${xAxisY}" stroke="#ded0c0" stroke-width="1"/>`;
    paths += `<line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${xAxisY}" stroke="#ded0c0" stroke-width="1"/>`;
    
    // X labels
    trends.years.forEach((year, i) => {
        const x = padding.left + (i / (trends.years.length - 1)) * chartW;
        paths += `<text x="${x}" y="${height - 10}" text-anchor="middle" font-size="12" fill="#8b7f73" font-weight="600">${year}</text>`;
    });
    
    svg.innerHTML = paths;
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
}

function renderLeaderboard() {
    const lb = papersData.leaderboard;
    const container = document.getElementById('leaderboardBody');
    
    container.innerHTML = lb.map((row, i) => `
        <div class="lb-row">
            <div style="display:flex;align-items:center;gap:10px">
                <span class="lb-rank">${i + 1}</span>
                <span class="lb-model">${row.model}</span>
            </div>
            <span class="lb-type ${row.type.toLowerCase()}">${row.type}</span>
        </div>
    `).join('');
}

function renderBenchmarks() {
    const benches = papersData.benchmarks;
    const container = document.getElementById('benchmarkContainer');
    
    container.innerHTML = benches.map(b => `
        <div class="bench-card">
            <div class="bench-header">
                <span class="bench-name">${b.name}</span>
            </div>
            <div class="bench-meta">
                <span>${b.type}</span>
                <span>&#8226;</span>
                <span>${b.size}</span>
                <span>&#8226;</span>
                <span>${b.year}</span>
            </div>
            <div class="bench-sota">
                <span class="bench-sota-label">Metric: ${b.metric}</span>
            </div>
        </div>
    `).join('');
}

function renderTaxonomy() {
    const taxonomy = [
        {
            icon: 'OCR', filter: 'ocr', title: 'OCR & Text Recognition', desc: 'Optical Character Recognition, scene text, handwritten text',
            children: ['Traditional OCR', 'Scene Text Detection', 'Handwritten Recognition', 'Multilingual OCR'],
            count: papersData.papers.filter(p => p.category === 'ocr').length
        },
        {
            icon: 'LAY', filter: 'layout', title: 'Layout Analysis', desc: 'Document structure detection, region segmentation, reading order',
            children: ['Layout Detection', 'Region Segmentation', 'Reading Order', 'Form Understanding'],
            count: papersData.papers.filter(p => p.category === 'layout').length
        },
        {
            icon: 'TAB', filter: 'table', title: 'Table Understanding', desc: 'Table detection, structure recognition, table QA',
            children: ['Table Detection', 'Structure Recognition', 'Table QA', 'Spreadsheet Understanding'],
            count: papersData.papers.filter(p => p.category === 'table').length
        },
        {
            icon: 'VLM', filter: 'vlm', title: 'Vision-Language Models', desc: 'VLM for document understanding, OCR-free methods, multimodal reasoning',
            children: ['OCR-free Models', 'High-resolution VLM', 'Document VLM', 'Multimodal RAG'],
            count: papersData.papers.filter(p => p.category === 'vlm').length
        },
        {
            icon: 'RAG', filter: 'rag', title: 'Retrieval-Augmented Generation', desc: 'Document RAG, knowledge extraction, long-context understanding',
            children: ['Document RAG', 'Knowledge Graph', 'Long-context', 'Multi-hop QA'],
            count: papersData.papers.filter(p => p.category === 'rag').length
        },
        {
            icon: 'EVAL', filter: 'eval', title: 'Evaluation & Benchmarks', desc: 'Datasets, metrics, benchmark suites for document intelligence',
            children: ['VQA Benchmarks', 'Layout Benchmarks', 'OCR Benchmarks', 'End-to-end Evaluation'],
            count: papersData.papers.filter(p => p.category === 'eval').length
        }
    ];
    
    const container = document.getElementById('taxonomyContainer');
    container.innerHTML = taxonomy.map(node => `
        <div class="taxonomy-card" onclick="filterPapers('${node.filter}')">
            <div class="tc-header">
                <div class="tc-icon">${node.icon}</div>
                <div class="tc-info">
                    <div class="tc-title">${node.title}</div>
                    <div class="tc-count">${node.count} papers</div>
                </div>
            </div>
            <div class="tc-desc">${node.desc}</div>
            <div class="tc-tags">
                ${node.children.map(child => `<span class="tc-tag">${child}</span>`).join('')}
            </div>
        </div>
    `).join('');
}

function renderTimeline() {
    const milestones = [
        { year: '2019', title: 'LayoutLM Era Begins', desc: 'First layout-aware pre-training for document AI', papers: ['LayoutLM'] },
        { year: '2020', title: 'DocVQA Benchmark', desc: 'Standardized visual question answering on documents', papers: ['DocVQA'] },
        { year: '2021', title: 'OCR-free Paradigm', desc: 'End-to-end document understanding without OCR', papers: ['Donut', 'Pix2Struct'] },
        { year: '2022', title: 'Unified Pre-training', desc: 'Unified text and image masking for document AI', papers: ['LayoutLMv3'] },
        { year: '2023', title: 'VLM for Documents', desc: 'Large vision-language models applied to documents', papers: ['Monkey', 'LLaVA', 'Qwen2-VL'] },
        { year: '2024', title: 'Document RAG & Parsing', desc: 'Retrieval-augmented generation and unified parsing', papers: ['LightRAG', 'OmniParser', 'GraphRAG'] },
        { year: '2025', title: 'Advanced Document VLM', desc: 'State-of-the-art vision-language models for documents', papers: ['Qwen3-VL'] }
    ];
    
    const container = document.getElementById('timelineContainer');
    container.innerHTML = milestones.map(m => `
        <div class="timeline-item">
            <div class="timeline-year">${m.year}</div>
            <div class="timeline-title">${m.title}</div>
            <div class="timeline-desc">${m.desc}</div>
            <div class="timeline-papers">
                ${m.papers.map(p => `<span class="timeline-paper">${p}</span>`).join('')}
            </div>
        </div>
    `).join('');
}

function renderDatasets() {
    const datasets = [
        { name: 'DocVQA', task: 'VQA', year: 2020, size: '12K docs', metric: 'ANLS', links: { paper: '2007.00398', code: '' } },
        { name: 'InfographicVQA', task: 'VQA', year: 2021, size: '5K docs', metric: 'ANLS', links: { paper: '2104.07453', code: '' } },
        { name: 'PubLayNet', task: 'Layout', year: 2019, size: '360K pages', metric: 'mAP', links: { paper: '1908.07836', code: '' } },
        { name: 'DocLayNet', task: 'Layout', year: 2022, size: '80K pages', metric: 'mAP', links: { paper: '2206.01062', code: '' } },
        { name: 'OCRBench', task: 'OCR', year: 2023, size: '29 tasks', metric: 'Score', links: { paper: '2312.09601', code: '' } },
        { name: 'CRAG', task: 'RAG', year: 2024, size: '4 domains', metric: 'Accuracy', links: { paper: '2401.15051', code: '' } },
        { name: 'TableFact', task: 'Table', year: 2019, size: '16K claims', metric: 'Accuracy', links: { paper: '1909.02164', code: '' } },
        { name: 'FeTaQA', task: 'Table', year: 2021, size: '10K QA', metric: 'BLEU', links: { paper: '2104.00369', code: '' } }
    ];
    
    const container = document.getElementById('datasetTableBody');
    container.innerHTML = datasets.map(d => `
        <tr>
            <td><span class="ds-name">${d.name}</span></td>
            <td><span class="ds-task">${d.task}</span></td>
            <td>${d.year}</td>
            <td>${d.size}</td>
            <td>${d.metric}</td>
            <td>
                <div class="ds-links">
                    ${d.links.paper ? `<a href="https://arxiv.org/abs/${d.links.paper}" target="_blank">Paper</a>` : ''}
                    ${d.links.code ? `<a href="${d.links.code}" target="_blank">Code</a>` : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

function renderReadingList() {
    const paths = [
        {
            title: 'Getting Started',
            desc: 'Essential papers to understand document intelligence',
            papers: [
                { title: 'LayoutLM', desc: 'Pre-training of Text and Layout for Document Image Understanding', tag: 'Foundation' },
                { title: 'Donut', desc: 'OCR-free Document Understanding Transformer', tag: 'OCR-free' },
                { title: 'DocVQA', desc: 'A Dataset for VQA on Document Images', tag: 'Benchmark' }
            ]
        },
        {
            title: 'Deep Dive',
            desc: 'Advanced methods and recent innovations',
            papers: [
                { title: 'LayoutLMv3', desc: 'Unified Text and Image Masking for Document AI', tag: 'Pre-training' },
                { title: 'Monkey', desc: 'Image Resolution and Text Label Are Important Things', tag: 'VLM' },
                { title: 'LightRAG', desc: 'Simple and Fast Retrieval-Augmented Generation', tag: 'RAG' }
            ]
        },
        {
            title: 'Cutting Edge',
            desc: 'Latest state-of-the-art methods',
            papers: [
                { title: 'Qwen3-VL', desc: 'Advanced Vision-Language Model for Document Understanding', tag: 'SOTA' },
                { title: 'OmniParser', desc: 'Unified Framework for Document Parsing', tag: 'Parsing' },
                { title: 'GraphRAG', desc: 'From Local to Global Reasoning on Graphs', tag: 'RAG' }
            ]
        }
    ];
    
    const container = document.getElementById('readingContainer');
    container.innerHTML = paths.map((path, pi) => `
        <div class="reading-card">
            <h3>${path.title}</h3>
            <p>${path.desc}</p>
            <div class="reading-list">
                ${path.papers.map((p, i) => `
                    <div class="reading-item">
                        <div class="ri-num">${i + 1}</div>
                        <div class="ri-content">
                            <div class="ri-title">${p.title}</div>
                            <div class="ri-desc">${p.desc}</div>
                            <span class="ri-tag">${p.tag}</span>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `).join('');
}

function renderActivity() {
    const activities = [
        { type: 'star', icon: 'GH', title: 'MinerU reached 66.9K stars', desc: 'OpenDataLab\'s document extraction tool gains massive popularity', time: 'Snapshot entry', color: '#f0e2d6' },
        { type: 'code', icon: 'REL', title: 'GraphRAG v0.4 released', desc: 'Microsoft adds new community detection algorithms', time: 'Snapshot entry', color: '#e6eee8' },
        { type: 'paper', icon: 'SOTA', title: 'New SOTA on DocVQA', desc: 'Qwen3-VL achieves 93.1% ANLS score', time: 'Needs citation', color: '#e7eef1' },
        { type: 'star', icon: 'GH', title: 'LightRAG trending', desc: 'HKUDS lightweight RAG framework hits 36.3K stars', time: 'Snapshot entry', color: '#f0e2d6' },
        { type: 'paper', icon: 'PPR', title: 'DocLayout-YOLO paper', desc: 'Real-time layout detection with synthetic data augmentation', time: 'Snapshot entry', color: '#e7eef1' }
    ];
    
    const container = document.getElementById('activityContainer');
    container.innerHTML = activities.map(a => `
        <div class="activity-item">
            <div class="activity-icon" style="background:${a.color}">${a.icon}</div>
            <div class="activity-content">
                <div class="activity-title">${a.title}</div>
                <div class="activity-desc">${a.desc}</div>
                <div class="activity-meta">
                    <span>${a.time}</span>
                </div>
            </div>
        </div>
    `).join('');
}

function filterPapers(category) {
    currentFilter = category;
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === category);
    });
    renderPapers();
}

function sortPapers(sortBy) {
    currentSort = sortBy;
    renderPapers();
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    
    document.getElementById('searchInput').addEventListener('input', () => renderPapers());
    
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => filterPapers(btn.dataset.filter));
    });
});

window.addEventListener('hashchange', restoreHashPosition);

// Lightbox
let currentFigIndex = 0;
const figs = ['fig01.png','fig02.png','fig03.png','fig04.png','fig05.png','fig06.png','fig07.png','fig08.png','fig09.png','fig10.png'];

function openLightbox(idx) {
    currentFigIndex = idx;
    document.getElementById('lightbox-img').src = 'images/' + figs[idx];
    document.getElementById('lightbox').classList.add('active');
}

function closeLightbox(e) {
    if (e.target.id === 'lightbox' || e.target.classList.contains('lightbox-close')) {
        document.getElementById('lightbox').classList.remove('active');
    }
}

function nextFig() {
    currentFigIndex = (currentFigIndex + 1) % figs.length;
    document.getElementById('lightbox-img').src = 'images/' + figs[currentFigIndex];
}

function prevFig() {
    currentFigIndex = (currentFigIndex - 1 + figs.length) % figs.length;
    document.getElementById('lightbox-img').src = 'images/' + figs[currentFigIndex];
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') document.getElementById('lightbox').classList.remove('active');
    if (e.key === 'ArrowRight') nextFig();
    if (e.key === 'ArrowLeft') prevFig();
});
