'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../docs/js/semantic-search.js'), 'utf8');

function create(fetch) {
    const context = {fetch};
    vm.runInNewContext(source, context, {filename: 'semantic-search.js'});
    return context.SemanticSearch;
}
const papers = [
    {title:'Donut: OCR-free Document Understanding', arxiv:'2111.15664', topics:['vlm']},
    {title:'Cross-page Evidence Localization for Document Retrieval', arxiv:'2601.10001', topics:['docrag']},
    {title:'Benchmarking Evidence Grounding and Faithfulness', arxiv:'2601.10002', topics:['eval']},
    {title:'High Accuracy OCR Text Recognition', arxiv:'2601.10003', topics:['ocr']},
    {title:'Document Layout Analysis', arxiv:'2601.10004', topics:['layout']}
];
function ranked(api, query) {
    return [...api.rank(papers, query)].sort((left, right) => right[1].score-left[1].score);
}
function payload(api, item=papers[0]) {
    return {
        schemaVersion:1, scope:'document-intelligence', algorithm:'tfidf-lsa+domain-concepts',
        dimensions:2, terms:['__concept_ocr_free','donut'], idf:[1,1], projection:[[1,0],[1,0]],
        documents:{[api.sourceKey(item)]:{fingerprints:[api.fingerprint(item)],vector:[1,0]}}
    };
}
async function main() {
    let requests=0;
    const api=create(() => { requests++; throw new Error('Unexpected network request'); });
    assert.equal(api.status().ready,false);
    assert.equal(api.status().displayName,'主题/意图增强检索');
    for(const query of ['不用OCR直接理解PDF','无需 OCR 直接读取 PDF','without OCR']) {
        const first=ranked(api,query)[0];
        assert.equal(first[0],papers[0],`${query} should prefer OCR-free understanding`);
        assert(first[1].concepts.includes('OCR-free / 无OCR理解'));
        assert(!first[1].concepts.includes('文字识别'),'OCR-free should not expand to generic OCR');
    }
    const evidence=ranked(api,'跨页证据定位')[0];
    assert.equal(evidence[0],papers[1]);
    assert(evidence[1].concepts.includes('文档检索与RAG'));
    const reliability=ranked(api,'模型答对但不解释依据')[0];
    assert.equal(reliability[0],papers[2],'Answer correctness without evidence should prioritize evaluation');
    assert(reliability[1].concepts.includes('评测与可靠性'));
    assert.equal(ranked(api,'document retrieval')[0][0],papers[1]);
    const exact=ranked(api,papers[3].title)[0];
    assert.equal(exact[0],papers[3]);
    assert.equal(exact[1].method,'exact-title');
    assert.equal(exact[1].score,1000);
    for(const query of ['', 'the and with', '紫色独角兽做奶茶', 'xylophonic quasar banana']) {
        assert.equal(api.rank(papers,query).size,0,`Unrelated query must not force matches: ${query}`);
    }
    assert.equal(api.rank(null,'OCR').size,0);
    assert.equal(requests,0,'Ranking and initialization are fully offline');

    assert.equal(api.sourceKey({arxiv:'2301.12345v3'}),'arxiv:2301.12345');
    assert.equal(api.sourceKey({url:'https://arxiv.org/pdf/2301.12345v2.pdf'}),'arxiv:2301.12345');
    assert.equal(api.sourceKey({id:'github:Docling-Project/Docling:123'}),'github:docling-project/docling:123');
    assert.equal(api.sourceKey({bibKey:'Donut2022'}),'bib:Donut2022');
    const unicode={title:'跨页 Evidence 📚',abstract:'Grounded answers with citation.',updated:'2026-11-09',tags:['RAG','中文'],topics:['docrag'],category:'Retrieval',categories:['RAG','Evaluation']};
    assert.equal(api.fingerprint(unicode),'4fd5ec55','Builder and browser must use matching UTF-16 fingerprint');
    assert.equal(api.fingerprint({...unicode,rank:99,lastSeen:'later'}),api.fingerprint(unicode),'Bookkeeping must not invalidate the index');
    assert.notEqual(api.fingerprint({...unicode,abstract:'New evidence.'}),api.fingerprint(unicode));
    assert.equal(api.setIndex({}),false);
    assert.equal(api.setIndex({...payload(api),projection:[[Infinity,0],[1,0]]}),false);
    assert.equal(api.setIndex(payload(api)),true);
    assert.equal(api.status().documentCount,1);
    assert.equal(api.rank(papers,'不用OCR直接理解PDF').get(papers[0]).indexed,true);
    const changed={...papers[0],abstract:'A revised abstract needs an updated index.'};
    const stale=api.rank([changed],'不用OCR直接理解PDF').get(changed);
    assert.equal(stale.indexed,false,'Changed content must fall back instead of using stale LSA vectors');
    assert.equal(stale.method,'concepts+tfidf');
    assert.equal(requests,0);

    const loads=[];
    const loading=create(async(url,options)=>{loads.push({url,options});return {ok:true,json:async()=>payload(api)};});
    assert.equal(await loading.load('https://example.com/model'),false);
    assert.equal(loads.length,0,'Only the approved static index path may be requested');
    assert.deepEqual(await Promise.all([loading.load(),loading.load()]),[true,true]);
    assert.equal(loads.length,1,'Concurrent initial loads share a single static request');
    assert.equal(loads[0].url,'data/semantic_index.json');
    assert.equal(await loading.load(),true);
    assert.equal(loads.length,1);
    const offline=create(async()=>{throw new Error('Offline');});
    assert.equal(await offline.load(),false);
    assert.equal(ranked(offline,'不用OCR直接理解PDF')[0][0],papers[0],'Static load failure retains intent matching');
    console.log('semantic search: bilingual intent, exact titles, stale-index fallback, and static-only loading passed');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
