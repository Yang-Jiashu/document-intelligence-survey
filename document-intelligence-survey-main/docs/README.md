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
