const assert = require('assert');
const fs = require('fs');
const vm = require('vm');

const container = { innerHTML: '' };
const context = vm.createContext({
    document: {
        addEventListener() {},
        getElementById(id) {
            assert.strictEqual(id, 'sotaContainer');
            return container;
        }
    },
    window: { addEventListener() {} }
});
vm.runInContext(fs.readFileSync('docs/js/app.js', 'utf8'), context);

const benchmark = {
    id: 'docvqa',
    name: 'DocVQA',
    task: 'Document QA',
    metric: 'ANLS',
    updateMode: 'auto-scraped',
    sourceName: 'RRC',
    sourceUrl: 'https://rrc.cvc.uab.es/?ch=17&com=evaluation&task=1',
    lastChecked: '2026-06-10',
    leader: { model: 'Verified model', score: 95.5 },
    history: [{ model: 'Verified model', score: 95.5 }]
};

function render(overrides = {}) {
    context.data = {
        lastChecked: '2026-10-26',
        status: 'partially refreshed snapshot',
        benchmarks: [{ ...benchmark, ...overrides }]
    };
    vm.runInContext('renderLiveSOTA(data)', context);
    return container.innerHTML;
}

const stale = render({
    checkStatus: 'stale',
    lastCheckAttempt: '2026-10-26',
    lastCheckError: 'Private transport diagnostic <urlopen error timed out>'
});
assert.match(stale, /Latest snapshot attempt: 2026-10-26/);
assert.match(stale, /Last verified 2026-06-10/);
assert.match(stale, /class="sota-check-stale">Stale/);
assert.match(stale, /Refresh failed on 2026-10-26; showing last verified data/);
assert.match(stale, /Verified model/);
assert.match(stale, /95\.5/);
assert.doesNotMatch(stale, /Private transport diagnostic|urlopen/);
assert.doesNotMatch(stale, /Last verified 2026-10-26/);

const http = render({
    checkStatus: 'fresh',
    lastChecked: '2026-10-27',
    lastCheckSourceUrl: 'http://rrc.cvc.uab.es/?ch=17&com=evaluation&task=1',
    lastCheckWarning: 'unencrypted official HTTP fallback'
});
assert.match(http, /Last verified 2026-10-27/);
assert.match(http, /Source checked over HTTP/);
assert.match(http, /href="http:\/\/rrc\.cvc\.uab\.es\/\?ch=17&amp;com=evaluation&amp;task=1"/);
assert.doesNotMatch(http, /sota-check-stale|Refresh failed/);

const https = render({
    checkStatus: 'fresh',
    lastCheckSourceUrl: benchmark.sourceUrl
});
assert.doesNotMatch(https, /Source checked over HTTP|sota-check-stale|Refresh failed/);
assert.match(https, /href="https:\/\/rrc\.cvc\.uab\.es\/\?ch=17&amp;com=evaluation&amp;task=1"/);

// A global attempt date must never stand in for a benchmark verification date.
assert.match(render({ lastChecked: undefined }), /Last verified Unknown/);
assert.match(render({ lastCheckSourceUrl: 'https://example.org/?q="quote"&x=1' }), /q=&quot;quote&quot;&amp;x=1/);
console.log('SOTA source status rendering test OK');
