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
            foundAt: '2026-07-11',
            arxivIds: []
        }]
    };
    filteredPapers = getSearchPapers();
    renderResults();
`);

assert.strictEqual(vm.runInThisContext('filteredPapers.length'), 1);
assert.match(nodes.resultsContainer.innerHTML, /Verified WeChat article/);
assert.match(nodes.resultsContainer.innerHTML, /公众号 · 机器之心/);

assert.strictEqual(
    vm.runInThisContext("paperMatchesQuery(filteredPapers[0], '公众号')"),
    true
);

console.log('Search source rendering test OK');
