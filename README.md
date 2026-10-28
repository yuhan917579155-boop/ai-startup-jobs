# AI Startup Jobs

Static job board aggregating public AI-startup job postings (Ashby/Greenhouse public APIs + attributed supplementary feeds). Summaries only (<=280 chars); applications link back to the original posting.

Build: `python3 site/build.py` reads `data/jobs-*.json` shards and writes `site/dist/`. Deployed on Vercel; custom domain hajimijob.top.
