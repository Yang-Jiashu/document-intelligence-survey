let paperIndex = null;
let dynamicPaperIndex = null;
let filteredPapers = [];
let currentPage = 1;
let currentQuery = '';
let currentCategory = 'all';
const pageSize = 25;

function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function paperMatchesQuery(paper, query) {
    if (!query) return true;
    const sourceMentions = getWechatSourceMentions(paper);
    const isWechatArticle = paper.sourceType === 'wechat';
    const haystack = [
        paper.title,
        paper.authors,
        paper.venue,
        paper.year,
        paper.bibKey,
        paper.category,
        ...(paper.categories || []),
        paper.subcategory,
        ...(paper.subcategories || []),
        ...(paper.topics || []),
        ...(paper.tags || []),
        paper.arxiv,
        paper.github,
        paper.sourceType,
        paper.sourceType === 'auto' ? 'auto-discovered' : '',
        paper.isDocumentIntelligence === false ? 'source-only outside document intelligence other' : '',
        isWechatArticle ? 'wechat 微信 公众号 wechat source' : '',
        ...(isWechatArticle ? sourceMentions.flatMap(mention => [mention.account, mention.articleTitle]) : []),
    ].join(' ').toLowerCase();
    return haystack.includes(query.toLowerCase());
}

function paperMatchesCategory(paper, category) {
    if (!category || category === 'all') return true;
    return paper.category === category || (paper.categories || []).includes(category);
}

function updateUrl() {
    const params = new URLSearchParams();
    if (currentQuery) params.set('q', currentQuery);
    if (currentCategory && currentCategory !== 'all') params.set('category', currentCategory);
    const next = params.toString() ? `search.html?${params.toString()}` : 'search.html';
    window.history.replaceState({}, '', next);
}

function applySearch() {
    filteredPapers = getSearchPapers()
        .filter(paper => paperMatchesCategory(paper, currentCategory))
        .filter(paper => paperMatchesQuery(paper, currentQuery))
        .sort((a, b) => {
            const yearDiff = (b.year || 0) - (a.year || 0);
            if (yearDiff) return yearDiff;
            return String(a.title).localeCompare(String(b.title));
        });

    const maxPage = Math.max(1, Math.ceil(filteredPapers.length / pageSize));
    currentPage = Math.min(currentPage, maxPage);
    renderResults();
    renderPagination();
    renderSummary();
    updateUrl();
}

function getSearchPapers() {
    const curatedMentionMap = dynamicPaperIndex?.curatedSourceMentions || {};
    const curated = (paperIndex.papers || []).map(paper => {
        const normalizedArxiv = String(paper.arxiv || '').replace(/v\d+$/i, '');
        return {
            ...paper,
            sourceType: paper.sourceType || 'curated',
            sourceMentions: [
                ...(Array.isArray(paper.sourceMentions) ? paper.sourceMentions : []),
                ...(Array.isArray(curatedMentionMap[normalizedArxiv]) ? curatedMentionMap[normalizedArxiv] : [])
            ]
        };
    });
    const dynamic = dynamicPaperIndex && Array.isArray(dynamicPaperIndex.papers)
        ? dynamicPaperIndex.papers.map(paper => ({
            ...paper,
            sourceType: 'auto',
            bibKey: paper.bibKey || '',
            stars: paper.stars || 0
        }))
        : [];
    const verifiedWechatArticles = Array.isArray(dynamicPaperIndex?.verifiedWechatArticles)
        ? dynamicPaperIndex.verifiedWechatArticles
            .map((article, index) => ({
                id: `wechat:${index}`,
                title: article.articleTitle || '微信公众号文章',
                authors: article.account || '微信公众号',
                venue: '微信公众号',
                year: Number(String(article.publishedDate || '').slice(0, 4)) || '',
                category: article.category || 'other',
                categories: Array.isArray(article.categories) && article.categories.length ? article.categories : [article.category || 'other'],
                tags: ['Verified WeChat source', ...(article.tags || [])],
                arxiv: Array.isArray(article.arxivIds) && article.arxivIds.length === 1 ? article.arxivIds[0] : '',
                github: Array.isArray(article.githubUrls) && article.githubUrls.length ? article.githubUrls[0] : '',
                sourceType: 'wechat',
                isDocumentIntelligence: article.isDocumentIntelligence === true,
                sourceMentions: [article]
            }))
        : [];
    return curated.concat(dynamic, verifiedWechatArticles);
}

function getWechatSourceMentions(paper) {
    const mentions = Array.isArray(paper.sourceMentions) ? paper.sourceMentions : [];
    const urls = new Set();
    return mentions.filter(mention => {
        const url = String(mention?.url || '');
        const isWechatArticleUrl = /^https:\/\/mp\.weixin\.qq\.com\/(?:s\/|s\?)/i.test(url);
        const isVerifiedPublisherUrl = paper.sourceType === 'wechat' && /^https:\/\//i.test(url);
        if ((!isWechatArticleUrl && !isVerifiedPublisherUrl) || urls.has(url)) return false;
        urls.add(url);
        return true;
    });
}

function renderSummary() {
    const summary = document.getElementById('resultSummary');
    const detail = document.getElementById('resultDetail');
    const categoryName = currentCategory === 'all'
        ? 'All categories'
        : (paperIndex.taxonomy.find(item => item.id === currentCategory)?.title || currentCategory);
    summary.textContent = `${filteredPapers.length} results`;
    detail.textContent = currentQuery
        ? `${categoryName} / "${currentQuery}"`
        : categoryName;
}

function renderResults() {
    const container = document.getElementById('resultsContainer');
    if (!filteredPapers.length) {
        container.innerHTML = '<div class="empty-results">No papers matched the current search.</div>';
        return;
    }

    const start = (currentPage - 1) * pageSize;
    const pageItems = filteredPapers.slice(start, start + pageSize);
    container.innerHTML = pageItems.map(paper => {
        const categories = (paper.categories || [paper.category]).filter(Boolean);
        const subcategories = (paper.subcategories || []).filter(Boolean).slice(0, 3);
        const arxivLink = paper.arxiv ? `https://arxiv.org/abs/${encodeURIComponent(paper.arxiv)}` : '';
        const githubLink = /^https:\/\/github\.com\//i.test(String(paper.github || '')) ? paper.github : '';
        const sourceLink = paper.sourceType !== 'auto' && paper.url && !paper.url.includes('arxiv.org') ? paper.url : '';
        const wechatMentions = getWechatSourceMentions(paper);
        const sourceLabel = paper.sourceType === 'wechat'
            ? '<span class="paper-source-label">Verified WeChat article</span>'
            : paper.sourceType === 'auto'
                ? `<span class="paper-source-label">${paper.isDocumentIntelligence === false ? 'WeChat source' : 'Auto-discovered'}</span>`
                : '';

        return `
            <article class="search-result-card">
                <div class="search-result-main">
                    <div class="paper-header">
                        <h3 class="paper-title">${escapeHtml(paper.title)}</h3>
                        <span class="paper-year">${escapeHtml(paper.year || '-')}</span>
                    </div>
                    <div class="paper-authors">${escapeHtml(paper.authors || 'Unknown authors')}</div>
                    <div class="paper-meta">
                        <span class="paper-venue">${escapeHtml(paper.venue || paper.bibKey || '')}</span>
                        ${paper.bibKey ? `<span class="paper-stars">${escapeHtml(paper.bibKey)}</span>` : ''}
                        ${sourceLabel}
                    </div>
                    <div class="paper-tags">
                        ${categories.map(item => `<span class="paper-tag">${escapeHtml(item)}</span>`).join('')}
                        ${subcategories.map(item => `<span class="paper-tag">${escapeHtml(item)}</span>`).join('')}
                    </div>
                </div>
                <div class="paper-actions search-result-actions">
                    ${arxivLink ? `<a href="${arxivLink}" target="_blank" class="paper-btn primary">arXiv</a>` : ''}
                    ${githubLink ? `<a href="${escapeHtml(githubLink)}" target="_blank" rel="noreferrer" class="paper-btn primary">GitHub</a>` : ''}
                    ${wechatMentions.map(mention => `
                        <a href="${escapeHtml(mention.url)}" target="_blank" rel="noreferrer" class="paper-btn secondary" title="${escapeHtml(mention.articleTitle || '')}">
                            公众号${mention.account && mention.account !== 'Unknown' ? ` · ${escapeHtml(mention.account)}` : ''}
                        </a>
                    `).join('')}
                    ${!wechatMentions.length && sourceLink ? `<a href="${escapeHtml(sourceLink)}" target="_blank" rel="noreferrer" class="paper-btn secondary">Source</a>` : ''}
                </div>
            </article>
        `;
    }).join('');
}

function renderPagination() {
    const container = document.getElementById('pagination');
    const totalPages = Math.max(1, Math.ceil(filteredPapers.length / pageSize));
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }

    const pages = [];
    const start = Math.max(1, currentPage - 2);
    const end = Math.min(totalPages, currentPage + 2);
    for (let page = start; page <= end; page += 1) pages.push(page);

    container.innerHTML = `
        <button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} data-page="${currentPage - 1}">Prev</button>
        ${start > 1 ? '<button class="page-btn" data-page="1">1</button><span class="page-gap">...</span>' : ''}
        ${pages.map(page => `<button class="page-btn ${page === currentPage ? 'active' : ''}" data-page="${page}">${page}</button>`).join('')}
        ${end < totalPages ? `<span class="page-gap">...</span><button class="page-btn" data-page="${totalPages}">${totalPages}</button>` : ''}
        <button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''} data-page="${currentPage + 1}">Next</button>
    `;

    container.querySelectorAll('.page-btn').forEach(button => {
        button.addEventListener('click', () => {
            const nextPage = Number(button.dataset.page);
            if (!Number.isFinite(nextPage)) return;
            currentPage = nextPage;
            renderResults();
            renderPagination();
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
    });
}

function setActiveFilter() {
    document.querySelectorAll('.filter-btn').forEach(button => {
        button.classList.toggle('active', button.dataset.filter === currentCategory);
    });
}

async function loadSearchPage() {
    const [indexResponse, dynamicResponse] = await Promise.all([
        fetch('data/paper_index.json'),
        fetch('data/dynamic_papers.json').catch(() => null)
    ]);
    paperIndex = await indexResponse.json();
    dynamicPaperIndex = dynamicResponse && dynamicResponse.ok ? await dynamicResponse.json() : { papers: [] };

    const params = new URLSearchParams(window.location.search);
    currentQuery = params.get('q') || '';
    currentCategory = params.get('category') || 'all';

    const input = document.getElementById('searchInput');
    input.value = currentQuery;
    input.addEventListener('input', () => {
        currentQuery = input.value.trim();
        currentPage = 1;
        applySearch();
    });
    input.addEventListener('keydown', event => {
        if (event.key === 'Enter') {
            currentQuery = input.value.trim();
            currentPage = 1;
            applySearch();
        }
    });

    document.querySelectorAll('.filter-btn').forEach(button => {
        button.addEventListener('click', () => {
            currentCategory = button.dataset.filter;
            currentPage = 1;
            setActiveFilter();
            applySearch();
        });
    });

    setActiveFilter();
    applySearch();
}

document.addEventListener('DOMContentLoaded', loadSearchPage);
