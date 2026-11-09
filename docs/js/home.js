(function (global) {
    'use strict';

    const stages = {
        perceive: {
            title: 'Read the page.',
            description: 'Recognize text, recover reading order, and turn document pixels into structured content.',
            link: 'Explore OCR methods →',
            href: 'search.html?category=ocr'
        },
        understand: {
            title: 'Understand the document.',
            description: 'Connect text, layout, tables, and visual evidence with document vision-language models.',
            link: 'Explore document VLMs →',
            href: 'search.html?category=vlm'
        },
        reason: {
            title: 'Reason across knowledge.',
            description: 'Retrieve evidence and answer questions across pages and documents with grounded reasoning.',
            link: 'Explore document RAG →',
            href: 'search.html?category=rag'
        }
    };

    function getDocument() {
        return global.document || null;
    }

    function setText(id, value) {
        const element = getDocument()?.getElementById(id);
        if (element) element.textContent = value;
    }

    function renderStats(paperIndexData, papersData, liveSotaData) {
        const indexedPapers = Array.isArray(paperIndexData?.papers) ? paperIndexData.papers : null;
        const curatedPapers = Array.isArray(papersData?.papers) ? papersData.papers : [];
        const taxonomy = Array.isArray(paperIndexData?.taxonomy) ? paperIndexData.taxonomy : [];
        const benchmarkCount = Array.isArray(liveSotaData?.benchmarks)
            ? liveSotaData.benchmarks.length
            : Object.keys(papersData?.sota_history || {}).length;

        setText('atlasPaperCount', (indexedPapers || curatedPapers).length.toLocaleString('en-US'));
        setText('atlasTopicCount', taxonomy.length.toLocaleString('en-US'));
        setText('atlasBenchmarkCount', benchmarkCount.toLocaleString('en-US'));
    }

    function initNavigation(doc) {
        const toggle = doc.getElementById('navToggle');
        const navigation = doc.getElementById('mainNav');
        if (!toggle || !navigation) return;

        function setOpen(open) {
            navigation.classList.toggle('is-open', open);
            toggle.setAttribute('aria-expanded', String(open));
        }

        setOpen(false);
        toggle.addEventListener('click', () => {
            setOpen(toggle.getAttribute('aria-expanded') !== 'true');
        });
        navigation.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => setOpen(false));
        });
        doc.addEventListener('keydown', event => {
            if (event.key === 'Escape' && toggle.getAttribute('aria-expanded') === 'true') {
                setOpen(false);
                toggle.focus();
            }
        });
    }

    function initAtlas(doc) {
        const atlas = doc.getElementById('documentAtlas');
        const panel = doc.getElementById('stagePanel');
        const tabs = Array.from(doc.querySelectorAll('button.atlas-tab[data-stage]'))
            .filter(tab => Object.hasOwn(stages, tab.dataset.stage));
        if (!atlas || !tabs.length) return;

        function selectStage(tab, moveFocus) {
            const name = tab.dataset.stage;
            const stage = stages[name];
            atlas.dataset.stage = name;
            tabs.forEach(item => {
                const selected = item === tab;
                item.setAttribute('aria-selected', String(selected));
                item.tabIndex = selected ? 0 : -1;
            });

            if (!tab.id) tab.id = `atlas-tab-${name}`;
            if (panel) {
                panel.setAttribute('role', 'tabpanel');
                panel.setAttribute('aria-labelledby', tab.id);
                tabs.forEach(item => item.setAttribute('aria-controls', panel.id));
            }

            setText('stageTitle', stage.title);
            setText('stageDescription', stage.description);
            const link = doc.getElementById('stageLink');
            if (link) {
                link.textContent = stage.link;
                link.setAttribute('href', stage.href);
            }
            if (moveFocus) tab.focus();
        }

        tabs.forEach((tab, index) => {
            tab.setAttribute('role', 'tab');
            tab.addEventListener('click', () => selectStage(tab, false));
            tab.addEventListener('keydown', event => {
                let nextIndex;
                if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
                else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
                else if (event.key === 'Home') nextIndex = 0;
                else if (event.key === 'End') nextIndex = tabs.length - 1;
                else return;
                event.preventDefault();
                selectStage(tabs[nextIndex], true);
            });
        });

        selectStage(tabs.find(tab => tab.dataset.stage === atlas.dataset.stage) || tabs[0], false);
    }

    function init() {
        const doc = getDocument();
        if (!doc) return;
        initNavigation(doc);
        initAtlas(doc);
    }

    global.HomeAtlas = Object.assign(global.HomeAtlas || {}, { renderStats });
    const doc = getDocument();
    if (doc?.readyState === 'loading') doc.addEventListener('DOMContentLoaded', init, { once: true });
    else init();
})(typeof window !== 'undefined' ? window : globalThis);
