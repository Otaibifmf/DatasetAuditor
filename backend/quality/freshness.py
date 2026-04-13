"""
Freshness check — how recent is the data?
Uses metadata_modified, last_modified on resources, and temporal coverage if present.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import re


@dataclass
class FreshnessResult:
    score: float           # 0–100
    days_since_update: Optional[int]
    last_modified: Optional[str]
    expected_frequency: Optional[str]
    issues: list[str] = field(default_factory=list)


# Score thresholds (days since last update → score)
THRESHOLDS = [
    (30,   100),
    (90,   85),
    (180,  65),
    (365,  45),
    (730,  25),
    (1095, 10),
]

FREQ_DAYS = {
    "daily": 2,
    "weekly": 10,
    "monthly": 40,
    "quarterly": 100,
    "annual": 380,
    "yearly": 380,
    "bi-annual": 190,
    "irregular": None,
    "not planned": None,
}


def _parse_date(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(val, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    # Try ISO-8601 with timezone
    try:
        return datetime.fromisoformat(re.sub(r"Z$", "+00:00", val))
    except ValueError:
        return None


def _score_from_days(days: int) -> float:
    for threshold, score in THRESHOLDS:
        if days <= threshold:
            return float(score)
    return 5.0


def check_freshness(dataset: dict) -> FreshnessResult:
    issues: list[str] = []
    now = datetime.now(timezone.utc)

    # Gather candidate dates
    candidate_dates = []
    for field_name in ("metadata_modified", "metadata_created", "last_modified"):
        dt = _parse_date(dataset.get(field_name))
        if dt:
            candidate_dates.append(dt)

    # Also check resources
    for r in dataset.get("resources", []):
        for f in ("last_modified", "created", "metadata_modified"):
            dt = _parse_date(r.get(f))
            if dt:
                candidate_dates.append(dt)

    if not candidate_dates:
        issues.append("No modification date found in dataset or resources")
        return FreshnessResult(
            score=20.0,
            days_since_update=None,
            last_modified=None,
            expected_frequency=None,
            issues=issues,
        )

    latest = max(candidate_dates)
    days = (now - latest).days

    # Detect expected update frequency
    freq_raw = (
        dataset.get("update_frequency")
        or dataset.get("frequency")
        or dataset.get("accrual_periodicity")
        or ""
    ).lower()
    expected_freq = None
    freq_threshold = None
    for key, threshold in FREQ_DAYS.items():
        if key in freq_raw:
            expected_freq = key
            freq_threshold = threshold
            break

    score = _score_from_days(days)

    # Extra penalty if update is overdue relative to stated frequency
    if freq_threshold and days > freq_threshold * 1.5:
        overdue_days = days - freq_threshold
        issues.append(
            f"Dataset is {overdue_days} days overdue based on '{expected_freq}' update frequency"
        )
        score = max(0.0, score - 15)

    if days > 365:
        issues.append(f"Dataset not updated in {days} days ({days // 365} year(s))")
    elif days > 180:
        issues.append(f"Dataset not updated in {days} days (~{days // 30} months)")

    return FreshnessResult(
        score=round(score, 1),
        days_since_update=days,
        last_modified=latest.isoformat(),
        expected_frequency=expected_freq,
        issues=issues,
    )
