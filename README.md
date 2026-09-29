# DataChecker — Saudi Open Data Quality Auditor

DataChecker audits datasets from the Saudi Open Data portal,
[open.data.gov.sa](https://open.data.gov.sa). It scores each dataset on 7 quality dimensions,
runs some ML analysis on it, and shows the results in a dashboard. You can export any audit
as a PDF report.

It all runs on your own machine with Docker. There's no account or hosted service involved.

---

## Before you start

You need:

1. **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** (Windows / macOS), or
   Docker Engine with the Compose plugin (Linux). Check that it works with
   `docker compose version`.
2. **Git**, to clone the repository. You can also download it as a ZIP from GitHub.
3. **An internet connection with a Saudi IP address.** This one matters most.

> ### ⚠️ Why a Saudi connection?
> open.data.gov.sa only accepts connections from Saudi IP addresses. From anywhere else, the
> connection is silently dropped and audits fail with a timeout. If you're in Saudi Arabia on
> a normal home, office or mobile connection, you don't need to set anything up.
>
> VPNs often exit through datacenter IP ranges, and those can be blocked even when the VPN
> location is Saudi. Turn your VPN off if audits time out.

---

## Run it

```bash
git clone https://github.com/Otaibifmf/DatasetAuditor.git
cd DatasetAuditor
docker compose up --build
```

The first build takes a few minutes. When the logs settle, open:

| What | Where |
|------|-------|
| **The app** | http://localhost:3000 |
| API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |

To run it in the background instead, add `-d`: `docker compose up --build -d`.

### Optional: a `.env` file

It runs without any configuration. Every setting has a working default. If you're on a
shared machine, or want to change ports, copy the example file and edit it:

```bash
cp .env.example .env      # Windows PowerShell: copy .env.example .env
```

Settings you're most likely to change:

| Variable | Default | When to change it |
|----------|---------|-------------------|
| `POSTGRES_PASSWORD` | `datachecker` | Set a real password on any shared machine |
| `FRONTEND_PORT` | `3000` | Port 3000 is already in use |
| `BACKEND_PORT` | `8000` | Port 8000 is already in use |
| `DB_PORT` | `5432` | You already run Postgres locally |

The database password is only read when the database is first created. If you change it
later, reset the database (see below).

---

## Using it

1. Open http://localhost:3000.
2. Find a dataset on [open.data.gov.sa](https://open.data.gov.sa) and copy its URL. It looks
   like `https://open.data.gov.sa/en/datasets/view/<dataset-id>`.
3. Paste the URL (or just the dataset ID) into **Audit by URL or ID** and click **Audit**.
   One audit can take up to a minute, because DataChecker downloads a sample of the data.

Results are saved locally, so they stay across restarts. The other tabs build on them:

- **Dataset detail** shows the score breakdown, the issues found and the ML insights, and
  lets you **download a PDF report**.
- **Leaderboard** ranks the organizations that publish the datasets you've audited.
- **Trends** and **History** track scores over time. Audit the same dataset again later to
  see whether it changed.

The portal has no public search or listing, so DataChecker can't find datasets on its own.
You give it URLs or IDs.

### How datasets are scored

| Dimension | Weight | What it checks |
|-----------|--------|----------------|
| Completeness | 20% | Share of cells that aren't empty |
| Freshness | 20% | Days since the last update |
| Consistency | 15% | Consistent formats and types, mixed-language columns |
| Validity | 15% | Out-of-range values and statistical outliers |
| Uniqueness | 10% | Duplicate rows |
| Accessibility | 10% | Download links work, open file formats |
| Metadata Quality | 10% | Description, license, tags, author |

The overall score is the weighted average, graded **A (≥ 90)** down to **F (< 60)**.

On top of the score, DataChecker also:

- **classifies the topic** of each dataset (Health, Economy, Education, …)
- **estimates the risk** that a dataset has been abandoned
- **flags anomalous values** in numeric columns
- **groups datasets into quality profiles** (this needs several audited datasets before it
  shows anything)

Large files are sampled (up to 5 MB / 10,000 rows) to keep audits fast.

---

## Stopping, updating, resetting

```bash
docker compose down            # stop (your audit data is kept)
docker compose down -v         # stop AND delete all saved audits
git pull && docker compose up --build    # update to the latest version
```

---

## Troubleshooting

**Audits fail with a timeout / "ConnectTimeout"**
Your connection isn't reaching the portal from a Saudi IP. Turn off any VPN or proxy and
check that you can open https://open.data.gov.sa in your browser on the same machine.

**"Request Rejected"**
The portal's firewall refused the request. Try again later. If it keeps happening, please
open an issue.

**"port is already allocated"**
Something else is using port 3000, 8000 or 5432. Set `FRONTEND_PORT`, `BACKEND_PORT` or
`DB_PORT` in `.env` to a free port and run `docker compose up` again.

**The app loads but says the database is unavailable**
Check http://localhost:8000/health. If `"database"` says `unavailable`, look at the logs with
`docker compose logs db backend`. If you changed `POSTGRES_PASSWORD` after the first run,
reset with `docker compose down -v`.

**Clustering / quality profile shows nothing**
That's expected until you've audited a handful of datasets.
