"""
DataChecker FastAPI backend — Saudi Open Data Quality Auditor
"""

from __future__ import annotations
import asyncio
import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func, desc, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, init_db, AsyncSessionLocal
from models import AuditResult
from ckan_client import CKANClient
from quality import (
    check_completeness, check_freshness, check_consistency,
    check_uniqueness, check_validity, check_accessibility,
    check_metadata_quality, compute_scores,
)
from quality.completeness import CompletenessResult
from quality.freshness import FreshnessResult
from quality.consistency import ConsistencyResult
from quality.uniqueness import UniquenessResult
from quality.validity import ValidityResult
from quality.accessibility import AccessibilityResult
from quality.metadata_quality import MetadataResult
from quality.scorer import QualityReport
from ml import detect_topic, predict_abandonment, cluster_datasets
from report import generate_pdf_report

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CKAN_BASE = "https://open.data.gov.sa/data/api"

_VALID_ID_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_\-]{2,149}$')


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="DataChecker API",
    description="Saudi Open Data Quality Audit Tool",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers={"User-Agent": "DataChecker/1.0"},
        timeout=30.0,
        follow_redirects=True,
    )


_AUDIT_DEFAULTS = [
    CompletenessResult(score=50.0, missing_pct=50.0),
    FreshnessResult(score=50.0, days_since_update=None, last_modified=None, expected_frequency=None),
    ConsistencyResult(score=50.0),
    UniquenessResult(score=100.0, duplicate_pct=0.0, duplicate_count=0, total_rows=0),
    ValidityResult(score=50.0),
    AccessibilityResult(score=50.0, working_links=0, broken_links=0, total_links=0, open_format_pct=0.0),
    MetadataResult(score=50.0, has_description=False, description_length=0,
                   description_too_vague=False, has_license=False,
                   has_tags=False, tag_count=0, has_author=False,
                   has_temporal_coverage=False, has_spatial_coverage=False),
]


async def _audit_dataset(dataset: dict, http_client: httpx.AsyncClient) -> tuple[QualityReport, str, str]:
    """Run all quality checks on a single dataset and return (report, org_id, org_name)."""
    ds_id = dataset.get("id") or dataset.get("name", "")
    ds_title = dataset.get("title") or dataset.get("name", "")
    org = (dataset.get("organization") or {})
    org_id = org.get("id", "")
    org_name = org.get("title") or org.get("name") or "Unknown"

    results = await asyncio.gather(
        check_completeness(dataset, http_client),
        asyncio.to_thread(check_freshness, dataset),
        check_consistency(dataset, http_client),
        check_uniqueness(dataset, http_client),
        check_validity(dataset, http_client),
        check_accessibility(dataset, http_client),
        asyncio.to_thread(check_metadata_quality, dataset),
        return_exceptions=True,
    )

    clean = [r if not isinstance(r, Exception) else _AUDIT_DEFAULTS[i] for i, r in enumerate(results)]
    comp, fresh, cons, uniq, valid, access, meta = clean

    report = compute_scores(
        dataset_id=ds_id,
        dataset_title=ds_title,
        organization=org_name,
        completeness=comp,
        freshness=fresh,
        consistency=cons,
        uniqueness=uniq,
        validity=valid,
        accessibility=access,
        metadata_quality=meta,
    )

    report.ml_topic = detect_topic(dataset)
    report.ml_abandoned_probability = predict_abandonment(
        days_since_update=fresh.days_since_update,
        update_frequency_stated=bool(fresh.expected_frequency),
        resource_count=len(dataset.get("resources", [])),
        has_broken_links=access.broken_links > 0,
        description_length=meta.description_length,
        tag_count=meta.tag_count,
    )
    report.audited_at = datetime.now(timezone.utc).isoformat()

    return report, org_id, org_name


async def _save_report(report: QualityReport, org_id: str, org_name: str, db: AsyncSession):
    row = AuditResult(
        dataset_id=report.dataset_id,
        dataset_title=report.dataset_title,
        organization_id=org_id,
        organization_name=org_name,
        overall_score=report.overall_score,
        grade=report.grade,
        completeness_score=report.dimension_scores.get("completeness"),
        freshness_score=report.dimension_scores.get("freshness"),
        consistency_score=report.dimension_scores.get("consistency"),
        uniqueness_score=report.dimension_scores.get("uniqueness"),
        validity_score=report.dimension_scores.get("validity"),
        accessibility_score=report.dimension_scores.get("accessibility"),
        metadata_quality_score=report.dimension_scores.get("metadata_quality"),
        ml_topic=report.ml_topic,
        ml_abandoned_probability=report.ml_abandoned_probability,
        dimension_scores=report.dimension_scores,
        all_issues=report.all_issues,
        details=report.to_dict().get("details"),
        days_since_update=report.freshness.days_since_update if report.freshness else None,
        total_rows=report.completeness.total_rows if report.completeness else 0,
        total_resources=report.accessibility.total_links if report.accessibility else 0,
        has_csv=(report.completeness.total_cols > 0) if report.completeness else False,
        audited_at=datetime.now(timezone.utc),
    )
    db.add(row)
    await db.commit()


# ── Routes: Dashboard ──────────────────────────────────────────────────────────

@app.get("/api/datasets", summary="List all audited datasets")
async def list_datasets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = Query("score_desc"),
    org: Optional[str] = None,
    grade: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Return paginated list of latest audit results per dataset."""
    subq = (
        select(AuditResult.dataset_id, func.max(AuditResult.audited_at).label("latest"))
        .group_by(AuditResult.dataset_id)
        .subquery()
    )
    q = (
        select(AuditResult)
        .join(subq, (AuditResult.dataset_id == subq.c.dataset_id) &
                    (AuditResult.audited_at == subq.c.latest))
    )
    if org:
        q = q.where(AuditResult.organization_id == org)
    if grade:
        q = q.where(AuditResult.grade == grade.upper())

    order_map = {
        "score_desc":  desc(AuditResult.overall_score),
        "score_asc":   AuditResult.overall_score,
        "date_desc":   desc(AuditResult.audited_at),
        "title_asc":   AuditResult.dataset_title,
    }
    q = q.order_by(order_map.get(sort, desc(AuditResult.overall_score)))

    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = (await db.execute(q.offset((page - 1) * page_size).limit(page_size))).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "datasets": [
            {
                "dataset_id": r.dataset_id,
                "title": r.dataset_title,
                "organization": r.organization_name,
                "organization_id": r.organization_id,
                "overall_score": r.overall_score,
                "grade": r.grade,
                "dimension_scores": r.dimension_scores,
                "ml_topic": r.ml_topic,
                "ml_abandoned_probability": r.ml_abandoned_probability,
                "audited_at": r.audited_at.isoformat() if r.audited_at else None,
            }
            for r in rows
        ],
    }


@app.get("/api/datasets/{dataset_id}", summary="Get full audit detail for a dataset")
async def get_dataset_detail(dataset_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(
        select(AuditResult)
        .where(AuditResult.dataset_id == dataset_id)
        .order_by(desc(AuditResult.audited_at))
        .limit(1)
    )).scalars().first()
    if not row:
        raise HTTPException(404, "Dataset not audited yet. Trigger an audit first.")
    return {
        "dataset_id": row.dataset_id,
        "title": row.dataset_title,
        "organization": row.organization_name,
        "overall_score": row.overall_score,
        "grade": row.grade,
        "dimension_scores": row.dimension_scores,
        "all_issues": row.all_issues,
        "details": row.details,
        "ml_topic": row.ml_topic,
        "ml_abandoned_probability": row.ml_abandoned_probability,
        "ml_quality_cluster": row.ml_quality_cluster,
        "audited_at": row.audited_at.isoformat() if row.audited_at else None,
    }


@app.get("/api/datasets/{dataset_id}/history", summary="Score history over time")
async def get_dataset_history(dataset_id: str, db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(AuditResult)
        .where(AuditResult.dataset_id == dataset_id)
        .order_by(AuditResult.audited_at)
    )).scalars().all()
    return [
        {
            "audited_at": r.audited_at.isoformat() if r.audited_at else None,
            "overall_score": r.overall_score,
            "grade": r.grade,
            "dimension_scores": r.dimension_scores,
        }
        for r in rows
    ]


@app.get("/api/datasets/{dataset_id}/report.pdf", summary="Download PDF report")
async def download_pdf(dataset_id: str, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(
        select(AuditResult)
        .where(AuditResult.dataset_id == dataset_id)
        .order_by(desc(AuditResult.audited_at))
        .limit(1)
    )).scalars().first()
    if not row:
        raise HTTPException(404, "No audit found for this dataset")

    report = QualityReport(
        dataset_id=row.dataset_id,
        dataset_title=row.dataset_title or "",
        organization=row.organization_name or "",
        overall_score=row.overall_score or 0,
        grade=row.grade or "F",
        dimension_scores=row.dimension_scores or {},
        all_issues=row.all_issues or [],
        ml_topic=row.ml_topic,
        ml_abandoned_probability=row.ml_abandoned_probability,
        audited_at=row.audited_at.isoformat() if row.audited_at else None,
    )
    pdf_bytes = generate_pdf_report(report)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}_report.pdf"'},
    )


# ── Routes: Leaderboard ────────────────────────────────────────────────────────

@app.get("/api/leaderboard", summary="Ministry/organization quality leaderboard")
async def leaderboard(db: AsyncSession = Depends(get_db)):
    """Average latest score per organization."""
    subq = (
        select(AuditResult.dataset_id, func.max(AuditResult.audited_at).label("latest"))
        .group_by(AuditResult.dataset_id)
        .subquery()
    )
    latest_q = (
        select(AuditResult)
        .join(subq, (AuditResult.dataset_id == subq.c.dataset_id) &
                    (AuditResult.audited_at == subq.c.latest))
        .subquery()
    )
    rows = (await db.execute(
        select(
            latest_q.c.organization_id,
            latest_q.c.organization_name,
            func.avg(latest_q.c.overall_score).label("avg_score"),
            func.count(latest_q.c.dataset_id).label("dataset_count"),
            func.min(latest_q.c.overall_score).label("min_score"),
            func.max(latest_q.c.overall_score).label("max_score"),
        )
        .group_by(latest_q.c.organization_id, latest_q.c.organization_name)
        .order_by(desc("avg_score"))
    )).all()
    return [
        {
            "organization_id": r.organization_id,
            "organization_name": r.organization_name,
            "avg_score": round(float(r.avg_score or 0), 1),
            "dataset_count": r.dataset_count,
            "min_score": round(float(r.min_score or 0), 1),
            "max_score": round(float(r.max_score or 0), 1),
        }
        for r in rows
    ]


@app.get("/api/stats", summary="Overall platform statistics")
async def platform_stats(db: AsyncSession = Depends(get_db)):
    subq = (
        select(AuditResult.dataset_id, func.max(AuditResult.audited_at).label("latest"))
        .group_by(AuditResult.dataset_id)
        .subquery()
    )
    latest_q = (
        select(AuditResult)
        .join(subq, (AuditResult.dataset_id == subq.c.dataset_id) &
                    (AuditResult.audited_at == subq.c.latest))
        .subquery()
    )
    stats = (await db.execute(
        select(
            func.count(latest_q.c.dataset_id).label("total_datasets"),
            func.avg(latest_q.c.overall_score).label("avg_score"),
            func.count(latest_q.c.organization_id.distinct()).label("total_orgs"),
        )
    )).first()

    grade_rows = (await db.execute(
        select(latest_q.c.grade, func.count(latest_q.c.grade).label("cnt"))
        .group_by(latest_q.c.grade)
    )).all()

    return {
        "total_datasets": stats.total_datasets or 0,
        "avg_score": round(float(stats.avg_score or 0), 1),
        "total_organizations": stats.total_orgs or 0,
        "grade_distribution": {r.grade: r.cnt for r in grade_rows},
    }


# ── Routes: Audit Triggers ─────────────────────────────────────────────────────

def _extract_dataset_id(url_or_id: str) -> Optional[str]:
    """
    Accept either:
      - A plain dataset ID: "my-dataset-name"
      - A data.gov.sa URL: "https://open.data.gov.sa/en/datasets/view/abc-123"
      - A CKAN URL:        "https://open.data.gov.sa/dataset/abc-123"
    Returns the dataset ID string, or None if input is invalid.
    """
    url_or_id = url_or_id.strip()
    m = re.search(r"/datasets?/(?:view/)?([A-Za-z0-9][A-Za-z0-9_\-]{2,149})(?:[/?#]|$)", url_or_id)
    if m:
        return m.group(1)
    if _VALID_ID_RE.match(url_or_id):
        return url_or_id
    return None


@app.post("/api/audit/raw", summary="Audit a dataset from raw CKAN JSON fetched by the browser")
async def audit_raw(
    dataset: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Accept a raw CKAN package dict (fetched client-side to bypass WAF)
    and run a full quality audit on it.
    """
    if not dataset.get("id") and not dataset.get("name"):
        raise HTTPException(400, "Dataset JSON must contain an 'id' or 'name' field")
    async with _http_client() as http:
        try:
            report, org_id, org_name = await _audit_dataset(dataset, http)
        except Exception as exc:
            raise HTTPException(500, f"Audit failed: {exc}")
    await _save_report(report, org_id, org_name, db)
    return {"message": "Audit complete", "report": report.to_dict()}


@app.post("/api/audit/bulk", summary="Audit multiple datasets (background job)")
async def audit_bulk(
    background_tasks: BackgroundTasks,
    limit: int = Query(50, ge=1, le=500),
):
    """Trigger a background bulk audit of the latest N datasets from data.gov.sa."""
    background_tasks.add_task(_bulk_audit_task, limit)
    return {"message": f"Bulk audit of up to {limit} datasets started in background"}


class SeedPayload(BaseModel):
    urls: list[str]


@app.post("/api/audit/seed", summary="Audit a list of dataset URLs/IDs in bulk")
async def audit_seed(
    payload: SeedPayload,
    background_tasks: BackgroundTasks,
):
    """
    Accept a JSON body with a list of dataset URLs or IDs and audit them all.
    Useful when the portal blocks automated discovery — paste URLs from the browser.
    Example body: {"urls": ["https://open.data.gov.sa/en/datasets/view/abc", "def-id"]}
    """
    ids = [_extract_dataset_id(u) for u in payload.urls if u.strip()]
    ids = list(dict.fromkeys(i for i in ids if i is not None))
    if not ids:
        raise HTTPException(400, "No valid dataset IDs found in the provided list")
    background_tasks.add_task(_seed_audit_task, ids)
    return {"message": f"Seeded audit of {len(ids)} datasets started in background", "ids": ids}


@app.post("/api/audit/by-url", summary="Audit a dataset by its data.gov.sa URL or ID")
async def audit_by_url(
    url: str = Query(..., description="Full dataset URL or plain dataset ID"),
    db: AsyncSession = Depends(get_db),
):
    dataset_id = _extract_dataset_id(url)
    if not dataset_id:
        raise HTTPException(
            400,
            "Could not extract a valid dataset ID. "
            "Paste a URL like https://open.data.gov.sa/en/datasets/view/my-dataset "
            "or a plain slug like 'my-dataset'."
        )
    return await audit_single(dataset_id, db)


@app.post("/api/audit/{dataset_id}", summary="Audit a single dataset by ID")
async def audit_single(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Fetch dataset from data.gov.sa and run quality audit."""
    async with _http_client() as http:
        async with CKANClient(CKAN_BASE) as ckan:
            try:
                dataset = await ckan.package_show(dataset_id)
            except Exception as exc:
                logger.exception("Failed to fetch dataset %s from CKAN", dataset_id)
                raise HTTPException(
                    502,
                    f"Could not fetch dataset from CKAN: {type(exc).__name__}: {exc}",
                )

        try:
            report, org_id, org_name = await _audit_dataset(dataset, http)
        except Exception as exc:
            raise HTTPException(500, f"Audit failed: {exc}")

    await _save_report(report, org_id, org_name, db)
    return {"message": "Audit complete", "report": report.to_dict()}


async def _bulk_audit_task(limit: int):
    """Background task: fetch and audit N datasets."""
    async with _http_client() as http:
        async with CKANClient(CKAN_BASE) as ckan:
            datasets = await ckan.get_all_datasets(limit=limit)

        async with AsyncSessionLocal() as db:
            for dataset in datasets:
                try:
                    report, org_id, org_name = await _audit_dataset(dataset, http)
                    await _save_report(report, org_id, org_name, db)
                    logger.info("Audited %s → %.1f", dataset.get("id"), report.overall_score)
                except Exception as exc:
                    logger.error("Failed to audit %s: %s", dataset.get("id"), exc)
                await asyncio.sleep(0.5)

    await _recluster()


async def _seed_audit_task(ids: list[str]):
    """Audit a pre-supplied list of dataset IDs via package_show."""
    async with _http_client() as http:
        async with CKANClient(CKAN_BASE) as ckan:
            async with AsyncSessionLocal() as db:
                for ds_id in ids:
                    try:
                        dataset = await ckan.package_show(ds_id)
                        report, org_id, org_name = await _audit_dataset(dataset, http)
                        await _save_report(report, org_id, org_name, db)
                        logger.info("Seeded audit %s → %.1f", ds_id, report.overall_score)
                    except Exception as exc:
                        logger.error("Seed audit failed for %s: %s", ds_id, exc)
                    await asyncio.sleep(0.5)
    await _recluster()


async def _recluster():
    """After a bulk audit, recompute K-means clusters and update DB."""
    async with AsyncSessionLocal() as db:
        subq = (
            select(AuditResult.dataset_id, func.max(AuditResult.audited_at).label("latest"))
            .group_by(AuditResult.dataset_id)
            .subquery()
        )
        rows = (await db.execute(
            select(AuditResult).join(
                subq, (AuditResult.dataset_id == subq.c.dataset_id) &
                      (AuditResult.audited_at == subq.c.latest)
            )
        )).scalars().all()

        if len(rows) < 4:
            return

        labels = cluster_datasets([r.dimension_scores or {} for r in rows])
        for row, label in zip(rows, labels):
            row.ml_quality_cluster = label
        await db.commit()


# ── Routes: Trend ──────────────────────────────────────────────────────────────

@app.get("/api/trends", summary="Platform-wide quality trends over time")
async def trends(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            cast(AuditResult.audited_at, Date).label("day"),
            func.avg(AuditResult.overall_score).label("avg_score"),
            func.count(AuditResult.id).label("audits"),
        )
        .group_by("day")
        .order_by("day")
    )).all()
    return [{"day": str(r.day), "avg_score": round(float(r.avg_score or 0), 1), "audits": r.audits}
            for r in rows]


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/debug/next-data", summary="Inspect __NEXT_DATA__ for a portal URL")
async def debug_next_data(url: str = Query(...)):
    """Fetch a portal page and return the raw __NEXT_DATA__ JSON for debugging."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=25.0) as client:
        await client.get("https://open.data.gov.sa/", timeout=15.0)
        resp = await client.get(url, timeout=25.0)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', resp.text, re.DOTALL)
    if not m:
        return {"error": "No __NEXT_DATA__ found", "status_code": resp.status_code, "html_snippet": resp.text[:500]}
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        return {"error": str(e), "raw": m.group(1)[:2000]}
    return data
