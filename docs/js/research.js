(function () {
    'use strict';
    const topicNames = { search: '搜索', ads: '广告', recommendation: '推荐' };
    const pageSize = 20;
    let data = null;
    let filters = readFilters(window.location.search);
    let loadError = false;

    function escapeHtml(value) {
        return String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
    }

    function safePaperUrl(value) {
        try {
            const url = new URL(value);
            return url.protocol === 'https:' && url.hostname === 'arxiv.org' && !url.username && !url.password && !url.port
                && !url.search && !url.hash
                && /^\/(abs|pdf)\/(?:\d{4}\.\d{4,5}(?:v\d+)?|[a-z.-]+\/\d{7}(?:v\d+)?)(?:\.pdf)?$/.test(url.pathname)
                ? url.href : '';
        } catch (_) { return ''; }
    }

    function safeSourceUrl(value) {
        try {
            const url = new URL(value);
            return url.protocol === 'https:' && ['arxiv.org', 'export.arxiv.org', 'rss.arxiv.org'].includes(url.hostname)
                && !url.username && !url.password && !url.port ? url.href : '';
        } catch (_) { return ''; }
    }

    function timestamp(value) {
        const result = Date.parse(value);
        return Number.isFinite(result) ? result : 0;
    }

    function dateLabel(value) {
        return timestamp(value) ? String(value).slice(0, 10) : '尚未核验';
    }

    function checkedLabel(value) {
        if (!timestamp(value)) return '尚未核验';
        const parts = new Intl.DateTimeFormat('zh-CN', {
            timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit', hourCycle: 'h23'
        }).formatToParts(new Date(value));
        const part = type => parts.find(item => item.type === type).value;
        return `${part('year')}-${part('month')}-${part('day')} ${part('hour')}:${part('minute')}（北京时间）`;
    }

    function readFilters(search) {
        const params = new URLSearchParams(search);
        const topic = params.get('topic') || 'all';
        const period = params.get('days') || '30';
        return {
            q: (params.get('q') || '').trim(),
            topic: Object.hasOwn(topicNames, topic) ? topic : 'all',
            days: ['7', '30', '90', 'all'].includes(period) ? period : '30',
            sort: params.get('sort') === 'updated' ? 'updated' : 'published',
            page: Math.max(1, Math.floor(Number(params.get('page')) || 1))
        };
    }

    function selectPapers(snapshot, selection, now = Date.now()) {
        const terms = String(selection.q || '').toLowerCase().split(/\s+/).filter(Boolean);
        const cutoff = selection.days === 'all' ? 0 : now - Number(selection.days) * 86400000;
        return (Array.isArray(snapshot?.papers) ? snapshot.papers : []).filter(paper => {
            const topics = Array.isArray(paper.topics) ? paper.topics : [];
            if (selection.topic !== 'all' && !topics.includes(selection.topic)) return false;
            const relevantDate = timestamp(paper[selection.sort]);
            if (!relevantDate || relevantDate < cutoff || relevantDate > now + 86400000) return false;
            const text = [paper.title, paper.abstract, ...(Array.isArray(paper.authors) ? paper.authors : []), paper.arxiv].join(' ').toLowerCase();
            return terms.every(term => text.includes(term));
        }).sort((a, b) => timestamp(b[selection.sort]) - timestamp(a[selection.sort])
            || timestamp(b.published) - timestamp(a.published)
            || String(a.title).localeCompare(String(b.title)));
    }

    function hasSourceFailure(snapshot) {
        return !snapshot || snapshot.status !== 'refreshed'
            || Object.keys(topicNames).some(id => !(Array.isArray(snapshot.topics) && snapshot.topics.some(topic => topic.id === id && topic.status === 'fresh')));
    }

    function statusHtml(snapshot, failed = false) {
        if (failed) return '<div class="research-status warning"><strong>进展数据暂时无法加载</strong><span>请稍后重试。此状态不代表没有新论文。</span></div>';
        if (!snapshot) return '<div class="research-status"><span>正在读取研究进展…</span></div>';
        const warning = hasSourceFailure(snapshot);
        const labels = { refreshed: '每日抓取已完成', partial: '部分来源抓取失败', unavailable: '本次抓取未完成', 'not-yet-checked': '等待首次核验' };
        return `<div class="research-status${warning ? ' warning' : ''}"><strong>${escapeHtml(labels[snapshot.status] || '来源状态待确认')}</strong>
            <span>最近尝试：${escapeHtml(checkedLabel(snapshot.lastAttempt))}</span>
            <span>最近完整核验：${escapeHtml(checkedLabel(snapshot.lastSuccessfulCheck))}</span>
            <span>下次计划：${escapeHtml(snapshot.nextScheduledCheck || '待确认')}</span>
            ${warning ? '<span>保留已核验记录；请查看各领域的最后核验日期。</span>' : ''}</div>`;
    }

    function topicStatusHtml(snapshot) {
        const topics = Array.isArray(snapshot?.topics) ? snapshot.topics : [];
        return Object.entries(topicNames).map(([id, name]) => {
            const topic = topics.find(item => item.id === id) || {};
            const fresh = topic.status === 'fresh';
            const source = safeSourceUrl(topic.sourceUrl);
            const label = fresh ? '已核验' : topic.status === 'stale' ? '抓取失败 · 保留旧数据' : '尚未核验';
            const cap = Number.isInteger(topic.resultLimit) && topic.resultLimit > 0 ? topic.resultLimit : null;
            return `<div class="research-source-card${fresh ? '' : ' stale'}"><div class="research-source-title"><span>${name}</span><span class="research-source-state">${label}</span></div>
                <span class="research-check-date">最后核验：${escapeHtml(checkedLabel(topic.lastChecked))}</span>
                ${cap ? `<span class="research-check-date">每次最多核验最新 ${cap} 条候选${topic.truncated === true ? '，非全量' : ''}</span>` : ''}
                ${source ? `<a href="${escapeHtml(source)}" target="_blank" rel="noreferrer">查看官方来源 ↗</a>` : ''}</div>`;
        }).join('');
    }

    function paperHtml(paper) {
        const url = safePaperUrl(paper.url);
        const pdf = safePaperUrl(paper.pdfUrl);
        const topics = (Array.isArray(paper.topics) ? paper.topics : []).filter(id => Object.hasOwn(topicNames, id));
        const authors = Array.isArray(paper.authors) ? paper.authors : [];
        const abstract = String(paper.abstract || '官方来源尚未提供摘要。');
        const preview = abstract.length > 360 ? abstract.slice(0, 360) + '…' : abstract;
        const revision = timestamp(paper.updated) > timestamp(paper.published);
        const matched = topics.flatMap(id => Array.isArray(paper.matchedTerms?.[id]) ? paper.matchedTerms[id] : []).slice(0, 6);
        return `<article class="research-paper"><div class="research-paper-topline">${topics.map(id => `<span class="research-topic-tag ${id}">${topicNames[id]}</span>`).join('')}<span class="research-preprint">arXiv 预印本</span></div>
            <h3>${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${escapeHtml(paper.title)}</a>` : escapeHtml(paper.title || '未命名论文')}</h3>
            <div class="research-paper-authors">${escapeHtml(authors.slice(0, 8).join(', '))}${authors.length > 8 ? ` 等 ${authors.length} 位作者` : ''}</div>
            <div class="research-paper-meta"><span>首次发表 ${escapeHtml(dateLabel(paper.published))}</span>${revision ? `<span>版本更新 ${escapeHtml(dateLabel(paper.updated))}${Number.isInteger(paper.version) && paper.version > 1 ? ` · v${paper.version}` : ''}</span>` : ''}<span>${escapeHtml(paper.arxiv || '')}</span></div>
            <div class="research-paper-abstract"><p>${escapeHtml(preview)}</p>${abstract.length > 360 ? `<details><summary>阅读完整摘要</summary><p class="research-abstract-rest">${escapeHtml(abstract)}</p></details>` : ''}</div>
            <div class="research-paper-footer"><div class="research-paper-links">${url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">论文原文 ↗</a>` : ''}${pdf ? `<a href="${escapeHtml(pdf)}" target="_blank" rel="noreferrer">PDF ↗</a>` : ''}</div>${matched.length ? `<span class="research-match">主题关键词：${escapeHtml([...new Set(matched)].join(' · '))}</span>` : ''}</div>
            </article>`;
    }

    function emptyHtml(snapshot, failed = false) {
        if (!snapshot && !failed) return '<div class="research-empty"><h3>正在读取研究进展…</h3><p>正在加载已核验记录，筛选条件会在加载后生效。</p></div>';
        if (failed || hasSourceFailure(snapshot)) return '<div class="research-empty"><h3>暂时没有可显示的已核验记录</h3><p>部分来源尚未成功核验，不能据此判断没有新研究。已有记录会继续保留，也可调整领域、关键词或时间范围查看。</p></div>';
        return '<div class="research-empty"><h3>当前筛选下没有已收录论文</h3><p>可以清除关键词、切换领域或扩大时间范围。自动发现按关键词覆盖来源，并不代表该领域没有其他新论文。</p></div>';
    }

    function updateUrl() {
        const params = new URLSearchParams();
        if (filters.q) params.set('q', filters.q);
        if (filters.topic !== 'all') params.set('topic', filters.topic);
        if (filters.days !== '30') params.set('days', filters.days);
        if (filters.sort !== 'published') params.set('sort', filters.sort);
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
        node.querySelectorAll('[data-page]').forEach(button => button.addEventListener('click', () => {
            filters.page = Number(button.dataset.page);
            render();
            document.getElementById('feedTitle').scrollIntoView({ behavior: 'smooth', block: 'start' });
        }));
    }

    function render() {
        document.getElementById('researchStatus').innerHTML = statusHtml(data, loadError);
        document.getElementById('researchTopics').innerHTML = topicStatusHtml(data);
        const papers = selectPapers(data, filters);
        filters.page = Math.min(filters.page, Math.max(1, Math.ceil(papers.length / pageSize)));
        document.getElementById('researchCount').textContent = `${papers.length} 篇已收录论文`;
        document.getElementById('researchResultNote').textContent = `${filters.sort === 'updated' ? '按版本更新时间排序、筛选；旧论文的新版本会出现。' : '按首次发表时间排序、筛选；版本更新不会被当成新发表。'} 每页 ${pageSize} 篇。`;
        document.getElementById('researchResults').innerHTML = papers.length
            ? papers.slice((filters.page - 1) * pageSize, filters.page * pageSize).map(paperHtml).join('')
            : emptyHtml(data, loadError);
        document.querySelectorAll('[data-topic]').forEach(button => {
            const active = button.dataset.topic === filters.topic;
            button.classList.toggle('active', active);
            button.setAttribute('aria-pressed', String(active));
        });
        renderPagination(papers.length);
        updateUrl();
    }

    async function load() {
        const query = document.getElementById('researchQuery');
        const period = document.getElementById('researchWindow');
        const sort = document.getElementById('researchSort');
        query.value = filters.q;
        period.value = filters.days;
        sort.value = filters.sort;
        function changed() {
            filters.q = query.value.trim();
            filters.days = period.value;
            filters.sort = sort.value;
            filters.page = 1;
            render();
        }
        query.addEventListener('input', changed);
        period.addEventListener('change', changed);
        sort.addEventListener('change', changed);
        document.getElementById('researchFilters').addEventListener('submit', event => { event.preventDefault(); changed(); });
        document.querySelectorAll('[data-topic]').forEach(button => button.addEventListener('click', () => {
            filters.topic = button.dataset.topic;
            changed();
        }));
        try {
            const response = await fetch('data/research_updates.json', { cache: 'no-store' });
            if (!response.ok) throw new Error('Research data unavailable');
            const result = await response.json();
            if (result.schemaVersion !== 1 || !Array.isArray(result.topics) || !Array.isArray(result.papers)) throw new Error('Unexpected research snapshot');
            data = result;
        } catch (_) {
            loadError = true;
        }
        render();
    }

    window.ResearchTracker = { readFilters, selectPapers, safePaperUrl, safeSourceUrl, checkedLabel, statusHtml, topicStatusHtml, paperHtml, emptyHtml, load, pageSize };
    document.addEventListener('DOMContentLoaded', load);
})();
