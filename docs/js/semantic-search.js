/* Offline topic/intent search. No hosted model, query upload, or inference API. */
(function (global) {
    'use strict';
    // BEGIN DOMAIN CONCEPTS
    const CONCEPTS = [
      {"id":"ocr_free","label":"OCR-free / 无OCR理解","query":["不用ocr","无需ocr","不依赖ocr","无ocr","ocr-free","without ocr","直接理解pdf","直接读取pdf","直接读图","端到端文档理解"],"document":["ocr-free","without ocr","end-to-end document understanding","donut","nougat","pix2struct","purely visual language understanding"],"topics":["vlm"]},
      {"id":"multipage","label":"跨页与长文档","query":["跨页","多页","跨文档","多文档","长文档","long document","multi-page","multi page","multi-document","long-context"],"document":["multi-page","multi page","cross-page","cross page","long document","long-context","multi-document","document collections"],"topics":["docrag","rag","docqa"]},
      {"id":"evidence","label":"证据与可验证性","query":["证据","依据","出处","可验证","可追溯","不解释","答对但","grounded","grounding","evidence","citation","attribution","faithfulness"],"document":["evidence","grounded","grounding","verifiable","citation","attribution","faithfulness","unanswerable","evidence localization"],"topics":["eval","docrag","rag"]},
      {"id":"doc_rag","label":"文档检索与RAG","query":["文档检索","检索增强","跨页证据","知识库","document retrieval","document rag","retrieval augmented","retrieve evidence","检索推理"],"document":["retrieval-augmented","retrieval augmented","document retrieval","multimodal retrieval","rag","retrieval and reasoning","retrieval-augmented generation"],"topics":["rag","docrag"]},
      {"id":"layout","label":"版面与阅读顺序","query":["版面","阅读顺序","文档布局","结构恢复","layout analysis","document layout","reading order","layout-aware"],"document":["layout analysis","document layout","reading order","layout-aware","layout detection","layoutlm","page segmentation"],"topics":["layout"]},
      {"id":"ocr","label":"文字识别","query":["文字识别","文本识别","识字","ocr","text recognition","character recognition","text spotting"],"document":["ocr","text recognition","character recognition","text spotting","text detection"],"topics":["ocr"]},
      {"id":"table","label":"表格结构与问答","query":["表格","单元格","行列","电子表格","table","tabular","spreadsheet","cell relationships"],"document":["table","tabular","spreadsheet","table question answering","cell structure","row and column"],"topics":["table"]},
      {"id":"chart","label":"图表理解","query":["图表","图形问答","chart","plot understanding"],"document":["chart","plot understanding","chart question answering","chartqa","infographic"],"topics":["table"]},
      {"id":"handwriting","label":"手写识别","query":["手写","笔迹","handwriting","handwritten"],"document":["handwriting","handwritten","htr","casia"],"topics":["ocr"]},
      {"id":"multilingual","label":"多语言与低资源","query":["多语言","跨语言","低资源","multilingual","cross-lingual","low-resource"],"document":["multilingual","cross-lingual","low-resource","low resource","non-latin"],"topics":["ocr"]},
      {"id":"evaluation","label":"评测与可靠性","query":["评测","基准","可靠性","幻觉","不确定","拒答","答对但","不解释依据","benchmark","evaluation","robustness","hallucination","uncertainty"],"document":["benchmark","evaluation","robustness","hallucination","uncertainty","unanswerable","docvqa","ocrbench","docbench"],"topics":["eval"]},
      {"id":"efficient","label":"效率与成本","query":["高效","轻量","效率","开销","成本","压缩","延迟","efficient","efficiency","lightweight","latency","compression","token cost"],"document":["efficient","efficiency","lightweight","latency","compression","token cost","computational cost","complexity-aware"],"topics":[]}
    ];
    // END DOMAIN CONCEPTS
    const STOPWORDS = new Set(('a an and are as at be been by can could did do does for from how i in into is it its may model models of on or our that the their these they this to using use used uses was we were what when where which who why will with without would you your document documents paper papers method methods approach approaches study studies understanding new based system systems research find search looking want need learn about tell me').split(' '));
    const displayName = '主题/意图增强检索';
    let index = null;
    let loadPromise = null;

    function normalize(value) {
        return String(value ?? '').normalize('NFKC').toLowerCase().replace(/[‐‑‒–—−_-]+/g, ' ').replace(/\s+/g, ' ').trim();
    }
    function tokenize(value) {
        const words = normalize(value).match(/[a-z0-9]+(?:\.[a-z0-9]+)*|[\p{Script=Han}]+/gu) || [];
        return words.flatMap(word => {
            if (/\p{Script=Han}/u.test(word)) return word.length > 1 ? Array.from({length: word.length - 1}, (_, i) => word.slice(i, i + 2)) : [word];
            return word.length > 1 && !STOPWORDS.has(word) ? [word] : [];
        });
    }
    function contains(text, phrase) {
        const needle = normalize(phrase);
        if (!needle) return false;
        if (/\p{Script=Han}/u.test(needle)) return text.replace(/\s+/g, '').includes(needle.replace(/\s+/g, ''));
        const escaped = needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        return new RegExp(`(^|[^a-z0-9])${escaped}($|[^a-z0-9])`, 'u').test(text);
    }
    function conceptsForQuery(query) {
        const text = normalize(query).slice(0, 600);
        let result = CONCEPTS.filter(concept => concept.query.some(phrase => contains(text, phrase)));
        if (result.some(concept => concept.id === 'ocr_free')) result = result.filter(concept => concept.id !== 'ocr');
        return result;
    }
    function textFields(item) {
        const array = value => Array.isArray(value) ? value.map(String) : value ? [String(value)] : [];
        return {
            title: normalize(item?.title),
            tags: normalize([...array(item?.tags), ...array(item?.category), ...array(item?.categories), ...array(item?.subcategory), ...array(item?.subcategories), ...array(item?.topics)].join(' ')),
            body: normalize(String(item?.abstract || '').slice(0, 7000)),
            authors: normalize(array(item?.authors).join(' ')),
            identity: normalize([item?.bibKey, item?.arxiv, item?.repo].filter(Boolean).join(' '))
        };
    }
    function sourceKey(item) {
        let arxiv = String(item?.arxiv || '').replace(/^arxiv:/i, '').replace(/v\d+$/i, '');
        if (!arxiv && String(item?.id || '').startsWith('arxiv:')) arxiv = String(item.id).slice(6).replace(/v\d+$/i, '');
        if (!arxiv) {
            const found = String(item?.url || '').match(/^https:\/\/(?:export\.)?arxiv\.org\/(?:abs|pdf)\/(.+?)(?:\.pdf)?$/);
            if (found) arxiv = found[1].replace(/v\d+$/i, '');
        }
        if (/^(?:\d{4}\.\d{4,5}|[a-z.-]+\/\d{7})$/i.test(arxiv)) return `arxiv:${arxiv.toLowerCase()}`;
        if (typeof item?.id === 'string' && item.id.startsWith('github:')) return item.id.toLowerCase();
        if (item?.bibKey) return `bib:${String(item.bibKey)}`;
        return `title:${normalize(item?.title)}`;
    }
    function fingerprint(item) {
        const fields = [String(item?.title || ''), String(item?.abstract || '').slice(0,7000), String(item?.updated || ''),
            Array.isArray(item?.tags) ? item.tags.join('|') : '', Array.isArray(item?.topics) ? item.topics.join('|') : '',
            String(item?.category || ''), Array.isArray(item?.categories) ? item.categories.join('|') : ''];
        const text = JSON.stringify(fields);
        let hash = 2166136261;
        for (let i=0; i<text.length; i++) { hash ^= text.charCodeAt(i); hash = Math.imul(hash,16777619); }
        return (hash >>> 0).toString(16).padStart(8,'0');
    }
    function itemConceptScore(fields, item, concept) {
        const titleHits = concept.document.filter(term => contains(fields.title, term)).length;
        const otherHits = concept.document.filter(term => contains(`${fields.tags} ${fields.body}`, term)).length;
        const topics = new Set([item?.category, ...(Array.isArray(item?.categories) ? item.categories : []), ...(Array.isArray(item?.topics) ? item.topics : [])]);
        const topic = concept.topics.some(value => topics.has(value));
        const strength = titleHits ? Math.min(1, .8 + titleHits * .1) : otherHits ? Math.min(.85,.5+otherHits*.12) : topic ? .24 : 0;
        return strength;
    }
    function cosine(left, right) {
        if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) return 0;
        let dot=0, a=0, b=0;
        for(let i=0;i<left.length;i++){dot += left[i]*right[i];a += left[i]*left[i];b += right[i]*right[i];}
        return a && b ? dot / Math.sqrt(a*b) : 0;
    }
    function projectQuery(query, concepts) {
        if (!index) return null;
        const counts = new Map();
        tokenize(query).forEach(term=>counts.set(term,(counts.get(term)||0)+1));
        concepts.forEach(concept=>{
            counts.set(`__concept_${concept.id}`,2);
            concept.document.forEach(phrase=>tokenize(phrase).forEach(term=>counts.set(term,(counts.get(term)||0)+.35)));
        });
        const vector = new Array(index.dimensions).fill(0);
        let known = 0;
        for(const [term, count] of counts){
            const position=index.positions.get(term);
            if(position===undefined)continue;
            known++;
            const weight=(1+Math.log(Math.max(1,count)))*index.idf[position];
            for(let j=0;j<vector.length;j++)vector[j]+=weight*index.projection[position][j];
        }
        return known ? vector : null;
    }
    function rank(items, query) {
        const result = new Map();
        if (!Array.isArray(items)) return result;
        const cleanQuery=normalize(query).slice(0,600);
        if(!cleanQuery)return result;
        const terms=[...new Set(tokenize(cleanQuery))];
        const concepts=conceptsForQuery(cleanQuery);
        if(!terms.length&&!concepts.length)return result;
        const documents=items.map(item=>{
            const fields=textFields(item);
            const titleTerms=new Set(tokenize(fields.title));
            const otherTerms=new Set(tokenize(`${fields.tags} ${fields.body} ${fields.authors} ${fields.identity}`));
            return {item,fields,titleTerms,otherTerms};
        });
        const termFrequency = new Map(terms.map(term=>[term,documents.filter(doc=>doc.titleTerms.has(term)||doc.otherTerms.has(term)).length]));
        const queryVector=projectQuery(cleanQuery,concepts);
        for(const {item,fields,titleTerms,otherTerms} of documents){
            const exactTitle=!!fields.title&&(fields.title===cleanQuery || (cleanQuery.length>16 && cleanQuery.includes(fields.title) && fields.title.length>16));
            let lexical=0, covered=0;
            for(const term of terms){
                const titleHit=titleTerms.has(term), otherHit=otherTerms.has(term);
                if(!titleHit&&!otherHit)continue;
                covered++;
                const idf=Math.log(1+(items.length+.5)/(termFrequency.get(term)+.5));
                lexical += idf * (titleHit ? 2.2 : .6);
            }
            const coverage=terms.length?covered/terms.length:0;
            const matches=concepts.map(concept=>({concept,strength:itemConceptScore(fields,item,concept)})).filter(match=>match.strength>0);
            const conceptStrength=concepts.length?matches.reduce((sum,x)=>sum+x.strength,0)/concepts.length:0;
            // LSA may rerank anchored results; it cannot invent matches for an unrelated/OOV query.
            if(!exactTitle && !matches.length && (!covered || coverage<.34))continue;
            if(!exactTitle && !matches.length && lexical<.3)continue;
            const entry=index?.documents[sourceKey(item)];
            const indexed=!!(entry&&entry.fingerprints.includes(fingerprint(item)));
            const similarity=indexed&&queryVector?cosine(queryVector,entry.vector):0;
            const lsa=similarity>.24?similarity*1.8:0;
            const titlePhrase=cleanQuery.length>3 && fields.title.includes(cleanQuery) ? 12 : 0;
            const score=exactTitle?1000:Math.min(30,lexical/Math.sqrt(Math.max(1,terms.length)))+conceptStrength*7+titlePhrase+lsa;
            if(score<=0)continue;
            result.set(item,{score,concepts:matches.map(match=>match.concept.label),method:exactTitle?'exact-title':indexed?'lsa+concepts':'concepts+tfidf',exactTitle,indexed});
        }
        return result;
    }
    function setIndex(payload) {
        if(!payload||payload.schemaVersion!==1||payload.scope!=='document-intelligence'||payload.algorithm!=='tfidf-lsa+domain-concepts')return false;
        const dimensions=Number(payload.dimensions);
        if(!Number.isInteger(dimensions)||dimensions<1||dimensions>32||!Array.isArray(payload.terms)||payload.terms.length>3000||!Array.isArray(payload.idf)||!Array.isArray(payload.projection)||typeof payload.documents!=='object'||!payload.documents)return false;
        if(payload.terms.length!==payload.idf.length||payload.terms.length!==payload.projection.length)return false;
        if(!payload.terms.every(term=>typeof term==='string'&&term.length<100)||!payload.idf.every(n=>Number.isFinite(n)&&n>0)||!payload.projection.every(row=>Array.isArray(row)&&row.length===dimensions&&row.every(Number.isFinite)))return false;
        const documents=Object.create(null);
        for(const [key,entry] of Object.entries(payload.documents)){
            if(!entry||!Array.isArray(entry.vector)||entry.vector.length!==dimensions||!entry.vector.every(Number.isFinite)||!Array.isArray(entry.fingerprints)||!entry.fingerprints.every(f=>typeof f==='string'&&/^[a-f0-9]{8}$/.test(f)))continue;
            documents[key]=entry;
        }
        index={dimensions,terms:payload.terms,idf:payload.idf,projection:payload.projection,documents,positions:new Map(payload.terms.map((term,i)=>[term,i]))};
        return true;
    }
    async function load(path='data/semantic_index.json') {
        if(index)return true;
        if(loadPromise)return loadPromise;
        if(path!=='data/semantic_index.json'||typeof global.fetch!=='function')return false;
        loadPromise=(async()=>{
            try {const response=await global.fetch(path,{cache:'no-cache'});return response.ok&&setIndex(await response.json());}
            catch(_){return false;}
            finally{loadPromise=null;}
        })();
        return loadPromise;
    }
    function status(){return{ready:!!index,displayName,method:index?'lsa-tfidf+domain-concepts':'domain-concepts+tfidf',documentCount:index?Object.keys(index.documents).length:0};}
    global.SemanticSearch={rank,load,setIndex,status,sourceKey,fingerprint,tokenize,conceptsForQuery};
})(typeof window!=='undefined'?window:globalThis);
