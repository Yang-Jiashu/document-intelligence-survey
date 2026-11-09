const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const nodes = { resultsContainer: { innerHTML: '' } };
global.document = {
    addEventListener() {},
    getElementById(id) {
        return nodes[id] || { innerHTML: '', textContent: '', addEventListener() {} };
    },
    querySelectorAll() { return []; }
};
global.window = {
    history: { replaceState() {} },
    location: { search: '' },
    scrollTo() {}
};

vm.runInThisContext(fs.readFileSync('docs/js/search.js', 'utf8'));
vm.runInThisContext(`
    filteredPapers = [{
        title: 'Demo',
        authors: 'Author',
        year: 2026,
        venue: 'arXiv',
        arxiv: '2601.00001',
        category: 'ocr',
        sourceType: 'auto',
        isDocumentIntelligence: false,
        sourceMentions: [{
            account: 'PaperWeekly',
            articleTitle: 'Demo article',
            url: 'https://mp.weixin.qq.com/s/demo'
        }]
    }];
    currentPage = 1;
    renderResults();
`);

assert.match(nodes.resultsContainer.innerHTML, /https:\/\/arxiv\.org\/abs\/2601\.00001/);
assert.match(nodes.resultsContainer.innerHTML, /公众号 · PaperWeekly/);
assert.match(nodes.resultsContainer.innerHTML, /https:\/\/mp\.weixin\.qq\.com\/s\/demo/);
assert.match(nodes.resultsContainer.innerHTML, /WeChat source/);

vm.runInThisContext(`
    paperIndex = { papers: [], taxonomy: [] };
    dynamicPaperIndex = {
        papers: [],
        verifiedWechatArticles: [{
            account: '机器之心',
            articleTitle: 'Verified article',
            url: 'https://mp.weixin.qq.com/s/verified',
            foundAt: '2026-07-12',
            publishedDate: '2026-02-03',
            arxivIds: [],
            githubUrls: ['https://github.com/PaddlePaddle/PaddleOCR'],
            category: 'ocr',
            categories: ['ocr'],
            isDocumentIntelligence: true
        }]
    };
    filteredPapers = getSearchPapers();
    renderResults();
`);

assert.strictEqual(vm.runInThisContext('filteredPapers.length'), 1);
assert.match(nodes.resultsContainer.innerHTML, /Verified WeChat article/);
assert.match(nodes.resultsContainer.innerHTML, /公众号 · 机器之心/);
assert.match(nodes.resultsContainer.innerHTML, /https:\/\/github\.com\/PaddlePaddle\/PaddleOCR/);
assert.match(nodes.resultsContainer.innerHTML, />GitHub</);
assert.strictEqual(vm.runInThisContext('filteredPapers[0].year'), 2026);

assert.strictEqual(
    vm.runInThisContext("paperMatchesQuery(filteredPapers[0], '公众号')"),
    true
);

const generated = JSON.parse(fs.readFileSync('docs/data/dynamic_papers.json', 'utf8'));
// The retained source snapshot has no promised article count. Validate the
// actual evidence rather than requiring invented entries to reach a quota.
assert.ok(generated.verifiedWechatArticles.length > 0);
assert.strictEqual(new Set(generated.verifiedWechatArticles.map(article => article.url)).size, generated.verifiedWechatArticles.length);
for (const article of generated.verifiedWechatArticles) {
    assert.strictEqual(new URL(article.url).hostname, 'mp.weixin.qq.com');
    assert.ok(article.account && article.articleTitle && article.provider);
    assert.match(article.publishedDate, /^20\d{2}-\d{2}-\d{2}$/);
    assert.match(article.foundAt, /^20\d{2}-\d{2}-\d{2}$/);
    assert.strictEqual(new URL(article.publicationDateEvidenceUrl).protocol, 'https:');
    assert.ok((article.arxivIds || []).length || (article.githubUrls || []).length);
}

console.log('Search source rendering test OK');
