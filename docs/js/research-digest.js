(function () {
    'use strict';
    const topics = { ocr: 'OCR / 解析', layout: '版面', table: '表格 / 图表', docqa: '文档问答', docrag: '文档 RAG', eval: '评测' };
    const repos = new Set(['paddlepaddle/paddleocr', 'opendatalab/mineru', 'docling-project/docling']);
    const clean = value => String(value ?? '').replace(/\s+/gu, ' ').trim();
    const escape = value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
    const timestamp = value => Number.isFinite(Date.parse(value)) ? Date.parse(value) : 0;
    const utc = value => timestamp(value) ? new Date(value).toISOString().replace(/\.\d{3}Z$/, 'Z') : '';
    const date = value => utc(value).slice(0, 10) || '日期未提供';
    function checked(value) {
        if (!timestamp(value)) return '尚未成功读取';
        return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(value)) + '（北京时间）';
    }
    function safeUrl(value, kind, repo) {
        try {
            const u = new URL(value);
            if (u.protocol !== 'https:' || u.username || u.password || u.port || u.search || u.hash) return '';
            if (kind !== 'release') return u.hostname === 'arxiv.org' && /^\/abs\/(?:\d{4}\.\d{4,5}(?:v\d+)?|[a-z.-]+\/\d{7}(?:v\d+)?)$/.test(u.pathname) ? u.href : '';
            const parts = u.pathname.split('/').filter(Boolean), identity = parts.slice(0, 2).join('/').toLowerCase();
            return u.hostname === 'github.com' && repos.has(identity) && (!repo || identity === String(repo).toLowerCase()) && parts[2] === 'releases' && (parts.length === 3 || (parts[3] === 'tag' && parts.length >= 5)) ? u.href : '';
        } catch (_) { return ''; }
    }
    function validSnapshot(value) {
        return value?.schemaVersion === 2 && value.scope === 'document-intelligence' && Array.isArray(value.papers);
    }
    function validDigest(value) {
        return value?.schemaVersion === 1 && value.scope === 'document-intelligence' && Array.isArray(value.items);
    }
    function sourceData(item) {
        if (!item || !['paper', 'release'].includes(item.kind) || typeof item.id !== 'string' || typeof item.title !== 'string' || typeof item.abstract !== 'string') return null;
        const kind = item.kind;
        const url = safeUrl(item.url, kind, item.repo);
        const topicIds = [...new Set(Array.isArray(item.topics) ? item.topics : [])].sort();
        if (!clean(item.title) || item.title.length > 1500 || !clean(item.abstract) || item.abstract.length > 100000 || !url || !topicIds.length || topicIds.some(id => !Object.hasOwn(topics, id))
            || !timestamp(item.published) || !timestamp(item.updated) || timestamp(item.published) > timestamp(item.updated) || timestamp(item.updated) > Date.now() + 300000) return null;
        const arxiv = item.id.slice(6);
        if (kind === 'paper' && (!item.id.startsWith('arxiv:') || !/^(?:\d{4}\.\d{4,5}|[a-z][a-z.\-]+\/\d{7})$/.test(arxiv) || item.url !== 'https://arxiv.org/abs/' + arxiv || (item.arxiv && item.arxiv !== arxiv))) return null;
        if (kind === 'release') {
            let decoded;
            try { decoded = decodeURIComponent(item.url); } catch (_) { return null; }
            if (typeof item.repo !== 'string' || !repos.has(item.repo.toLowerCase()) || !item.id.startsWith('github:' + item.repo + ':') || !/^[1-9]\d*$/.test(item.id.split(':').at(-1)) || !item.url.startsWith('https://github.com/' + item.repo + '/releases/tag/') || decoded.split('/').some(part => part === '.' || part === '..')) return null;
        }
        const version = item.version === undefined ? 1 : item.version;
        if (kind === 'paper' && (!Number.isInteger(version) || version < 1 || version > 10000)) return null;
        // Keep exactly the backend's canonical field order for its SHA-256 cache key.
        return { abstract: clean(item.abstract), id: String(item.id), kind, published: utc(item.published), title: clean(item.title), topics: topicIds,
            updated: utc(item.updated), url: item.url, version: kind === 'release' ? 0 : version };
    }
    async function fingerprint(source) {
        if (!globalThis.crypto?.subtle || typeof TextEncoder === 'undefined') return '';
        try {
            const buffer = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(source)));
            return Array.from(new Uint8Array(buffer), byte => byte.toString(16).padStart(2, '0')).join('');
        } catch (_) { return ''; }
    }
    function sourceText(value) {
        const entities = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ' };
        return clean(String(value || '').replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/<[^>]*>/g, ' ').replace(/&(#x[\da-f]+|#\d+|amp|lt|gt|quot|apos|nbsp);/gi, (raw, code) => {
            if (code[0] !== '#') return entities[code.toLowerCase()] || raw;
            const point = code[1].toLowerCase() === 'x' ? parseInt(code.slice(2), 16) : parseInt(code.slice(1), 10);
            return point > 0 && point <= 0x10ffff ? String.fromCodePoint(point) : raw;
        }));
    }
    function excerpt(source, limit = 330) {
        const text = sourceText(source.abstract).replace(/(?:https?:\/\/|www\.)\S+/g, '').replace(/[#*_`~>]/g, '').trim();
        return text ? text.slice(0, limit) + (text.length > limit ? '…' : '') : '官方来源未提供摘要，请查看原文。';
    }
    async function prepare(snapshot, digest) {
        if (!validSnapshot(snapshot)) return { items: [], snapshot: null, digest: null };
        const sources = snapshot.papers.map(item => ({ source: sourceData(item), rank: Number(item.rankScore) || Number(item.relevanceScore) || 0 })).filter(item => item.source);
        const byId = new Map(sources.map(item => [item.source.id, item]));
        const usable = validDigest(digest) ? digest : null;
        const selected = [], seen = new Set();
        if (usable) for (const item of usable.items) {
            if (!item || typeof item !== 'object') continue;
            const origin = byId.get(item.id);
            if (!origin || seen.has(item.id)) continue;
            const source = origin.source, hash = await fingerprint(source);
            const sameOrigin = clean(item.title) === source.title && safeUrl(item.url, source.kind) === source.url;
            const ai = item.summaryKind === 'ai-abstract-summary' && sameOrigin && typeof item.summary === 'string' && clean(item.summary);
            const matching = Boolean(ai && hash && item.sourceFingerprint === hash && item.summarySourceFingerprint === hash && !item.stale && item.summaryStatus === 'ready' && item.sourceBasis === (source.kind === 'release' ? 'official-release-notes' : 'arxiv-abstract'));
            const evidence = matching && Array.isArray(item.evidenceQuotes) ? item.evidenceQuotes.filter(quote => typeof quote === 'string' && clean(quote) && sourceText(source.abstract).includes(clean(quote))).slice(0, 3) : [];
            const current = matching && evidence.length > 0;
            const contributions = current && Array.isArray(item.contributions) ? item.contributions.filter(value => typeof value === 'string' && clean(value)).slice(0, 3) : [];
            selected.push({ source, summary: current ? clean(item.summary) : excerpt(source), ai: current,
                generatedAt: current ? item.summaryGeneratedAt : '', evidence, contributions,
                oldSummary: ai && !current ? clean(item.summary) : '', oldGeneratedAt: ai && !current ? item.summaryGeneratedAt : '' });
            seen.add(item.id);
        }
        // A missing/old digest must not hide fresh, validated source records.
        sources.sort((a, b) => b.rank - a.rank || timestamp(b.source.updated) - timestamp(a.source.updated));
        for (const { source } of sources) if (!seen.has(source.id)) {
            selected.push({ source, summary: excerpt(source), ai: false, contributions: [], evidence: [], oldSummary: '' });
            seen.add(source.id);
        }
        return { items: selected, snapshot, digest: usable && usable.status === 'ready' && selected.some(item => item.oldSummary) ? { ...usable, status: 'stale' } : usable };
    }
    function stateText(digest, available = true) {
        if (!available) return '来源数据暂时无法读取，请稍后重试。';
        if (!digest) return '自动发现继续运行；智能摘要状态暂不可读取，先展示来源摘要。';
        if (digest.status === 'quota' && ['forbidden', 'unauthorized', '401', '403'].includes(String(digest.budget?.reason))) return 'AI 账号认证未通过或权限待检查；保留待处理内容，来源摘要照常展示。';
        if (digest.status === 'quota' && digest.budget?.reason === 'budget') return '已达到本地每日智能整理上限；待处理内容留待下次尝试，来源摘要照常展示。';
        if (digest.status === 'quota' && digest.budget?.reason !== 'quota') return '智能整理已暂停；保留待处理内容，来源摘要照常展示。';
        const states = {
            unconfigured: '免费自动发现已接入；中文 AI 摘要待配置，当前展示来源节选。',
            quota: '免费 AI 额度已用完；待处理内容留待下次尝试，来源摘要照常展示。',
            fallback: '本次 AI 整理暂未完成；保留已有摘要，其余展示来源节选。',
            stale: '部分摘要等待更新；旧摘要单独标注，当前来源摘要照常展示。',
            ready: digest.mode === 'cached' ? '已复用摘要缓存；仅新增或修订内容需要再次整理。' : '本次精选已整理；AI 内容仅依据来源摘要或官方版本说明。'
        };
        return states[digest.status] || '自动发现已接入；智能整理状态待确认，先展示来源摘要。';
    }
    function cardHtml(item, compact = false) {
        const { source } = item;
        const revision = timestamp(source.updated) > timestamp(source.published);
        const summary = compact && item.summary.length > 170 ? item.summary.slice(0, 170) + '…' : item.summary;
        const label = item.ai ? 'AI 摘要 · 仅基于来源' : '原始摘要节选';
        return `<article class="digest-card"><div class="digest-card-meta"><span>${source.topics.map(id => topics[id]).join(' · ')}</span><span>${source.kind === 'release' ? '官方版本' : 'arXiv 预印本'}</span></div><h3><a href="${escape(source.url)}" target="_blank" rel="noreferrer">${escape(source.title)} <span aria-hidden="true">↗</span></a></h3><div class="digest-dates">${source.kind === 'release' ? '版本发布' : '首次发表'} ${escape(date(source.published))}${revision ? ` · ${source.kind === 'release' ? '说明更新' : '版本更新'} ${escape(date(source.updated))}` : ''}</div><span class="digest-summary-kind">${label}${item.ai && item.generatedAt ? ` · ${escape(date(item.generatedAt))}` : ''}</span><p class="digest-summary">${escape(summary)}</p>${!compact && item.contributions.length ? `<ul class="digest-contributions">${item.contributions.map(value => `<li>${escape(value)}</li>`).join('')}</ul>` : ''}${!compact && item.evidence.length ? `<details class="digest-evidence"><summary>查看摘要依据</summary>${item.evidence.map(value => `<blockquote>${escape(value)}</blockquote>`).join('')}<a href="${escape(source.url)}" target="_blank" rel="noreferrer">核对原文 ↗</a></details>` : ''}${item.oldSummary ? `<details class="digest-old"><summary>旧版 AI 摘要${item.oldGeneratedAt ? ` · ${escape(date(item.oldGeneratedAt))}` : ''} · 待更新</summary><p>${escape(item.oldSummary)}</p><small>来源已修订或缓存未通过本次核对；上方展示当前来源节选。</small></details>` : ''}</article>`;
    }
    function render(payload, compact = false) {
        const count = compact ? 3 : 8, { snapshot, digest } = payload;
        const status = stateText(digest, Boolean(snapshot));
        const pending = Number.isInteger(digest?.pendingCount) && digest.pendingCount > 0 ? ` ${digest.pendingCount} 条待智能整理。` : '';
        const heading = compact ? '' : '<div class="digest-heading"><div><span class="digest-kicker">THE READING LIST</span><h2 id="digestTitle">每日阅读精选</h2></div><span>先筛选，再阅读</span></div>';
        const empty = '<p class="digest-empty">暂时没有可显示的来源记录。可前往研究进展查看各来源状态。</p>';
        return `${heading}<p class="digest-state" role="status">${escape(status + pending)}</p>${!compact ? '<p class="digest-note">按文档主题与新近程度筛选。来源节选与 AI 摘要分别标注；精选不代表论文质量评审。</p>' : ''}<div class="digest-list${compact ? ' compact' : ''}">${payload.items.length ? payload.items.slice(0, count).map(item => cardHtml(item, compact)).join('') : empty}</div>${compact ? '<a class="digest-more" href="research.html#researchDigest">查看阅读精选与全部进展 ↗</a>' : ''}`;
    }
    async function load() {
        const home = document.getElementById('dynamicOverviewContainer'), research = document.getElementById('researchDigest');
        if (!home && !research) return;
        const mount = payload => {
            if (home) home.innerHTML = render(payload, true);
            if (research) research.innerHTML = render(payload);
            const badge = document.getElementById('dynamicLastUpdated');
            if (badge) badge.textContent = checked(payload.snapshot?.lastAttempt);
        };
        if (home) home.innerHTML = '<p class="digest-state" role="status">正在读取来源与阅读清单…</p>';
        if (research) research.innerHTML = '<h2 id="digestTitle">每日阅读精选</h2><p class="digest-state" role="status">正在读取来源与阅读清单…</p>';
        const read = async path => { const response = await fetch(path, { cache: 'no-store' }); if (!response.ok) throw new Error('Source unavailable'); return response.json(); };
        const [sources, digest] = await Promise.allSettled([read('data/research_updates.json'), read('data/research_digest.json')]);
        try { mount(await prepare(sources.status === 'fulfilled' ? sources.value : null, digest.status === 'fulfilled' ? digest.value : null)); }
        catch (_) { mount({ items: [], snapshot: null, digest: null }); }
    }
    window.ResearchDigest = { safeUrl, sourceData, fingerprint, validSnapshot, validDigest, prepare, stateText, cardHtml, render, load };
    document.addEventListener('DOMContentLoaded', load);
})();
