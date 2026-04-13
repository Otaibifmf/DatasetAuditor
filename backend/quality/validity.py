"""
Validity check — values fall within expected/reasonable ranges.
Uses statistical outlier detection (IQR method) and known domain heuristics.
"""

from __future__ import annotations
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

MAX_ROWS = 10_000
SAMPLE_BYTES = 5 * 1024 * 1024

# Column name hints that imply 0–100 range (percentages)
PERCENTAGE_HINTS = ("pct", "percent", "rate", "ratio", "نسبة", "%")
# Column name hints for latitude/longitude
LAT_HINTS = ("lat", "latitude", "خط_عرض")
LON_HINTS = ("lon", "long", "longitude", "خط_طول")


@dataclass
class ValidityResult:
    score: float
    outlier_cols: dict[str, int] = field(default_factory=dict)  # col -> # outlier rows
    range_violations: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _col_matches(col: str, hints: tuple) -> bool:
    col_lower = col.lower()
    return any(h in col_lower for h in hints)


def _iqr_outliers(series: pd.Series) -> int:
    """Count rows outside 3×IQR fence."""
    q1, q3 = series.quantile(0.25), series.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return 0
    fence_lo = q1 - 3 * iqr
    fence_hi = q3 + 3 * iqr
    return int(((series < fence_lo) | (series > fence_hi)).sum())


async def check_validity(
    dataset: dict,
    http_client: Optional[httpx.AsyncClient] = None,
) -> ValidityResult:
    issues: list[str] = []
    outlier_cols: dict[str, int] = {}
    range_violations: list[str] = []
    score = 100.0

    resources = dataset.get("resources", [])
    csv_resource = next(
        (r for r in resources if r.get("format", "").upper() in ("CSV", "XLSX", "XLS")),
        None,
    )

    if not csv_resource or not http_client:
        return ValidityResult(score=score, issues=issues)

    url = csv_resource.get("url", "")
    if not url:
        return ValidityResult(score=score, issues=issues)

    try:
        async with http_client.stream("GET", url, timeout=20.0) as resp:
            if resp.status_code >= 400:
                return ValidityResult(score=score, issues=issues)
            chunks, total = [], 0
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
            return ValidityResult(score=score, issues=issues)

        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            series = df[col].dropna()
            if len(series) < 20:
                continue

            col_str = str(col)

            # Domain-specific range checks
            if _col_matches(col_str, PERCENTAGE_HINTS):
                bad = int(((series < 0) | (series > 100)).sum())
                if bad:
                    range_violations.append(f"{col_str}: {bad} values outside 0–100%")
                    score -= 5

            if _col_matches(col_str, LAT_HINTS):
                bad = int(((series < -90) | (series > 90)).sum())
                if bad:
                    range_violations.append(f"{col_str}: {bad} invalid latitudes")
                    score -= 5

            if _col_matches(col_str, LON_HINTS):
                bad = int(((series < -180) | (series > 180)).sum())
                if bad:
                    range_violations.append(f"{col_str}: {bad} invalid longitudes")
                    score -= 5

            # Statistical outliers
            n_outliers = _iqr_outliers(series)
            pct = n_outliers / len(series) * 100
            if pct > 1:
                outlier_cols[col_str] = n_outliers
                score -= min(5.0, pct * 0.5)

        if range_violations:
            issues.extend(range_violations)
        if outlier_cols:
            top = sorted(outlier_cols.items(), key=lambda x: -x[1])[:5]
            issues.append(
                f"Statistical outliers in: {', '.join(f'{c}({n})' for c, n in top)}"
            )

        return ValidityResult(
            score=max(0.0, round(score, 1)),
            outlier_cols=outlier_cols,
            range_violations=range_violations,
            issues=issues,
        )

    except Exception as exc:
        logger.warning("Validity check failed: %s", exc)
        issues.append(f"Could not analyse resource: {exc}")
        return ValidityResult(score=50.0, issues=issues)
