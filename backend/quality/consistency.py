"""
Consistency check — uniform formats, correct column types, no mixed-language column names.
"""

from __future__ import annotations
import io
import re
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
import pandas as pd

logger = logging.getLogger(__name__)

MAX_ROWS = 5_000
SAMPLE_BYTES = 3 * 1024 * 1024

# Regex patterns
ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),                # ISO
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),                # DD/MM/YYYY
    re.compile(r"^\d{2}-\d{2}-\d{4}$"),                # DD-MM-YYYY
    re.compile(r"^\d{4}/\d{2}/\d{2}$"),                # YYYY/MM/DD
]


@dataclass
class ConsistencyResult:
    score: float
    mixed_language_columns: list[str] = field(default_factory=list)
    inconsistent_date_cols: list[str] = field(default_factory=list)
    mixed_type_cols: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


def _has_mixed_language(columns: list[str]) -> list[str]:
    has_arabic = any(ARABIC_RE.search(c) for c in columns)
    has_latin = any(re.search(r"[a-zA-Z]", c) for c in columns)
    if has_arabic and has_latin:
        return [c for c in columns if ARABIC_RE.search(c)]
    return []


def _check_date_consistency(series: pd.Series) -> bool:
    """Returns True if date column uses multiple formats."""
    non_null = series.dropna().astype(str).head(200)
    if len(non_null) < 10:
        return False
    fmt_counts = [0] * len(DATE_PATTERNS)
    for val in non_null:
        for i, pat in enumerate(DATE_PATTERNS):
            if pat.match(val.strip()):
                fmt_counts[i] += 1
                break
    used = sum(1 for c in fmt_counts if c > 0)
    return used > 1


def _check_type_consistency(series: pd.Series) -> bool:
    """Returns True if a numeric-looking column has non-numeric values mixed in."""
    non_null = series.dropna().astype(str).head(200)
    numeric = sum(1 for v in non_null if re.match(r"^-?\d+(\.\d+)?$", v.strip()))
    ratio = numeric / len(non_null) if len(non_null) else 0
    return 0.1 < ratio < 0.9  # mixed


async def check_consistency(
    dataset: dict,
    http_client: Optional[httpx.AsyncClient] = None,
) -> ConsistencyResult:
    issues: list[str] = []
    score = 100.0
    mixed_lang = []
    bad_dates = []
    mixed_types = []

    resources = dataset.get("resources", [])
    csv_resource = next(
        (r for r in resources if r.get("format", "").upper() in ("CSV", "XLSX", "XLS")),
        None,
    )

    if not csv_resource or not http_client:
        # Still check resource format consistency
        formats = [r.get("format", "").upper() for r in resources if r.get("format")]
        if len(set(formats)) > 3:
            issues.append(f"Many different resource formats: {set(formats)}")
            score -= 10
        return ConsistencyResult(score=score, issues=issues)

    url = csv_resource.get("url", "")
    if not url:
        return ConsistencyResult(score=score, issues=issues)

    try:
        async with http_client.stream("GET", url, timeout=20.0) as resp:
            if resp.status_code >= 400:
                return ConsistencyResult(score=score, issues=issues)
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
            return ConsistencyResult(score=score, issues=issues)

        columns = list(df.columns)

        # Language consistency in column names
        mixed_lang = _has_mixed_language(columns)
        if mixed_lang:
            issues.append(f"Mixed Arabic/English column names ({len(mixed_lang)} Arabic columns)")
            score -= 15

        # Date format consistency
        date_candidate_cols = [
            c for c in columns
            if any(k in str(c).lower() for k in ("date", "time", "تاريخ", "year", "سنة"))
        ]
        for col in date_candidate_cols:
            if _check_date_consistency(df[col]):
                bad_dates.append(col)
        if bad_dates:
            issues.append(f"Inconsistent date formats in: {', '.join(bad_dates)}")
            score -= 10 * len(bad_dates)

        # Type consistency
        for col in df.select_dtypes(include="object").columns:
            if _check_type_consistency(df[col]):
                mixed_types.append(col)
        if mixed_types:
            issues.append(f"Mixed numeric/text values in: {', '.join(mixed_types[:5])}")
            score -= 5 * min(len(mixed_types), 4)

        return ConsistencyResult(
            score=max(0.0, round(score, 1)),
            mixed_language_columns=mixed_lang,
            inconsistent_date_cols=bad_dates,
            mixed_type_cols=mixed_types,
            issues=issues,
        )

    except Exception as exc:
        logger.warning("Consistency check failed: %s", exc)
        issues.append(f"Could not analyse resource: {exc}")
        return ConsistencyResult(score=50.0, issues=issues)
