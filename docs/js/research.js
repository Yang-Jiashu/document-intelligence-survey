(function () {
    'use strict';
    const topicNames = { ocr: 'OCR / 解析', layout: '版面', table: '表格 / 图表', docqa: '文档问答', docrag: '文档 RAG', eval: '评测' };
    const officialRepos = new Set(['paddlepaddle/paddleocr', 'opendatalab/mineru', 'docling-project/docling']);
    const pageSize = 20;
    let data = null;
    let filters = readFilters(window.location.search);
    let loadError = false;
    let scopeError = false;

    function escapeHtml(value) {
        return String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
    }
    function safePaperUrl(value) {
        try {
            const url = new URL(value);
            return url.protocol === 'https:' && url.hostname === 'arxiv.org' && !url.username && !url.password && !url.port && !url.search && !url.hash
                && /^\/(abs|pdf)\/(?:\d{4}\.\d{4,5}(?:v\d+)?|[a-z.-]+\/\d{7}(?:v\d+)?)(?:\.pdf)?$/.test(url.pathname) ? url.href : '';
        } catch (_) { return ''; }
    }
    function safeReleaseUrl(value, expectedRepo) {
        try {
            const url = new URL(value);
            const parts = url.pathname.split('/').filter(Boolean);
            const repo = parts.slice(0, 2).join('/').toLowerCase();
            return url.protocol === 'https:' && url.hostname === 'github.com' && !url.username && !url.password && !url.port && !url.search && !url.hash
                && officialRepos.has(repo) && (!expectedRepo || repo === String(expectedRepo).toLowerCase())
                && parts[2] === 'releases' && (parts.length === 3 || (parts[3] === 'tag' && parts.length >= 5)) ? url.href : '';
        } catch (_) { return ''; }
    }
    function safeSourceUrl(value) {
        try {
            const url = new URL(value);
            if (url.protocol !== 'https:' || url.username || url.password || url.port) return '';
            if (['arxiv.org', 'export.arxiv.org', 'rss.arxiv.org'].includes(url.hostname)) return url.href;
            if (url.hostname === 'api.github.com') {
                const match = url.pathname.match(/^\/repos\/([^/]+\/[^/]+)\/releases(?:\/latest)?$/);
                return match && officialRepos.has(match[1].toLowerCase()) ? url.href : '';
            }
            return safeReleaseUrl(value);
        } catch (_) { return ''; }
    }
    function timestamp(value) { const result = Date.parse(value); return Number.isFinite(result) ? result : 0; }
    function dateLabel(value) { return timestamp(value) ? String(value).slice(0, 10) : '尚未核验'; }
    function checkedLabel(value) {
        if (!timestamp(value)) return '尚未核验';
        const parts = new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(value));
        const part = type => parts.find(item => item.type === type).value;
        return `${part('year')}-${part('month')}-${part('day')} ${part('hour')}:${part('minute')}（北京时间）`;
    }
    function validSnapshot(snapshot) {
        return snapshot?.schemaVersion === 2 && snapshot.scope === 'document-intelligence' && Array.isArray(snapshot.topics) && Array.isArray(snapshot.papers);
    }
    function readFilters(search) {
        const params = new URLSearchParams(search);
        const topic = params.get('topic') || 'all';
        const period = params.get('days') || '30';
        const page = Number(params.get('page'));
        return { q: (params.get('q') || '').trim(), topic: Object.hasOwn(topicNames, topic) ? topic : 'all', days: ['7', '30', '90', 'all'].includes(period) ? period : '30',
            kind: ['paper', 'release'].includes(params.get('kind')) ? params.get('kind') : 'all',
            sort: ['published', 'updated'].includes(params.get('sort')) ? params.get('sort') : 'recommended', page: Number.isFinite(page) ? Math.max(1, Math.floor(page)) : 1 };
    }
    function tokens(value) {
        const lower = String(value || '').toLowerCase();
        const result = lower.match(/[a-z0-9]+(?:[.-][a-z0-9]+)*|[\p{Script=Han}]+/gu) || [];
        return result.flatMap(token => /[\p{Script=Han}]/u.test(token) && token.length > 1 ? Array.from({ length: token.length - 1 }, (_, i) => token.slice(i, i + 2)) : [token]);
    }
    function queryTokens(query) {
        const aliases = { '文档': 'document', '解析': 'parsing', '表格': 'table', '图表': 'chart', '版面': 'layout', '问答': 'docvqa question answering', '检索': 'retrieval', '发票': 'invoice', '票据': 'receipt', '扫描': 'scanned', '评测': 'benchmark evaluation' };
        let expanded = String(query || '');
        for (const [term, alias] of Object.entries(aliases)) if (expanded.includes(term)) expanded += ' ' + alias;
        return [...new Set(tokens(expanded))];
    }
    function bm25Scores(items, query) {
        const terms = queryTokens(query);
        if (!terms.length) return new Map(items.map(item => [item, 0]));
        const documents = items.map(item => {
            const title = tokens(item.title), tags = tokens([...(Array.isArray(item.tags) ? item.tags : []), ...(Array.isArray(item.topics) ? item.topics : []).map(id => topicNames[id] || '')].join(' '));
            const body = [...title, ...title, ...title, ...title, ...tags, ...tags, ...tokens(item.abstract), ...tokens((Array.isArray(item.authors) ? item.authors : []).join(' ')), ...tokens(item.arxiv), ...tokens(item.repo)];
            const counts = new Map();
            body.forEach(term => counts.set(term, (counts.get(term) || 0) + 1));
            return { item, counts, length: body.length || 1 };
        });
        const averageLength = documents.reduce((sum, doc) => sum + doc.length, 0) / (documents.length || 1);
        const frequency = new Map(terms.map(term => [term, documents.filter(doc => doc.counts.has(term)).length]));
        return new Map(documents.map(doc => {
            const score = terms.reduce((sum, term) => {
                const tf = doc.counts.get(term) || 0;
                const df = frequency.get(term);
                const idf = Math.log(1 + (documents.length - df + 0.5) / (df + 0.5));
                return sum + (tf ? idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * doc.length / averageLength)) : 0);
            }, 0);
            return [doc.item, score];
        }));
    }
    function selectPapers(snapshot, selection, now = Date.now()) {
        if (!validSnapshot(snapshot)) return [];
        const cutoff = selection.days === 'all' ? 0 : now - Number(selection.days) * 86400000;
        const sort = selection.sort || 'recommended';
        const relevantField = sort === 'published' ? 'published' : 'updated';
        const candidates = snapshot.papers.filter(item => {
            const topics = Array.isArray(item.topics) ? item.topics.filter(id => Object.hasOwn(topicNames, id)) : [];
            if (!topics.length || (selection.topic !== 'all' && !topics.includes(selection.topic))) return false;
            const kind = item.kind === 'release' ? 'release' : 'paper';
            if (selection.kind && selection.kind !== 'all' && kind !== selection.kind) return false;
            const relevantDate = timestamp(item[relevantField] || item.published);
            return relevantDate && relevantDate >= cutoff && relevantDate <= now + 86400000;
        });
        const searching = queryTokens(selection.q).length > 0;
        const scores = bm25Scores(candidates, selection.q);
        const ranked = candidates.filter(item => !searching || scores.get(item) > 0).sort((a, b) => {
            if (searching) { const relevance = scores.get(b) - scores.get(a); if (relevance) return relevance; }
            if (sort === 'recommended') {
                const rank = item => Number.isFinite(item.rankScore) ? item.rankScore : Number(item.relevanceScore) || 0;
                const score = rank(b) - rank(a);
                if (score) return score;
            }
            return timestamp(b[relevantField] || b.published) - timestamp(a[relevantField] || a.published) || String(a.title).localeCompare(String(b.title));
        });
        return ranked;
    }
    function hasSourceFailure(snapshot) {
        return !validSnapshot(snapshot) || snapshot.status !== 'refreshed' || Object.keys(topicNames).some(id => !snapshot.topics.some(topic => topic.id === id && topic.status === 'fresh'))
            || (Array.isArray(snapshot.sources) && snapshot.sources.some(source => source.status !== 'fresh'));
    }
    function statusHtml(snapshot, failed = false, wrongScope = false) {
        if (wrongScope) return '<div class="research-status warning"><strong>正在切换为文档智能进展</strong><span>旧范围数据已隐藏，等待文档智能来源核验。</span></div>';
        if (failed) return '<div class="research-status warning"><strong>进展数据暂时无法加载</strong><span>请稍后重试。此状态不代表没有新进展。</span></div>';
        if (!snapshot) return '<div class="research-status"><span>正在读取文档智能进展…</span></div>';
        const warning = hasSourceFailure(snapshot);
        const labels = { refreshed: '每日抓取已完成', partial: '部分来源抓取失败', unavailable: '本次抓取未完成', 'not-yet-checked': '等待首次核验' };
        return `<div class="research-status${warning ? ' warning' : ''}"><strong>${escapeHtml(labels[snapshot.status] || '来源状态待确认')}</strong><span>最近尝试：${escapeHtml(checkedLabel(snapshot.lastAttempt))}</span><span>最近完整核验：${escapeHtml(checkedLabel(snapshot.lastSuccessfulCheck))}</span><span>下次计划：${escapeHtml(snapshot.nextScheduledCheck || '待确认')}</span>${warning ? '<span>保留已核验记录；请查看各来源的最后核验日期。</span>' : ''}</div>`;
    }
    function sourceCard(source, title) {
        const fresh = source.status === 'fresh';
        const href = safeSourceUrl(source.sourceUrl || source.url);
        const cap = Number.isInteger(source.resultLimit) && source.resultLimit > 0 ? source.resultLimit : null;
        return `<div class="research-source-card${fresh ? '' : ' stale'}"><div class="research-source-title"><span>${escapeHtml(title)}</span><span class="research-source-state">${fresh ? '已核验' : source.status === 'stale' ? '抓取失败 · 保留旧数据' : '尚未核验'}</span></div><span class="research-check-date">最后核验：${escapeHtml(checkedLabel(source.lastChecked))}</span>${cap ? `<span class="research-check-date">每次最多核验最新 ${cap} 条候选${source.truncated === true ? '，非全量' : ''}</span>` : ''}${href ? `<a href="${escapeHtml(href)}" target="_blank" rel="noreferrer">查看官方来源 ↗</a>` : ''}</div>`;
    }
    function topicStatusHtml(snapshot) {
        return Object.entries(topicNames).map(([id, name]) => sourceCard(snapshot?.topics?.find(topic => topic.id === id) || {}, name)).join('');
    }
    function sourceStatusHtml(snapshot) {
        return (Array.isArray(snapshot?.sources) ? snapshot.sources : []).map(source => sourceCard(source, source.title || source.id || '官方开源来源')).join('');
    }
    function paperHtml(item) {
        const release = item.kind === 'release';
        const url = release ? safeReleaseUrl(item.url, item.repo) : safePaperUrl(item.url);
        const pdf = release ? '' : safePaperUrl(item.pdfUrl);
        const topics = (Array.isArray(item.topics) ? item.topics : []).filter(id => Object.hasOwn(topicNames, id));
        const authors = Array.isArray(item.authors) ? item.authors : [];
        const abstract = String(item.abstract || '官方来源尚未提供摘要。');
        const preview = abstract.length > 360 ? abstract.slice(0, 360) + '…' : abstract;
        const revision = !release && timestamp(item.updated) > timestamp(item.published);
        const reasons = (Array.isArray(item.rankReasons) ? item.rankReasons : []).slice(0, 3);
        const matched = topics.flatMap(id => Array.isArray(item.matchedTerms?.[id]) ? item.matchedTerms[id] : []).slice(0, 5);
        return `<article class="research-paper"><div class="research-paper-topline">${topics.map(id => `<span class="research-topic-tag ${id}">${topicNames[id]}</span>`).join('')}<span class="research-preprint">${release ? '官方开源版本' : 'arXiv 预印本'}</span></div><h3>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(item.title)}</a>` : escapeHtml(item.title || '未命名进展')}</h3><div class="research-paper-authors">${release ? escapeHtml(item.sourceName || item.repo || 'GitHub') : escapeHtml(authors.slice(0, 8).join(', '))}${!release && authors.length > 8 ? ` 等 ${authors.length} 位作者` : ''}</div><div class="research-paper-meta"><span>${release ? '版本发布' : '首次发表'} ${escapeHtml(dateLabel(item.published))}</span>${revision ? `<span>${release ? '发布说明更新' : '版本更新'} ${escapeHtml(dateLabel(item.updated))}${Number.isInteger(item.version) && item.version > 1 ? ` · v${item.version}` : ''}</span>` : ''}<span>${escapeHtml(release ? item.repo || '' : item.arxiv || '')}</span></div><div class="research-paper-abstract"><p>${escapeHtml(preview)}</p>${abstract.length > 360 ? `<details><summary>阅读完整${release ? '版本说明' : '摘要'}</summary><p class="research-abstract-rest">${escapeHtml(abstract)}</p></details>` : ''}</div>${reasons.length ? `<div class="research-rank-reasons">推荐依据：${reasons.map(escapeHtml).join(' · ')}</div>` : ''}<div class="research-paper-footer"><div class="research-paper-links">${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${release ? '官方版本' : '论文原文'} ↗</a>` : ''}${pdf ? `<a href="${escapeHtml(pdf)}" target="_blank" rel="noreferrer">PDF ↗</a>` : ''}</div>${matched.length ? `<span class="research-match">主题关键词：${escapeHtml([...new Set(matched)].join(' · '))}</span>` : ''}</div></article>`;
    }
    function emptyHtml(snapshot, failed = false, wrongScope = false) {
        if (wrongScope) return '<div class="research-empty"><h3>文档智能进展正在准备中</h3><p>先前范围的数据已隐藏；只展示经文档相关性筛选的新论文和官方开源版本。</p></div>';
        if (!snapshot && !failed) return '<div class="research-empty"><h3>正在读取文档智能进展…</h3><p>筛选条件会在数据加载后生效。</p></div>';
        if (failed || hasSourceFailure(snapshot)) return '<div class="research-empty"><h3>暂时没有可显示的已核验记录</h3><p>部分来源尚未成功核验，不能据此判断没有新研究。已有记录会继续保留，也可调整主题、关键词或时间范围查看。</p></div>';
        return '<div class="research-empty"><h3>当前筛选下没有已收录进展</h3><p>可以清除关键词、切换主题或扩大时间范围。自动发现按文档相关性覆盖来源，并不代表没有其他新进展。</p></div>';
    }
    function updateUrl() {
        const params = new URLSearchParams();
        if (filters.q) params.set('q', filters.q);
        if (filters.topic !== 'all') params.set('topic', filters.topic);
        if (filters.kind !== 'all') params.set('kind', filters.kind);
        if (filters.days !== '30') params.set('days', filters.days);
        if (filters.sort !== 'recommended') params.set('sort', filters.sort);
        if (filters.page > 1) params.set('page', String(filters.page));
        window.history.replaceState({}, '', 'research.html' + (params.size ? '?' + params.toString() : ''));
    }
    function renderPagination(total) {
        const node = document.getElementById('researchPagination');
        const totalPages = Math.max(1, Math.ceil(total / pageSize));
        if (totalPages === 1) { node.innerHTML = ''; return; }
        const pages = [];
        for (let page = Math.max(1, filters.page - 2); page <= Math.min(totalPages, filters.page + 2); page++) pages.push(page);
        node.innerHTML = `<button type="button" data-page="${filters.page - 1}" ${filters.page === 1 ? 'disabled' : ''}>上一页</button>${pages.map(page => `<button type="button" data-page="${page}" ${page === filters.page ? 'class="active" aria-current="page"' : ''}>${page}</button>`).join('')}<button type="button" data-page="${filters.page + 1}" ${filters.page === totalPages ? 'disabled' : ''}>下一页</button>`;
        node.querySelectorAll('[data-page]').forEach(button => button.addEventListener('click', () => { filters.page = Number(button.dataset.page); render(); document.getElementById('feedTitle').scrollIntoView({ behavior: 'smooth', block: 'start' }); }));
    }
    function render() {
        document.getElementById('researchStatus').innerHTML = statusHtml(data, loadError, scopeError);
        document.getElementById('researchTopics').innerHTML = topicStatusHtml(data);
        document.getElementById('researchSources').innerHTML = sourceStatusHtml(data);
        const papers = selectPapers(data, filters);
        filters.page = Math.min(filters.page, Math.max(1, Math.ceil(papers.length / pageSize)));
        document.getElementById('researchCount').textContent = `${papers.length} 条已收录进展`;
        document.getElementById('researchResultNote').textContent = (filters.q ? '按关键词相关性检索优先，' : '') + (filters.sort === 'recommended' ? '推荐结合文档主题匹配、近期更新与新收录；不代表质量评审。' : filters.sort === 'updated' ? '按版本更新时间排序、筛选；旧论文的新版本会出现。' : '按首次发表时间排序、筛选；版本更新不当成新发表。') + ` 每页 ${pageSize} 条。`;
        document.getElementById('researchResults').innerHTML = papers.length ? papers.slice((filters.page - 1) * pageSize, filters.page * pageSize).map(paperHtml).join('') : emptyHtml(data, loadError, scopeError);
        document.querySelectorAll('[data-topic]').forEach(button => { const active = button.dataset.topic === filters.topic; button.classList.toggle('active', active); button.setAttribute('aria-pressed', String(active)); });
        renderPagination(papers.length); updateUrl();
    }
    async function load() {
        const query = document.getElementById('researchQuery'), period = document.getElementById('researchWindow'), sort = document.getElementById('researchSort'), kind = document.getElementById('researchKind');
        query.value = filters.q; period.value = filters.days; sort.value = filters.sort; kind.value = filters.kind;
        function changed() { filters.q = query.value.trim(); filters.days = period.value; filters.sort = sort.value; filters.kind = kind.value; filters.page = 1; render(); }
        query.addEventListener('input', changed); period.addEventListener('change', changed); sort.addEventListener('change', changed); kind.addEventListener('change', changed);
        document.getElementById('researchFilters').addEventListener('submit', event => { event.preventDefault(); changed(); });
        document.querySelectorAll('[data-topic]').forEach(button => button.addEventListener('click', () => { filters.topic = button.dataset.topic; changed(); }));
        try {
            const response = await fetch('data/research_updates.json', { cache: 'no-store' });
            if (!response.ok) throw new Error('Research data unavailable');
            const result = await response.json();
            if (!validSnapshot(result)) { data = null; scopeError = true; } else { data = result; loadError = false; scopeError = false; }
        } catch (_) { loadError = true; }
        render();
    }
    window.ResearchTracker = { readFilters, selectPapers, bm25Scores, safePaperUrl, safeReleaseUrl, safeSourceUrl, checkedLabel, validSnapshot, statusHtml, topicStatusHtml, sourceStatusHtml, paperHtml, emptyHtml, load, pageSize };
    document.addEventListener('DOMContentLoaded', load);
})();
