# Beyond OCR: Document Intelligence Survey

Interactive web demo for the survey paper **"Beyond OCR: A Survey of Document Intelligence from Structured Perception to Multimodal Question Answering"**.

## Live Demo

Visit: `https://your-org.github.io/document-intelligence-survey/`

## Local Preview

```bash
cd docs
python3 -m http.server 8080
# Open http://localhost:8080
```

## Deploy to GitHub Pages

1. Push this repo to GitHub
2. Go to **Settings > Pages**
3. Set **Source** to "GitHub Actions"
4. The workflow in `.github/workflows/deploy.yml` will auto-deploy on push

## Structure

- `index.html` - Main page with all sections
- `images/` - All survey figures (PNG)
- `.github/workflows/deploy.yml` - Auto-deployment workflow

## SOTA snapshot maintenance

Run the offline regression tests from the repository root with Python 3.11 or newer:

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/test_sota_status.js
node tests/test_sota_deployment.js
```

The tests use local fixtures and mocked requests; they require neither network access nor API keys. The `Test SOTA updater` workflow runs them on relevant pull requests and pushes to `final`. The scheduled update also runs them before fetching or writing data.

The `Update SOTA snapshot` workflow runs automatically every day at 02:16 UTC (10:16 Asia/Shanghai) on the default `final` branch. Each run fetches the official sources, retries transient failures, and commits safely validated results. A failed source is tried again on the next daily run without a manual rerun. Changes to the updater or its workflow also trigger a refresh automatically; data-only commits do not create a refresh loop.

For an optional immediate local refresh against live public sources:

```bash
python scripts/update_sota.py
```

This command writes `docs/data/sota.json` and `docs/data/pending_updates.json`. A benchmark's ranking and `lastChecked` advance only after its source was fetched and safely parsed. Failed sources retain their previous ranking and check date, with failure details recorded for review. A partial snapshot is explicitly marked `partially refreshed snapshot`, and the command exits nonzero when any source fails. The GitHub Actions refresh step includes a summary and failure annotations.

DocVQA and InfographicVQA prefer their official RRC HTTPS evaluation pages. A fallback is limited to the same two official pages over HTTP after retryable HTTPS transport or server failures; certificate failures and parse errors must not trigger a downgrade. HTTP is unencrypted, so successful checks record the actual source URL and a warning. The benchmark cards link to that recorded URL and visibly label checks made over HTTP. A failed attempt shows `Stale` and the attempt date while keeping the last verified date and ranking.

GitHub-hosted diagnostics also identified an incomplete RRC TLS certificate chain. The RRC adapter supplies the missing public GEANT TLS RSA 1 intermediate from its issuing CA, while requiring a full chain to an existing system root and checking the hostname and certificate validity. See `scripts/certs/README.md` for source, fingerprint and verification details. The read-only `Diagnose RRC transport` workflow remains available for future network investigations.

On 2026-10-27, live requests to both HTTPS task pages returned an Envoy 503 upstream connection failure from the verification environment. The exact official HTTP pages returned 200 without redirects, with the correct active task and complete `Date / Method / Score` tables. This does not establish a global RRC outage or a markup regression. The repaired adapters validated 174 DocVQA and 62 InfographicVQA model rows; both top-five rankings were unchanged. Only these two benchmarks were rechecked for this repair; the other benchmarks retain their earlier dates. Snapshot-level `lastChecked` describes the latest snapshot attempt, while each benchmark records its own last successful verification.

The scheduled workflow commits successful updates and failure metadata, then a separate source-health check fails when any source could not refresh. A snapshot-written output prevents publication after an incomplete write. Pages may publish a partial snapshot only when the upstream snapshot job successfully tested, wrote and committed it; source-health failures remain visible in Actions while the site displays retained data and stale markers. Failed tests, failed writes, failed commits and cancelled runs cannot authorize this partial-snapshot deployment. Inspect the source errors before retrying; an HTTP error, timeout, or missing ranking table alone does not establish a permanent source outage. Do not advance check dates or substitute unverified rankings to clear a failure.

## Document intelligence research progress

Open [the research tracker](research.html) for current document intelligence papers and official project releases. Its topics cover OCR/document parsing, layout analysis, tables and charts, document question answering, document RAG and evaluation. The configuration and data files are separate from the curated survey and the existing WeChat discovery workflow. The feed uses direct arXiv metadata and an allowlist of official GitHub projects, without a paid search or classification API.

The `Update Research Progress` workflow runs daily at 03:16 UTC (11:16 Asia/Shanghai). Changes to the updater, topic configuration or tracker interface also trigger an immediate refresh on `final`; its data-only commits do not create a refresh loop. Multiple topic queries discover candidate papers, and a required document-intelligence relevance gate filters out generic search, advertising and recommendation research. arXiv requests are serialized and rate limited. The configured result limits, discovery window and retention bounds make this a useful recent-progress feed, not a complete census of every relevant paper.

Search and recommendation describe how this site discovers and orders document intelligence progress. Keyword and topic matches, freshness, source information and topic diversification contribute to an explainable ranking. This is not a trained personalized recommender, an advertisement service, an expert quality score or a claim that preprints are peer reviewed. Paper and release records are visibly distinguished and link back to their official sources.

Publication date, revision date, release date, discovery time and the latest successful source check remain separate. An older paper with a new revision is not described as newly published. Duplicate arXiv versions and repeated official release records are merged using their source identities. Schema version 2 marks the feed's scope as `document-intelligence`; incompatible older feed data must not be displayed as current document intelligence progress without passing the relevance checks.

Every run validates source responses before merging data. A failed paper query or official project source retains its prior verified records and successful check date, receives a stale status, and is retried automatically the next day. A failed fetch is distinct from a successful search with no matching results. The updater writes `docs/data/research_updates.json` and `docs/data/research_update_log.json`, emits an Actions summary and returns nonzero for partial failure. Only a tested, safely written and committed snapshot may authorize Pages publication; a separate health check preserves the failure signal while the site can display retained records, source coverage and stale status.

The update workflow supplies its standard ephemeral `GITHUB_TOKEN` for public GitHub release requests. No new repository secret or additional permission is required. Local runs can use the public unauthenticated endpoint, or an optional `GITHUB_TOKEN` for the public API's authenticated rate limit; never store tokens in configuration or generated data.

Run the same offline checks locally:

```bash
python -m unittest discover -s tests -p 'test_*.py'
node tests/test_research_ui.js
node tests/test_sota_deployment.js
```

For an immediate live refresh, use `python scripts/update_research.py`. Edit `configs/research_sources.json` to maintain topic queries, relevance terms, ranking settings and the official project allowlist. All source dates and paper metadata must come from successfully parsed official responses; never fabricate entries or advance verification dates to clear an error.
