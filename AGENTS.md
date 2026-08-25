# AGENTS.md

## Cursor Cloud specific instructions

This repo is a single Python project (Python 3.12): a Naver Smart Store SEO
automation toolkit for 나눔랩/퍼마코트. The primary product is a **Flask web
dashboard + REST API on port 5000** (`app.py`). Other entry points (Flet apps
`main.py`/`flet_app.py`, Streamlit `streamlit_app.py`, and many `*.py` CLI
scripts) share the same core library and are optional.

### Environment / running
- Dependencies live in a local virtualenv at `.venv/` (gitignored). The startup
  update script creates it and runs `pip install -r requirements.txt`. Activate
  with `source .venv/bin/activate` before running anything.
- Run the web app in dev mode with `python app.py` → serves on
  `http://0.0.0.0:5000`. Health check: `GET /api/health`. This is the dev
  command; `gunicorn -c gunicorn_conf.py app:app` (see `cloudtype.yaml`) is the
  production command and is not needed for local dev.
- Non-obvious: `python app.py` does NOT auto-start the background scheduler /
  rank sweeps. Those only start when `AUTO_START_BACKGROUND=1` (and
  `AUTO_START_SCHEDULER=1`) are set — Cloudtype sets these, local dev does not.
  Leave them unset for a quiet dev server unless you specifically want the
  background loop.

### External dependencies (mostly optional for local dev)
- There is **no database** — state is file-based (CSV/JSON/JSONL in the repo
  root, `data/`, `generated_content/`, `blog_drafts/`). No services to start.
- Rank tracking and traffic simulation make live calls to Naver. For reliable
  rank data set `NAVER_CLIENT_ID`/`NAVER_CLIENT_SECRET` (see `.env.example`);
  without keys the app still boots and template/keyword features work, but
  network-dependent endpoints (e.g. `/api/track-now`) may be slow or blocked.
- Playwright (deep rank scan / traffic engines) needs a browser that is NOT
  installed by the update script: run `python -m playwright install chromium`
  on demand. It is not required for the Flask dashboard itself.
- AI blog/content generation falls back to built-in templates when no Gemini
  key is present, so `/api/content/generate` works offline.

### Tests / lint
- There is **no formal test suite** (no pytest/unittest). `rank_test.py` and
  `scripts/check_api_rank.py` are manual/network smoke scripts. No linter is
  configured. Validate changes by importing/booting the app and hitting the API
  (e.g. `curl http://127.0.0.1:5000/api/health`).
