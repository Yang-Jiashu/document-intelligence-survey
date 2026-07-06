let paperIndex = null;
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
    filteredPapers = [...paperIndex.papers]
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

function renderSummary() {
    const summary = document.getElementById('resultSummary');
    const detail = document.getElementById('resultDetail');
    const categoryName = currentCategory === 'all'
        ? 'All categories'
        : (paperIndex.taxonomy.find(item => item.id === currentCategory)?.title || currentCategory);
    summary.textContent = `${filteredPapers.length} papers`;
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
        const sourceLink = paper.url && !paper.url.includes('arxiv.org') ? paper.url : '';

        return `
            <article class="search-result-card">
                <div class="search-result-main">
                    <div class="paper-header">
                        <h3 class="paper-title">${escapeHtml(paper.title)}</h3>
                        <span class="paper-year">${escapeHtml(paper.year || '-')}</span>
                    </div>
                    <div class="paper-authors">${escapeHtml(paper.authors || 'Unknown authors')}</div>
                    <div class="paper-meta">
                        <span class="paper-venue">${escapeHtml(paper.venue || paper.bibKey)}</span>
                        <span class="paper-stars">${escapeHtml(paper.bibKey)}</span>
                    </div>
                    <div class="paper-tags">
                        ${categories.map(item => `<span class="paper-tag">${escapeHtml(item)}</span>`).join('')}
                        ${subcategories.map(item => `<span class="paper-tag">${escapeHtml(item)}</span>`).join('')}
                    </div>
                </div>
                <div class="paper-actions search-result-actions">
                    ${arxivLink ? `<a href="${arxivLink}" target="_blank" class="paper-btn primary">arXiv</a>` : ''}
                    ${sourceLink ? `<a href="${escapeHtml(sourceLink)}" target="_blank" class="paper-btn secondary">Source</a>` : ''}
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
    const response = await fetch('data/paper_index.json');
    paperIndex = await response.json();

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
