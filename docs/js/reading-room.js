(function (global) {
    'use strict';

    const books = new WeakMap();
    const progressBars = new WeakSet();
    const comparisonSliders = new WeakSet();
    const interactiveSelector = 'a, button, input, select, textarea, summary, [role="button"], [role="link"], [contenteditable="true"]';
    const notes = {
        ocr: {
            title: 'Read the characters.',
            body: 'OCR recovers text from document images. Recognition quality and reading order shape the evidence available to every downstream task.',
            category: 'ocr', link: 'Explore OCR methods →'
        },
        layout: {
            title: 'Recover the structure.',
            body: 'Layout analysis locates headings, paragraphs, tables, and figures. Their positions and relationships help a system read the page in context.',
            category: 'layout', link: 'Explore layout analysis →'
        },
        table: {
            title: 'Keep rows and columns connected.',
            body: 'Table understanding combines cell content with row, column, and header relationships. Preserving that structure matters for retrieval, computation, and question answering.',
            category: 'table', link: 'Explore table understanding →'
        },
        rag: {
            title: 'Find evidence before answering.',
            body: 'Document RAG retrieves relevant evidence before generating an answer. Long documents add the challenge of connecting evidence across pages and modalities.',
            category: 'rag', link: 'Explore document RAG →'
        },
        vlm: {
            title: 'Read text and visual context together.',
            body: 'Document vision-language models connect the words on a page with its visual structure. OCR-free approaches learn to interpret the document image directly.',
            category: 'vlm', link: 'Explore document VLMs →'
        },
        evidence: {
            title: 'Make the answer verifiable.',
            body: 'A useful answer should point back to its supporting page, region, or table cell. Evaluation should consider evidence, uncertainty, and robustness as well as answer accuracy.',
            category: 'eval', link: 'Explore evaluation and benchmarks →'
        }
    };
    const pageNotes = [
        { title: 'A field guide, with room in the margins.', body: 'Turn the pages to explore the survey. Select an underlined concept to open a note and follow its research direction.', link: 'Explore the research map →', href: '#taxonomy' },
        { title: 'First, make the page readable.', body: 'Text recognition and layout analysis turn document pixels into useful content and structure. Select a marked term to explore its methods.', link: 'Browse perception papers →', href: 'search.html?category=ocr' },
        { title: 'Then, connect the evidence.', body: 'Tables, retrieval, and vision-language models offer different routes from document content to a grounded answer.', link: 'Browse document understanding →', href: 'search.html?category=vlm' },
        { title: 'Questions worth keeping open.', body: 'The survey highlights verifiable evidence, complex evidence organization, and evaluation under real-world conditions.', link: 'Explore evaluation and benchmarks →', href: 'search.html?category=eval' }
    ];

    function clampPage(value, count) {
        const parsed = Number(value);
        return Math.max(0, Math.min(Math.max(0, count - 1), Number.isFinite(parsed) ? Math.trunc(parsed) : 0));
    }

    function pageLabel(page, count) {
        return `${String(page + 1).padStart(2, '0')} / ${String(count).padStart(2, '0')}`;
    }

    function isInteractive(target) {
        return !!(target && typeof target.closest === 'function' && target.closest(interactiveSelector));
    }

    function prefersReducedMotion() {
        return !!global.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    }

    function initProgress(doc) {
        const progress = doc.getElementById('readerProgress');
        if (!progress || progressBars.has(progress)) return;
        progressBars.add(progress);
        progress.setAttribute('role', 'progressbar');
        progress.setAttribute('aria-label', 'Page reading progress');
        progress.setAttribute('aria-valuemin', '0');
        progress.setAttribute('aria-valuemax', '100');
        let scheduled = false;

        function update() {
            scheduled = false;
            const scroller = doc.scrollingElement || doc.documentElement;
            if (!scroller) return;
            const height = Math.max(scroller.scrollHeight || 0, doc.body?.scrollHeight || 0);
            const viewport = global.innerHeight || scroller.clientHeight || 0;
            const offset = Number.isFinite(global.scrollY) ? global.scrollY : (scroller.scrollTop || 0);
            const distance = height - viewport;
            const ratio = distance > 0 ? Math.max(0, Math.min(1, offset / distance)) : 0;
            progress.style.setProperty('--reading-progress', String(ratio));
            progress.setAttribute('aria-valuenow', String(Math.round(ratio * 100)));
        }

        function schedule() {
            if (scheduled) return;
            scheduled = true;
            if (typeof global.requestAnimationFrame === 'function') global.requestAnimationFrame(update);
            else update();
        }

        global.addEventListener?.('scroll', schedule, { passive: true });
        global.addEventListener?.('resize', schedule, { passive: true });
        update();
    }

    function initComparison(doc) {
        const slider = doc.getElementById('ocrReveal');
        const comparison = doc.getElementById('ocrComparison');
        const label = doc.getElementById('revealValue');
        if (!slider || !comparison || comparisonSliders.has(slider)) return;
        comparisonSliders.add(slider);

        function reveal() {
            const parsed = Number(slider.value);
            const value = Number.isFinite(parsed) ? Math.max(0, Math.min(100, Math.round(parsed))) : 55;
            const description = `${value}% structure revealed`;
            comparison.style.setProperty('--reveal', `${value}%`);
            slider.setAttribute('aria-valuetext', description);
            if (label) label.textContent = description;
        }

        slider.addEventListener('input', reveal);
        reveal();
    }

    function init() {
        const doc = global.document;
        if (!doc) return null;
        initProgress(doc);
        initComparison(doc);
        const book = doc.getElementById('surveyBook');
        if (!book) return null;
        if (books.has(book)) return books.get(book);
        const spreads = Array.from(book.querySelectorAll('.book-spread[data-spread]'))
            .sort((a, b) => Number(a.dataset.spread) - Number(b.dataset.spread));
        if (!spreads.length) return null;
        const tabs = Array.from(doc.querySelectorAll('.book-tab[data-book-page]'))
            .filter(tab => Number.isInteger(Number(tab.dataset.bookPage)) && Number(tab.dataset.bookPage) >= 0 && Number(tab.dataset.bookPage) < spreads.length);
        const previous = doc.getElementById('bookPrev');
        const next = doc.getElementById('bookNext');
        const label = doc.getElementById('bookPageLabel');
        const turnArea = doc.getElementById('bookTurnArea');
        const turningLeaf = book.querySelector?.('.book-turning-leaf') || null;
        const annotation = doc.getElementById('bookAnnotation');
        const annotationTitle = doc.getElementById('bookAnnotationTitle');
        const annotationBody = doc.getElementById('bookAnnotationBody');
        const annotationLink = doc.getElementById('bookAnnotationLink');
        const annotationClose = doc.getElementById('annotationClose');
        const triggers = Array.from(book.querySelectorAll('button.annotation-trigger[data-note]'))
            .filter(trigger => Object.hasOwn(notes, trigger.dataset.note));
        let currentPage = clampPage(book.dataset.page, spreads.length);
        let activeTrigger = null;
        let animationTimer = null;
        let drag = null;

        if (label) {
            label.setAttribute('aria-live', 'polite');
            label.setAttribute('aria-atomic', 'true');
        }
        if (annotation) {
            annotation.setAttribute('aria-live', 'polite');
            annotation.setAttribute('aria-atomic', 'true');
        }
        spreads.forEach((spread, index) => {
            if (!spread.id) spread.id = `book-spread-${index + 1}`;
        });
        tabs.forEach(tab => tab.setAttribute('aria-controls', spreads[Number(tab.dataset.bookPage)].id));
        triggers.forEach(trigger => {
            trigger.setAttribute('aria-expanded', 'false');
            if (annotation) trigger.setAttribute('aria-controls', annotation.id);
        });

        function clearTrigger() {
            triggers.forEach(trigger => {
                trigger.classList.remove('is-active');
                trigger.setAttribute('aria-expanded', 'false');
            });
            activeTrigger = null;
        }

        function updateAnnotation(note) {
            if (annotationTitle) annotationTitle.textContent = note.title;
            if (annotationBody) annotationBody.textContent = note.body;
            if (annotationLink) {
                annotationLink.textContent = note.link;
                annotationLink.setAttribute('href', note.href || `search.html?category=${encodeURIComponent(note.category)}`);
            }
            if (annotation) annotation.hidden = false;
        }

        function resetAnnotation() {
            clearTrigger();
            updateAnnotation(pageNotes[currentPage] || pageNotes[0]);
        }

        function closeAnnotation(restoreFocus) {
            const trigger = activeTrigger;
            clearTrigger();
            if (annotation) annotation.hidden = true;
            if (restoreFocus) (trigger || book).focus({ preventScroll: true });
        }

        function clearTurnSnapshot() {
            if (!turningLeaf) return;
            if (typeof turningLeaf.replaceChildren === 'function') turningLeaf.replaceChildren();
            else turningLeaf.textContent = '';
        }

        function prepareTurnSnapshot(direction) {
            clearTurnSnapshot();
            if (!turningLeaf || prefersReducedMotion() || typeof turningLeaf.replaceChildren !== 'function') return;
            const source = spreads[currentPage].querySelector?.(direction === 'next' ? '.book-page-right' : '.book-page-left');
            if (!source || typeof source.cloneNode !== 'function') return;
            const snapshot = source.cloneNode(true);
            // A visual turning leaf must never become a second accessible or interactive page.
            if (typeof snapshot.querySelectorAll !== 'function' || typeof snapshot.removeAttribute !== 'function' || typeof snapshot.setAttribute !== 'function') return;
            snapshot.removeAttribute('id');
            snapshot.querySelectorAll('[id]').forEach(element => element.removeAttribute('id'));
            snapshot.setAttribute('aria-hidden', 'true');
            snapshot.setAttribute('inert', '');
            snapshot.inert = true;
            const focusable = `${interactiveSelector}, [tabindex], audio[controls], video[controls], iframe`;
            if (snapshot.matches?.(focusable)) snapshot.setAttribute('tabindex', '-1');
            snapshot.querySelectorAll(focusable).forEach(element => element.setAttribute('tabindex', '-1'));
            turningLeaf.replaceChildren(snapshot);
        }

        function animateTurn(direction) {
            if (animationTimer !== null) global.clearTimeout?.(animationTimer);
            book.classList.remove('is-turning');
            book.dataset.turn = direction;
            if (prefersReducedMotion()) {
                clearTurnSnapshot();
                return;
            }
            // Restart the turning leaf even when the reader turns several pages quickly.
            void book.offsetWidth;
            book.classList.add('is-turning');
            if (typeof global.setTimeout === 'function') {
                animationTimer = global.setTimeout(() => {
                    book.classList.remove('is-turning');
                    clearTurnSnapshot();
                    animationTimer = null;
                }, 420);
            } else {
                book.classList.remove('is-turning');
                clearTurnSnapshot();
            }
        }

        function renderPage() {
            book.dataset.page = String(currentPage);
            spreads.forEach((spread, index) => {
                const selected = index === currentPage;
                spread.hidden = !selected;
                spread.setAttribute('aria-hidden', String(!selected));
            });
            tabs.forEach(tab => {
                const selected = Number(tab.dataset.bookPage) === currentPage;
                tab.classList.toggle('is-active', selected);
                tab.classList.toggle('active', selected);
                if (selected) tab.setAttribute('aria-current', 'page');
                else tab.removeAttribute('aria-current');
                if (tab.getAttribute('role') === 'tab') tab.setAttribute('aria-selected', String(selected));
                else tab.setAttribute('aria-pressed', String(selected));
            });
            if (previous) {
                previous.disabled = currentPage === 0;
                previous.setAttribute('aria-disabled', String(previous.disabled));
            }
            if (next) {
                next.disabled = currentPage === spreads.length - 1;
                next.setAttribute('aria-disabled', String(next.disabled));
            }
            if (label) label.textContent = pageLabel(currentPage, spreads.length);
            resetAnnotation();
        }

        function goToPage(value, animate = true) {
            const target = clampPage(value, spreads.length);
            if (target === currentPage) return false;
            const direction = target > currentPage ? 'next' : 'prev';
            const focused = doc.activeElement;
            const focusWasOnPage = spreads[currentPage].contains(focused);
            if (animate) prepareTurnSnapshot(direction);
            else clearTurnSnapshot();
            currentPage = target;
            renderPage();
            if (animate) animateTurn(direction);
            if (focusWasOnPage || (previous && focused === previous && previous.disabled) || (next && focused === next && next.disabled)) {
                book.focus({ preventScroll: true });
            }
            return true;
        }

        previous?.addEventListener('click', () => goToPage(currentPage - 1));
        next?.addEventListener('click', () => goToPage(currentPage + 1));
        tabs.forEach(tab => tab.addEventListener('click', event => {
            event.preventDefault();
            goToPage(Number(tab.dataset.bookPage));
        }));
        book.addEventListener('keydown', event => {
            if (event.defaultPrevented || event.altKey || event.ctrlKey || event.metaKey) return;
            const control = event.target?.closest?.(interactiveSelector);
            const pageControl = control && control.tagName === 'BUTTON' && (control === previous || control === next || tabs.includes(control));
            if (control && !pageControl) return;
            let target;
            if (event.key === 'ArrowLeft') target = currentPage - 1;
            else if (event.key === 'ArrowRight') target = currentPage + 1;
            else if (event.key === 'Home') target = 0;
            else if (event.key === 'End') target = spreads.length - 1;
            else return;
            event.preventDefault();
            goToPage(target);
        });

        triggers.forEach(trigger => trigger.addEventListener('click', () => {
            if (trigger === activeTrigger && annotation && !annotation.hidden) {
                closeAnnotation(false);
                return;
            }
            clearTrigger();
            activeTrigger = trigger;
            trigger.classList.add('is-active');
            trigger.setAttribute('aria-expanded', 'true');
            updateAnnotation(notes[trigger.dataset.note]);
        }));
        annotationClose?.addEventListener('click', () => closeAnnotation(true));
        doc.addEventListener('keydown', event => {
            if (event.key !== 'Escape' || !activeTrigger || !annotation || annotation.hidden) return;
            const target = event.target;
            if (!book.contains(target) && !annotation.contains(target)) return;
            event.preventDefault();
            closeAnnotation(true);
        });

        if (turnArea) {
            turnArea.style.touchAction = 'pan-y';

            function resetDrag() {
                if (drag && turnArea.hasPointerCapture?.(drag.id)) {
                    try { turnArea.releasePointerCapture(drag.id); } catch (_) { /* A cancelled pointer may already have been released. */ }
                }
                drag = null;
                turnArea.style.setProperty('--page-drag', '0px');
                book.classList.remove('is-dragging');
                delete book.dataset.turnDirection;
            }

            turnArea.addEventListener('pointerdown', event => {
                if (event.isPrimary === false || event.button !== 0 || isInteractive(event.target)) return;
                drag = { id: event.pointerId, startX: event.clientX, startY: event.clientY, lastX: event.clientX, lastY: event.clientY, horizontal: false };
            });
            turnArea.addEventListener('pointermove', event => {
                if (!drag || drag.id !== event.pointerId) return;
                drag.lastX = event.clientX;
                drag.lastY = event.clientY;
                const dx = drag.lastX - drag.startX;
                const dy = drag.lastY - drag.startY;
                if (!drag.horizontal && Math.abs(dy) > 12 && Math.abs(dy) > Math.abs(dx) * 1.2) {
                    resetDrag();
                    return;
                }
                if (!drag.horizontal && Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy) * 1.2) {
                    drag.horizontal = true;
                    try { turnArea.setPointerCapture(event.pointerId); } catch (_) { /* Pointer capture is optional for a detached or cancelled pointer. */ }
                }
                if (!drag.horizontal) return;
                if (event.cancelable) event.preventDefault();
                book.classList.add('is-dragging');
                book.dataset.turnDirection = dx < 0 ? 'next' : 'prev';
                turnArea.style.setProperty('--page-drag', `${Math.max(-140, Math.min(140, dx))}px`);
            }, { passive: false });

            function finishDrag(event) {
                if (!drag || drag.id !== event.pointerId) return;
                const dx = (Number.isFinite(event.clientX) ? event.clientX : drag.lastX) - drag.startX;
                const dy = (Number.isFinite(event.clientY) ? event.clientY : drag.lastY) - drag.startY;
                const turn = drag.horizontal && Math.abs(dx) >= 50 && Math.abs(dx) > Math.abs(dy) * 1.2;
                resetDrag();
                if (turn) goToPage(currentPage + (dx < 0 ? 1 : -1));
            }

            turnArea.addEventListener('pointerup', finishDrag);
            global.addEventListener?.('pointerup', finishDrag);
            turnArea.addEventListener('pointercancel', resetDrag);
            turnArea.addEventListener('lostpointercapture', resetDrag);
        }

        renderPage();
        const controller = { goToPage, next: () => goToPage(currentPage + 1), previous: () => goToPage(currentPage - 1), getPage: () => currentPage };
        books.set(book, controller);
        return controller;
    }

    global.ReadingRoom = Object.assign(global.ReadingRoom || {}, { init, clampPage, pageLabel });
    const doc = global.document;
    if (doc?.readyState === 'loading') doc.addEventListener('DOMContentLoaded', init, { once: true });
    else init();
})(typeof window !== 'undefined' ? window : globalThis);
