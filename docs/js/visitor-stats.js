(function () {
    'use strict';

    const container = document.getElementById('visitorStats');
    if (!container) return;

    // One canonical page key, shared by /, index.html, queries and hash links.
    // page_* is essential: site_* would include other projects on this host.
    const canonical = new URL('https://yang-jiashu.github.io/document-intelligence-survey/');
    const production = location.origin === canonical.origin &&
        [canonical.pathname, `${canonical.pathname}index.html`].includes(location.pathname);
    const identityKey = 'beyond-ocr-visitor-identity';
    const headers = { 'x-bsz-referer': canonical.href };
    if (production) {
        try {
            const identity = localStorage.getItem(identityKey);
            if (identity) headers.Authorization = `Bearer ${identity}`;
        } catch (_) { /* Statistics still work when browser storage is disabled. */ }
    }

    async function load() {
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 8000);
        const status = document.getElementById('visitorStatsStatus');
        try {
            const response = await fetch('https://busuanzi.meuicat.com/api', {
                // Local previews read the real count without recording QA visits.
                method: production ? 'POST' : 'GET',
                headers,
                credentials: 'omit',
                referrerPolicy: 'no-referrer',
                cache: 'no-store',
                signal: controller.signal
            });
            if (!response.ok) throw new Error('Statistics unavailable');
            const payload = await response.json();
            const data = payload.data;
            if (payload.success !== true || !data ||
                !Number.isSafeInteger(data.page_pv) || data.page_pv < 0 ||
                !Number.isSafeInteger(data.page_uv) || data.page_uv < 0) {
                throw new Error('Invalid statistics');
            }
            document.getElementById('homepageViews').textContent = data.page_pv.toLocaleString('en-US');
            document.getElementById('homepageVisitors').textContent = data.page_uv.toLocaleString('en-US');
            if (production) {
                try {
                    const identity = response.headers.get('Set-Bsz-Identity');
                    if (identity) localStorage.setItem(identityKey, identity);
                } catch (_) { /* Do not hide valid counts if persistence is blocked. */ }
            }
            container.dataset.state = 'ready';
            status.textContent = '';
        } catch (_) {
            container.dataset.state = 'unavailable';
            status.textContent = ' · Statistics temporarily unavailable';
        } finally {
            clearTimeout(timeout);
            container.setAttribute('aria-busy', 'false');
        }
    }

    load();
})();
