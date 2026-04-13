# DataChecker — Saudi Open Data Quality Auditor

A full-stack tool that automatically audits datasets from [data.gov.sa](https://open.data.gov.sa),
scores them across 7 quality dimensions, applies ML analysis, and presents results in a live dashboard.

---

## Quick Start

### Option A — Docker (recommended)

```bash
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

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
npm run dev   # http://localhost:3000
```

---

## Architecture

```
DataChecker/
├── backend/
│   ├── main.py               FastAPI app — all API routes
│   ├── ckan_client.py        CKAN v3 API client (data.gov.sa)
│   ├── models.py             SQLAlchemy ORM models
│   ├── database.py           Async PostgreSQL connection
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
└── frontend/
    └── src/
        ├── App.jsx
        ├── api.js
        └── components/
            ├── Dashboard.jsx       Dataset table + bulk audit
            ├── DatasetDetail.jsx   Drill-down + PDF download
            ├── Leaderboard.jsx     Ministry ranking
            ├── TrendView.jsx       Score trends over time
            └── ScoreCard.jsx       Shared score UI components
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
| GET | `/api/datasets` | Paginated dataset list with scores |
| GET | `/api/datasets/{id}` | Full audit detail |
| GET | `/api/datasets/{id}/history` | Score history over time |
| GET | `/api/datasets/{id}/report.pdf` | Download PDF report |
| POST | `/api/audit/{id}` | Audit a single dataset |
| POST | `/api/audit/bulk?limit=N` | Background bulk audit |
| GET | `/api/leaderboard` | Organization ranking |
| GET | `/api/stats` | Platform statistics |
| GET | `/api/trends` | Quality trends over time |

---

## ML Components

- **Topic Detector** — Keyword-based NLP to classify datasets (Health, Economy, Education, etc.)
- **Abandonment Predictor** — Heuristic model estimating probability a dataset won't be updated
  (replaceable with a trained sklearn classifier once data is collected)
- **Anomaly Detection** — Isolation Forest per numeric column to flag suspicious values
- **Quality Clustering** — K-Means (k=4) groups datasets into quality profiles: High / Acceptable / Poor / Critical

---

## Notes

- data.gov.sa uses standard CKAN v3 API — no authentication required for public datasets
- Resource files are sampled (max 5MB / 10k rows) to keep audits fast
- Rate limiting is applied when fetching multiple datasets (~0.5s between requests)
- The abandonment classifier falls back to a rule-based model until you train and save a
  sklearn model to `backend/ml/abandonment_model.pkl`
