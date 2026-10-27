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
```

The tests use local fixtures and mocked requests; they require neither network access nor API keys. The `Test SOTA updater` workflow runs them on relevant pull requests and pushes to `final`. The scheduled update also runs them before fetching or writing data.

To refresh the snapshot against live public sources:

```bash
python scripts/update_sota.py
```

This command writes `docs/data/sota.json` and `docs/data/pending_updates.json`. A benchmark's ranking and `lastChecked` advance only after its source was fetched and safely parsed. Failed sources retain their previous ranking and check date, with failure details recorded for review. A partial snapshot is explicitly marked `partially refreshed snapshot`, and the command exits nonzero when any source fails. The GitHub Actions refresh step includes a summary and failure annotations.

DocVQA and InfographicVQA prefer their official RRC HTTPS evaluation pages. A fallback is limited to the same two official pages over HTTP after retryable HTTPS transport or server failures; certificate failures and parse errors must not trigger a downgrade. HTTP is unencrypted, so successful checks record the actual source URL and a warning. The benchmark cards link to that recorded URL and visibly label checks made over HTTP. A failed attempt shows `Stale` and the attempt date while keeping the last verified date and ranking.

On 2026-10-27, live requests to both HTTPS task pages returned an Envoy 503 upstream connection failure from the verification environment. The exact official HTTP pages returned 200 without redirects, with the correct active task and complete `Date / Method / Score` tables. This does not establish a global RRC outage or a markup regression. The repaired adapters validated 174 DocVQA and 62 InfographicVQA model rows; both top-five rankings were unchanged. Only these two benchmarks were rechecked for this repair; the other benchmarks retain their earlier dates. Snapshot-level `lastChecked` describes the latest snapshot attempt, while each benchmark records its own last successful verification.

The scheduled workflow commits successful updates and failure metadata before reporting a failed check for a partial refresh. The existing Pages deployment requires a successful workflow run, so a partial refresh commit is retained in the repository but is not automatically deployed by that failed run. Inspect the source errors before retrying; an HTTP error, timeout, or missing ranking table alone does not establish a permanent source outage. Do not advance check dates or substitute unverified rankings to clear a failure.
