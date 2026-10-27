const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const now = Date.parse('2026-10-28T12:00:00Z');
const nodes = {};
function node(id) {
    return nodes[id] ||= { innerHTML: '', textContent: '', value: '', listeners: {}, addEventListener(event, callback) { this.listeners[event] = callback; }, querySelectorAll() { return []; } };
}
const context = vm.createContext({
    document: { addEventListener() {}, getElementById: node, querySelectorAll() { return []; } },
    window: { location: { search: '' }, history: { replaceState(_state, _title, url) { context.lastUrl = url; } } },
    URL, URLSearchParams,
    Date: class extends Date { static now() { return now; } },
    fetch: async () => { throw new Error('Offline network is forbidden'); }
});
vm.runInContext(fs.readFileSync('docs/js/research.js', 'utf8'), context);
const tracker = context.window.ResearchTracker;
const topics = ['search', 'ads', 'recommendation'].map(id => ({ id, status: 'fresh', lastChecked: '2026-10-28T10:00:00Z', sourceUrl: 'https://export.arxiv.org/api/query?search_query=example' }));
const paper = {
    id: 'arxiv:2610.12345', arxiv: '2610.12345', version: 1,
    title: 'Neural Search for Retrieval', abstract: 'An abstract about dense retrieval and relevance.', authors: ['Example Author'],
    published: '2026-10-26T00:00:00Z', updated: '2026-10-26T00:00:00Z',
    url: 'https://arxiv.org/abs/2610.12345', pdfUrl: 'https://arxiv.org/pdf/2610.12345',
    topics: ['search'], matchedTerms: { search: ['dense retrieval'] }, sourceName: 'arXiv'
};
const revised = { ...paper, id: 'arxiv:2401.12345', arxiv: '2401.12345', title: 'Old Recommendation Study', topics: ['recommendation'], published: '2024-01-01T00:00:00Z', updated: '2026-10-28T00:00:00Z', version: 3 };
const newer = { ...paper, id: 'arxiv:2610.22222', arxiv: '2610.22222', title: 'Advertising Auctions', authors: ['Other Researcher'], topics: ['ads'], published: '2026-10-27T00:00:00Z', updated: '2026-10-27T00:00:00Z' };
const data = { schemaVersion: 1, status: 'refreshed', topics, papers: [paper, revised, newer], lastAttempt: '2026-10-28T10:00:00Z', lastSuccessfulCheck: '2026-10-28T10:00:00Z', nextScheduledCheck: '2026-10-29' };
const base = { topic: 'all', q: '', days: '30', sort: 'published', page: 1 };
function titles(selection, snapshot = data) { return Array.from(tracker.selectPapers(snapshot, { ...base, ...selection }, now), p => p.title); }

assert.deepStrictEqual(titles({}), ['Advertising Auctions', 'Neural Search for Retrieval']);
assert.deepStrictEqual(titles({ sort: 'updated' }), ['Old Recommendation Study', 'Advertising Auctions', 'Neural Search for Retrieval']);
assert.deepStrictEqual(titles({ topic: 'search' }), [paper.title]);
assert.deepStrictEqual(titles({ q: 'dense relevance' }), [newer.title, paper.title]);
assert.deepStrictEqual(titles({ q: 'example author' }), [paper.title]);
assert.deepStrictEqual(titles({ q: '2610.22222' }), [newer.title]);
assert.deepStrictEqual(titles({ q: 'nonexistent' }), []);
assert.deepStrictEqual(titles({ days: 'all', topic: 'recommendation' }), [revised.title]);
assert.deepStrictEqual(titles({ topic: 'recommendation' }), []);
assert.deepStrictEqual(titles({ sort: 'updated', topic: 'recommendation' }), [revised.title]);
assert.deepStrictEqual(titles({}, { ...data, papers: [{ ...paper, published: 'invalid' }, { ...paper, published: '2027-01-01' }] }), []);
assert.strictEqual(tracker.pageSize, 20);

const parsed = tracker.readFilters('?topic=ads&q=auction&days=7&sort=updated&page=3');
assert.strictEqual(parsed.topic, 'ads');
assert.strictEqual(parsed.q, 'auction');
assert.strictEqual(parsed.days, '7');
assert.strictEqual(parsed.sort, 'updated');
assert.strictEqual(parsed.page, 3);
const invalid = tracker.readFilters('?topic=constructor&days=-2&sort=score&page=-4');
assert.strictEqual(invalid.topic, 'all');
assert.strictEqual(invalid.days, '30');
assert.strictEqual(invalid.sort, 'published');
assert.strictEqual(invalid.page, 1);

assert.strictEqual(tracker.safePaperUrl(paper.url), paper.url);
for (const url of ['javascript:alert(1)', 'https://arxiv.org.evil.test/abs/2610.12345', 'http://arxiv.org/abs/2610.12345', 'https://evil@arxiv.org/abs/2610.12345', 'https://arxiv.org/abs/2610.12345?next=evil', 'https://arxiv.org/abs/"><img src=x>']) {
    assert.strictEqual(tracker.safePaperUrl(url), '', url);
}
assert.strictEqual(tracker.safeSourceUrl('https://rss.arxiv.org/rss/cs.IR'), 'https://rss.arxiv.org/rss/cs.IR');
assert.strictEqual(tracker.safeSourceUrl('https://evil.test/feed'), '');
const unsafe = tracker.paperHtml({ ...paper, title: '<img src=x onerror=alert(1)>', authors: ['<script>bad</script>'], abstract: '<svg onload=alert(1)>', url: 'javascript:bad()', pdfUrl: 'https://evil.test/pdf', matchedTerms: { search: ['<b>bad</b>'] } });
assert.match(unsafe, /&lt;img/);
assert.match(unsafe, /&lt;script&gt;/);
assert.match(unsafe, /&lt;svg/);
assert.doesNotMatch(unsafe, /<img|<script|<svg|href="javascript|href="https:\/\/evil/);
assert.match(tracker.paperHtml(paper), /首次发表 2026-10-26/);
assert.doesNotMatch(tracker.paperHtml(paper), /版本更新/);
assert.match(tracker.paperHtml(revised), /首次发表 2024-01-01/);
assert.match(tracker.paperHtml(revised), /版本更新 2026-10-28 · v3/);
assert.match(tracker.paperHtml({ ...paper, abstract: 'A'.repeat(500) }), /阅读完整摘要/);

const partial = { ...data, status: 'partial', lastAttempt: '2026-10-28T10:00:00Z', lastSuccessfulCheck: '2026-10-25T10:00:00Z', topics: [{ ...topics[0], status: 'stale', lastChecked: '2026-10-24T10:00:00Z', error: 'secret diagnostic' }, ...topics.slice(1)] };
assert.match(tracker.statusHtml(partial), /部分来源抓取失败/);
assert.match(tracker.statusHtml(partial), /最近尝试：2026-10-28 18:00（北京时间）/);
assert.match(tracker.statusHtml(partial), /最近完整核验：2026-10-25 18:00（北京时间）/);
assert.match(tracker.topicStatusHtml(partial), /最后核验：2026-10-24 18:00（北京时间）/);
assert.strictEqual(tracker.checkedLabel('2026-10-27T16:23:53Z'), '2026-10-28 00:23（北京时间）');
assert.strictEqual(tracker.checkedLabel(null), '尚未核验');
const capped = { ...data, topics: [{ ...topics[0], resultLimit: 100, truncated: true }, ...topics.slice(1)] };
assert.match(tracker.topicStatusHtml(capped), /每次最多核验最新 100 条候选，非全量/);
assert.doesNotMatch(tracker.topicStatusHtml({ ...data, topics: [{ ...topics[0], resultLimit: '<script>bad</script>' }] }), /<script>/);
assert.match(tracker.paperHtml({ ...paper, published: '2026-10-27T16:23:53Z', updated: '2026-10-27T16:23:53Z' }), /首次发表 2026-10-27/);
assert.match(tracker.topicStatusHtml(partial), /抓取失败 · 保留旧数据/);
assert.doesNotMatch(tracker.topicStatusHtml(partial), /secret diagnostic/);
assert.match(tracker.emptyHtml(partial), /不能据此判断没有新研究/);
assert.match(tracker.emptyHtml(data), /当前筛选下没有已收录论文/);
assert.match(tracker.statusHtml(null, true), /不代表没有新论文/);
assert.match(tracker.statusHtml(null), /正在读取研究进展/);
assert.match(tracker.statusHtml({ ...data, status: 'mystery' }), /research-status warning/);

(async () => {
    let resolveFetch;
    context.fetch = () => new Promise(resolve => { resolveFetch = resolve; });
    const loading = tracker.load();
    node('researchQuery').value = 'retrieval';
    node('researchQuery').listeners.input();
    assert.match(node('researchStatus').innerHTML, /正在读取研究进展/);
    assert.match(node('researchResults').innerHTML, /筛选条件会在加载后生效/);
    resolveFetch({ ok: true, json: async () => data });
    await loading;
    assert.strictEqual(node('researchCount').textContent, '2 篇已收录论文');
    assert.match(context.lastUrl, /q=retrieval/);
    node('researchQuery').value = '';
    node('researchQuery').listeners.input();
    context.fetch = async () => ({ ok: true, json: async () => data });
    await tracker.load();
    assert.match(node('researchResults').innerHTML, /Advertising Auctions/);
    assert.doesNotMatch(node('researchResults').innerHTML, /Old Recommendation Study/);
    assert.strictEqual(node('researchCount').textContent, '2 篇已收录论文');
    assert.strictEqual(context.lastUrl, 'research.html');
    context.fetch = async () => { throw new Error('Synthetic timeout'); };
    await tracker.load();
    assert.match(node('researchStatus').innerHTML, /暂时无法加载/);
    assert.match(node('researchResults').innerHTML, /Advertising Auctions/); // Preserve a previously loaded view.
    console.log('Research stream UI tests OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
