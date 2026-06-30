# DataChecker — Saudi Open Data Quality Auditor

A full-stack tool that audits public datasets from [data.gov.sa](https://open.data.gov.sa),
scores them across 7 data-quality dimensions, runs ML analysis (topic detection, anomaly
detection, abandonment risk, quality clustering), and presents the results in a live
dashboard with PDF report exports.

**Live at:** `https://auditor.otaibifmf.com` (target subdomain — see deployment notes below)

## What it demonstrates

- **Full-stack architecture** — FastAPI (async, Python) backend + React/Vite frontend,
  containerized with Docker, backed by PostgreSQL.
- **Data quality engineering** — a weighted scoring system across completeness, freshness,
  consistency, uniqueness, validity, accessibility, and metadata quality.
- **Applied ML** — Isolation Forest for anomaly detection, K-Means clustering for quality
  profiling, a heuristic/sklearn-swappable abandonment-risk predictor, and keyword-based
  topic classification.
- **Real external API integration** — consumes the CKAN v3 API that powers Saudi Arabia's
  national open data portal.
- **Production-shaped deploy** — split across two providers (Render for the stateful
  backend + DB, Vercel for the static frontend), connected via a same-origin reverse proxy
  rather than open CORS, mirroring how real multi-service apps are deployed.

## Architecture

```
DatasetAuditor/
├── backend/                  FastAPI app (Render: Docker + Postgres)
│   ├── main.py                API routes, CORS, lifespan/init
│   ├── ckan_client.py         CKAN v3 API client (data.gov.sa)
│   ├── models.py              SQLAlchemy ORM models
│   ├── database.py            Async Postgres connection (env-driven DATABASE_URL)
│   ├── report.py               PDF report generator (ReportLab)
│   ├── quality/                7 scoring dimensions + weighted aggregator
│   └── ml/                     topic detection, abandonment risk, anomaly, clustering
└── frontend/                  React + Vite app (Vercel: static build)
    └── src/
        ├── App.jsx
        ├── api.js              calls relative /api/* (proxied to backend)
        └── components/         Dashboard, DatasetDetail, Leaderboard, TrendView, ScoreCard
```

## How the two halves connect

The frontend never talks to the backend's raw URL directly. `frontend/api.js` calls a
relative path (`/api/...`); `frontend/vercel.json` rewrites that path server-side to the
Render-hosted backend. From the browser's perspective everything is same-origin — no CORS
exposure, no backend URL leaked into client code.

```
Browser → auditor.otaibifmf.com/api/*
        → (Vercel rewrite, server-side)
        → datasetauditor-backend.onrender.com/api/*
        → Postgres (Render managed DB)
```

## Deployment notes (for connecting to the portfolio)

1. **Backend + DB** deploy independently on Render via [`render.yaml`](render.yaml) (a
   Blueprint — one click provisions the web service and the free Postgres instance, with
   `DATABASE_URL` auto-wired between them).
2. **Frontend** deploys independently on Vercel as its own project (root: `frontend/`).
3. **DNS**: a single CNAME — `auditor.otaibifmf.com` → the Vercel frontend project. No
   changes needed to the portfolio's own Vercel project, repo, or routing.
4. **Portfolio integration**: add a project card/link on the portfolio (otaibifmf.com)
   pointing at `https://auditor.otaibifmf.com`. The two codebases and deploys stay fully
   decoupled — a redeploy or outage on one never touches the other.

This project is intentionally kept as a separate deploy from the portfolio rather than
mounted at a path like `otaibifmf.com/projects/dataauditor`, to avoid coupling its routing
into the portfolio's own Vercel config.
