"""
Uniqueness check — detect duplicate rows.
"""

from __future__ import annotations
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

MAX_ROWS = 10_000
SAMPLE_BYTES = 5 * 1024 * 1024


@dataclass
class UniquenessResult:
    score: float
    duplicate_pct: float
    duplicate_count: int
    total_rows: int
    issues: list[str] = field(default_factory=list)


async def check_uniqueness(
    dataset: dict,
    http_client: Optional[httpx.AsyncClient] = None,
) -> UniquenessResult:
    issues: list[str] = []

    resources = dataset.get("resources", [])
    csv_resource = next(
        (r for r in resources if r.get("format", "").upper() in ("CSV", "XLSX", "XLS")),
        None,
    )

    if not csv_resource or not http_client:
        return UniquenessResult(score=100.0, duplicate_pct=0.0, duplicate_count=0, total_rows=0)

    url = csv_resource.get("url", "")
    if not url:
        return UniquenessResult(score=100.0, duplicate_pct=0.0, duplicate_count=0, total_rows=0)

    try:
        async with http_client.stream("GET", url, timeout=20.0) as resp:
            if resp.status_code >= 400:
                return UniquenessResult(score=100.0, duplicate_pct=0.0, duplicate_count=0, total_rows=0)
            chunks = []
            total = 0
            async for chunk in resp.aiter_bytes(65536):
                chunks.append(chunk)
                total += len(chunk)
                if total >= SAMPLE_BYTES:
                    break
            raw = b"".join(chunks)

        fmt = csv_resource.get("format", "").upper()
        if fmt in ("XLSX", "XLS"):
            df = pd.read_excel(io.BytesIO(raw), nrows=MAX_ROWS)
        else:
            df = pd.read_csv(io.BytesIO(raw), nrows=MAX_ROWS, on_bad_lines="skip", low_memory=False)

        if df.empty:
            return UniquenessResult(score=100.0, duplicate_pct=0.0, duplicate_count=0, total_rows=0)

        n_rows = len(df)
        n_dupes = int(df.duplicated().sum())
        dupe_pct = n_dupes / n_rows * 100 if n_rows else 0

        # Score: exponential penalty for duplicates
        score = max(0.0, 100 - dupe_pct * 3)

        if dupe_pct > 5:
            issues.append(
                f"{n_dupes} duplicate rows ({dupe_pct:.1f}% of dataset)"
            )
        if dupe_pct > 20:
            issues.append("High duplicate rate — data may not be deduplicated before publishing")

        return UniquenessResult(
            score=round(score, 1),
            duplicate_pct=round(dupe_pct, 2),
            duplicate_count=n_dupes,
            total_rows=n_rows,
            issues=issues,
        )

    except Exception as exc:
        logger.warning("Uniqueness check failed: %s", exc)
        issues.append(f"Could not analyse resource: {exc}")
        return UniquenessResult(score=50.0, duplicate_pct=0.0, duplicate_count=0, total_rows=0, issues=issues)
