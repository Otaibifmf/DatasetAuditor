"""
Completeness check — what percentage of cells/fields are non-empty.
Works on both dataset-level metadata and resource-level data (if downloadable CSV).
"""

from __future__ import annotations
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CompletenessResult:
    score: float                    # 0–100
    missing_pct: float              # overall % missing
    column_missing: dict[str, float] = field(default_factory=dict)
    total_rows: int = 0
    total_cols: int = 0
    issues: list[str] = field(default_factory=list)
    sampled: bool = False           # True if only first N rows were checked


MAX_ROWS = 10_000
SAMPLE_BYTES = 5 * 1024 * 1024     # 5 MB cap for download


async def check_completeness(
    dataset: dict,
    http_client: Optional[httpx.AsyncClient] = None,
) -> CompletenessResult:
    """
    1. Check metadata completeness (title, description, license, etc.)
    2. If CSV resource available, download and check cell completeness.
    """
    issues: list[str] = []

    # ── 1. Metadata completeness ──────────────────────────────────────────
    meta_fields = ["title", "notes", "license_id", "author", "maintainer",
                   "tags", "groups", "resources"]
    missing_meta = [f for f in meta_fields if not dataset.get(f)]
    meta_score = 100 - (len(missing_meta) / len(meta_fields) * 100)
    if missing_meta:
        issues.append(f"Missing metadata fields: {', '.join(missing_meta)}")

    # ── 2. Resource (tabular) completeness ────────────────────────────────
    resources = dataset.get("resources", [])
    csv_resource = next(
        (r for r in resources if r.get("format", "").upper() in ("CSV", "XLSX", "XLS")),
        None,
    )

    if not csv_resource or not http_client:
        return CompletenessResult(
            score=meta_score,
            missing_pct=100 - meta_score,
            issues=issues,
        )

    url = csv_resource.get("url", "")
    if not url:
        return CompletenessResult(score=meta_score, missing_pct=100 - meta_score, issues=issues)

    try:
        async with http_client.stream("GET", url, timeout=20.0) as resp:
            if resp.status_code >= 400:
                issues.append(f"Resource download failed: HTTP {resp.status_code}")
                return CompletenessResult(score=meta_score, missing_pct=100 - meta_score, issues=issues)
            chunks = []
            total = 0
            async for chunk in resp.aiter_bytes(chunk_size=65536):
                chunks.append(chunk)
                total += len(chunk)
                if total >= SAMPLE_BYTES:
                    break
            raw = b"".join(chunks)

        fmt = csv_resource.get("format", "").upper()
        if fmt in ("XLSX", "XLS"):
            df = pd.read_excel(io.BytesIO(raw), nrows=MAX_ROWS)
            sampled = True
        else:
            df = pd.read_csv(io.BytesIO(raw), nrows=MAX_ROWS, on_bad_lines="skip", low_memory=False)
            sampled = total >= SAMPLE_BYTES

        if df.empty:
            issues.append("Resource downloaded but DataFrame is empty")
            return CompletenessResult(score=meta_score, missing_pct=100 - meta_score, issues=issues)

        total_cells = df.size
        missing_cells = df.isnull().sum().sum() + (df == "").sum().sum()
        missing_pct = (missing_cells / total_cells * 100) if total_cells else 0

        col_missing = {
            col: round(df[col].isnull().mean() * 100, 1)
            for col in df.columns
        }
        high_missing = [c for c, v in col_missing.items() if v > 20]
        if high_missing:
            issues.append(
                f"{len(high_missing)} column(s) >20% missing: {', '.join(high_missing[:5])}"
            )

        data_score = max(0.0, 100 - missing_pct * 1.5)  # penalise missing harder
        combined = meta_score * 0.3 + data_score * 0.7
        return CompletenessResult(
            score=round(combined, 1),
            missing_pct=round(missing_pct, 2),
            column_missing=col_missing,
            total_rows=len(df),
            total_cols=len(df.columns),
            issues=issues,
            sampled=sampled,
        )

    except Exception as exc:
        logger.warning("Completeness check failed for %s: %s", url, exc)
        issues.append(f"Could not analyse resource: {exc}")
        return CompletenessResult(
            score=meta_score * 0.5,
            missing_pct=50.0,
            issues=issues,
        )
