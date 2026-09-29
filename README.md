# DataChecker — Saudi Open Data Quality Auditor

A full-stack tool that audits datasets from [open.data.gov.sa](https://open.data.gov.sa),
scores them across 7 quality dimensions, applies ML analysis, and presents results in a live
dashboard with PDF report export.

---

## ⚠️ Requires a Saudi IP address

The portal blocks requests from outside Saudi Arabia **at the network layer** — a non-Saudi
source IP gets a TCP connect timeout, not an error page. There are three independent gates,
and a request must clear all of them:

| Gate | Requirement |
|------|-------------|
| Network / geo | Source IP must be Saudi. Non-Saudi → `ConnectTimeout` |
| WAF headers | Full browser-like headers. A bare `Mozilla/5.0` → `Request Rejected` |
| Path allowlist | Only `/data/api/datasets` and `/data/api/datasets/resources` are permitted |

**Running from inside Saudi Arabia:** works out of the box, no extra configuration.

**Running anywhere else:** you need [`relay/`](relay/) — a small proxy deployed on a
Saudi-IP host — and must set `PORTAL_BASE_URL` to point at it. The relay clears gate 1 by
being in Saudi Arabia and gate 2 by sending the same browser headers as the backend.

---

## Quick Start

### Option A — Docker (recommended)

```bash
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

No `.env` is required locally — every setting has a working default. On any shared or public
machine, `cp .env.example .env` and set a real `POSTGRES_PASSWORD` first. Postgres is only
published on `127.0.0.1`. Stop with `docker compose down` (add `-v` to also delete the database
volume).

### Option B — Local Development

**Backend**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Start PostgreSQL separately, then:
export DATABASE_URL=postgresql+asyncpg://datachecker:datachecker@localhost:5432/datachecker
uvicorn main:app --reload
```

**Frontend**
```bash
cd frontend
npm install
npm run dev   # http://localhost:3000, proxies /api to localhost:8000
```

Requires Python 3.11+ (`asyncio.timeout` is used during database startup).

---

## Configuration

All configuration is environment-driven and resolved in a single place —
[`backend/config.py`](backend/config.py). Nothing else reads the environment or hardcodes a
host, so deploying somewhere new means setting env vars, never editing code.

Defaults run the local compose stack with zero configuration. To override anything, set
environment variables (a local `.env` file also works — compose and the shell pick it up,
and it's gitignored). Key values:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | local compose Postgres | Accepts `postgres://`, `postgresql://` or `postgresql+asyncpg://` |
| `PORTAL_BASE_URL` | `https://open.data.gov.sa` | Point at a Saudi-IP relay when hosting outside KSA |
| `RELAY_KEY` | *(empty)* | Shared secret sent as `x-relay-key`; must match the relay (required on the relay itself) |
| `CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `ENABLE_BULK_ENDPOINTS` | `false` | Gates the fan-out audit endpoints |
| `DB_CONNECT_TIMEOUT` | `10` | Fail fast instead of hanging on a dead database |

Frontend build-time settings are `VITE_*` variables (`VITE_API_BASE_URL`, defaults to
same-origin `/api`; `VITE_API_TIMEOUT_MS`; `VITE_AUDIT_TIMEOUT_MS`). Vite inlines them at
build time, so changing them requires a rebuild.

### Behaviour when the database is down

The app starts anyway rather than hanging: `/health` still answers (reporting
`"database": "unavailable"`), and DB-backed routes return a `503` with a clear message
instead of a timeout. An unreachable database must never make the service undiagnosable.

---

## Architecture

```
DatasetAuditor/
├── backend/
│   ├── config.py             All env-driven configuration (single source of truth)
│   ├── main.py               FastAPI app — all API routes
│   ├── ckan_client.py        Portal REST API client (NOT CKAN — see Notes)
│   ├── models.py             SQLAlchemy ORM models
│   ├── database.py           Async PostgreSQL connection + health probe
│   ├── report.py             PDF report generator (ReportLab)
│   ├── quality/
│   │   ├── completeness.py   Missing values check
│   │   ├── freshness.py      Last-update age check
│   │   ├── consistency.py    Format + type uniformity
│   │   ├── uniqueness.py     Duplicate row detection
│   │   ├── validity.py       Range / outlier checks
│   │   ├── accessibility.py  Link health + open formats
│   │   ├── metadata_quality.py  Description, tags, license
│   │   └── scorer.py         Weighted score aggregator
│   └── ml/
│       ├── topic_detector.py   NLP topic classification
│       ├── abandonment.py      Abandonment risk predictor
│       ├── anomaly.py          Isolation Forest anomaly detection
│       └── clustering.py       K-Means quality profile clustering
├── frontend/
│   └── src/
│       ├── App.jsx
│       ├── api.js            Axios client — base URL + timeouts from env
│       └── components/
│           ├── Dashboard.jsx      Audit by URL/ID + seed
│           ├── DatasetDetail.jsx  Drill-down + PDF download
│           ├── Leaderboard.jsx    Ministry ranking
│           ├── TrendView.jsx      Score trends over time
│           ├── History.jsx        Past audit runs
│           └── ScoreCard.jsx      Shared score UI components
└── relay/                    Saudi-IP proxy — only needed when hosting outside KSA
```

---

## Quality Dimensions & Weights

| Dimension        | Weight | What it checks |
|-----------------|--------|----------------|
| Completeness    | 20%    | % of non-null cells |
| Freshness       | 20%    | Days since last update |
| Consistency     | 15%    | Uniform formats, mixed language columns |
| Uniqueness      | 10%    | Duplicate rows |
| Validity        | 15%    | Out-of-range values, statistical outliers |
| Accessibility   | 10%    | Working download links, open formats |
| Metadata Quality| 10%    | Description, license, tags, author |

**Overall score = weighted average → Grade A (≥90) to F (<60)**

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Liveness + live database and portal config status |
| GET | `/api/datasets` | Paginated dataset list with scores |
| GET | `/api/datasets/{id}` | Full audit detail |
| GET | `/api/datasets/{id}/history` | Score history over time |
| GET | `/api/datasets/{id}/report.pdf` | Download PDF report |
| POST | `/api/audit/{id}` | Audit a single dataset by ID |
| POST | `/api/audit/by-url?url=` | Audit by full dataset URL or plain ID |
| POST | `/api/audit/raw` | Audit from a raw dataset JSON body |
| POST | `/api/audit/bulk?limit=N` | Background bulk audit — *gated* |
| POST | `/api/audit/seed` | Audit a pasted list of URLs/IDs — *gated* |
| GET | `/api/leaderboard` | Organization ranking |
| GET | `/api/stats` | Platform statistics |
| GET | `/api/trends` | Quality trends over time |

*Gated* endpoints return `403` unless `ENABLE_BULK_ENDPOINTS=true`. They fan out into many
upstream requests, so they stay off in public deployments.

---

## ML Components

- **Topic Detector** — Keyword-based NLP to classify datasets (Health, Economy, Education, etc.)
- **Abandonment Predictor** — Heuristic model estimating probability a dataset won't be updated
  (replaceable with a trained sklearn classifier once data is collected)
- **Anomaly Detection** — Isolation Forest per numeric column to flag suspicious values
- **Quality Clustering** — K-Means (k=4) groups datasets into quality profiles: High / Acceptable
  / Poor / Critical. Needs several audited datasets before it returns a cluster; with only one
  in the database it is `null`.

---

## Notes

- **This portal is not CKAN.** The class is named `CKANClient` for historical reasons, but it
  calls the portal's own REST API at `/data/api/...`, not CKAN's `/api/3/action/*`. The CKAN
  paths are rejected by the WAF.
- **There is no listing/search endpoint.** `get_all_datasets()` returns an empty list — the
  portal exposes no public dataset index, so `bulk` audits find nothing. Use the seed/URL
  audit flow with specific dataset IDs instead.
- Resource files are sampled (max 5MB / 10k rows) to keep audits fast
- Rate limiting is applied when fetching multiple datasets (~0.5s between requests)
- The abandonment classifier falls back to a rule-based model until you train and save a
  sklearn model to `backend/ml/abandonment_model.pkl`
