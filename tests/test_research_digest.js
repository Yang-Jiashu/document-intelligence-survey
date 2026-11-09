const assert = require('assert');
const fs = require('fs');
const vm = require('vm');
const { webcrypto, createHash } = require('crypto');
const nodes = {};
const node = id => nodes[id] ||= { innerHTML: '', textContent: '' };
const context = vm.createContext({ window: {}, document: { getElementById: id => nodes[id] || null, addEventListener() {} }, crypto: webcrypto, TextEncoder, URL, Intl, Date: class extends Date { static now() { return Date.parse('2026-11-09T12:00:00Z'); } }, fetch: async () => { throw new Error('Network forbidden'); } });
vm.runInContext(fs.readFileSync('docs/js/research-digest.js', 'utf8'), context);
const ui = context.window.ResearchDigest;
const source = { id: 'arxiv:2610.12345', kind: 'paper', title: 'Document Parsing', abstract: 'We align document regions with evidence. We evaluate scanned pages.', published: '2026-10-20T00:00:00Z', updated: '2026-10-28T12:00:00Z', topics: ['layout', 'ocr'], version: 2, url: 'https://arxiv.org/abs/2610.12345', rankScore: 9 };
const snapshot = { schemaVersion: 2, scope: 'document-intelligence', papers: [source], lastAttempt: '2026-10-29T03:16:00Z' };
const digest = items => ({ schemaVersion: 1, scope: 'document-intelligence', status: 'ready', mode: 'cloudflare', items, pendingCount: 0 });

(async () => {
    const canonical = ui.sourceData(source);
    const hash = await ui.fingerprint(canonical);
    const expected = createHash('sha256').update(JSON.stringify({ abstract: source.abstract, id: source.id, kind: 'paper', published: source.published, title: source.title, topics: ['layout', 'ocr'], updated: source.updated, url: source.url, version: 2 })).digest('hex');
    assert.strictEqual(hash, expected, 'cache fingerprint must match the backend canonical field order');
    assert.strictEqual(ui.safeUrl('javascript:alert(1)', 'paper'), '');
    assert.strictEqual(ui.safeUrl('https://arxiv.org.evil/abs/2610.12345', 'paper'), '');
    assert.strictEqual(ui.safeUrl('https://arxiv.org/abs/2610.12345?redirect=evil', 'paper'), '');
    assert.strictEqual(ui.safeUrl('https://github.com/evil/project/releases/tag/v1', 'release'), '');
    assert.strictEqual(ui.safeUrl('https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v3', 'release', 'opendatalab/mineru'), '');
    assert.ok(ui.safeUrl('https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v3', 'release'));
    assert.strictEqual(ui.sourceData({ ...source, published: 'not-a-date' }), null);
    assert.strictEqual(ui.sourceData({ ...source, updated: '2027-01-01T00:00:00Z' }), null);
    assert.strictEqual(ui.sourceData({ ...source, id: 'arxiv:2610.99999' }), null);

    const entry = { ...source, sourceFingerprint: hash, summarySourceFingerprint: hash, summaryKind: 'ai-abstract-summary', summaryStatus: 'ready', sourceBasis: 'arxiv-abstract', summaryGeneratedAt: '2026-10-29T03:20:00Z', summary: '通过区域对齐保留文档证据。', contributions: ['提供区域对齐方法。'], evidenceQuotes: ['We align document regions with evidence.', 'Unsupported invented evidence.'] };
    const ready = await ui.prepare(snapshot, digest([entry]));
    assert.strictEqual(ready.items[0].ai, true);
    assert.deepStrictEqual(Array.from(ready.items[0].evidence), ['We align document regions with evidence.']);
    const rendered = ui.render(ready);
    assert.match(rendered, /AI 摘要 · 仅基于来源/);
    assert.match(rendered, /首次发表 2026-10-20 · 版本更新 2026-10-28/);
    assert.match(rendered, /查看摘要依据/);
    assert.doesNotMatch(rendered, /Unsupported invented evidence/);
    assert.strictEqual((await ui.prepare(snapshot, digest([{ ...entry, evidenceQuotes: ['An invented ungrounded quote.'] }]))).items[0].ai, false);

    // A changed source must not present the cached model result as current.
    const changed = await ui.prepare({ ...snapshot, papers: [{ ...source, abstract: 'A revised document study.' }] }, digest([entry]));
    assert.strictEqual(changed.items[0].ai, false);
    const changedHtml = ui.render(changed);
    assert.match(changedHtml, /原始摘要节选/);
    assert.match(changedHtml, /A revised document study/);
    assert.match(changedHtml, /旧版 AI 摘要 · 2026-10-29 · 待更新/);
    assert.doesNotMatch(changedHtml, /提供区域对齐方法/);

    const malformed = await ui.prepare(snapshot, digest([{ ...entry, url: 'https://evil.example/malicious', summary: '<img src=x onerror=alert(1)>' }, { ...entry, id: 'unrelated', title: 'Invented paper' }]));
    const malformedHtml = ui.render(malformed);
    assert.match(malformedHtml, /Document Parsing/);
    assert.doesNotMatch(malformedHtml, /evil.example|Invented paper|<img|onerror/);

    // Excerpts come from the validated source, never model-provided fallback text.
    const fallback = await ui.prepare(snapshot, { ...digest([{ ...entry, summaryKind: 'source-excerpt', summary: 'Invented fallback text' }]), status: 'unconfigured' });
    assert.match(ui.render(fallback), /中文 AI 摘要待配置/);
    assert.match(ui.render(fallback), /We align document regions/);
    assert.doesNotMatch(ui.render(fallback), /Invented fallback text|旧版 AI 摘要/);
    assert.match(ui.stateText({ status: 'quota', budget: { reason: 'quota' } }), /免费 AI 额度已用完/);
    assert.match(ui.stateText({ status: 'quota', budget: { reason: 'quota' } }), /下次尝试/);
    assert.doesNotMatch(ui.stateText({ status: 'quota' }), /免费 AI 额度已用完/);
    assert.match(ui.stateText({ status: 'quota', budget: { reason: 'forbidden' } }), /账号认证未通过或权限待检查/);
    assert.doesNotMatch(ui.stateText({ status: 'quota', budget: { reason: 'forbidden' } }), /额度已用完/);
    assert.match(ui.stateText({ status: 'quota', budget: { reason: 'budget' } }), /本地每日智能整理上限/);
    assert.doesNotMatch(ui.stateText({ status: 'quota', budget: { reason: 'budget' } }), /免费 AI 额度已用完/);
    assert.match(ui.render(await ui.prepare(snapshot, null)), /智能摘要状态暂不可读取/);
    assert.strictEqual((await ui.prepare({ ...snapshot, scope: 'other' }, digest([entry]))).items.length, 0);

    const xss = await ui.prepare({ ...snapshot, papers: [{ ...source, title: '<script>alert(1)</script>', abstract: '<svg onload=alert(1)>source</svg>' }] }, null);
    const safeHtml = ui.render(xss);
    assert.match(safeHtml, /&lt;script&gt;/);
    assert.doesNotMatch(safeHtml, /<script|<svg/);

    // No Web Crypto means safe excerpt fallback, not an unverified AI summary.
    context.crypto = undefined;
    const noCrypto = await ui.prepare(snapshot, digest([entry]));
    assert.strictEqual(noCrypto.items[0].ai, false);
    context.crypto = webcrypto;

    node('dynamicOverviewContainer'); node('dynamicLastUpdated'); node('researchDigest');
    context.fetch = async path => ({ ok: true, json: async () => path.endsWith('research_updates.json') ? snapshot : { ...digest([]), status: 'unconfigured' } });
    await ui.load();
    assert.match(nodes.dynamicOverviewContainer.innerHTML, /Document Parsing/);
    assert.match(nodes.researchDigest.innerHTML, /每日阅读精选/);
    assert.match(nodes.dynamicLastUpdated.textContent, /2026\/10\/29 11:16/);
    context.fetch = async () => { throw new Error('Synthetic timeout with secret detail'); };
    await ui.load();
    assert.match(nodes.researchDigest.innerHTML, /来源数据暂时无法读取/);
    assert.doesNotMatch(nodes.researchDigest.innerHTML, /secret detail/);
    console.log('Research digest provenance, fallback and rendering tests OK');
})().catch(error => { console.error(error); process.exitCode = 1; });
