"""
Metadata quality check — description richness, license presence, proper tagging, etc.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field


@dataclass
class MetadataResult:
    score: float
    has_description: bool
    description_length: int
    description_too_vague: bool
    has_license: bool
    has_tags: bool
    tag_count: int
    has_author: bool
    has_temporal_coverage: bool
    has_spatial_coverage: bool
    issues: list[str] = field(default_factory=list)


# Vague/copy-pasted boilerplate phrases
VAGUE_PHRASES = [
    "this dataset contains",
    "data about",
    "هذه البيانات",
    "بيانات عن",
    "n/a",
    "na",
    "none",
    "تجريبي",
    "test",
    "no description",
    "لا يوجد",
]

MIN_DESCRIPTION_LENGTH = 50
GOOD_DESCRIPTION_LENGTH = 150


def check_metadata_quality(dataset: dict) -> MetadataResult:
    issues: list[str] = []
    score = 100.0

    # Description
    desc = (dataset.get("notes") or dataset.get("description") or "").strip()
    has_desc = len(desc) >= 10
    desc_len = len(desc)
    too_vague = False

    if not has_desc:
        issues.append("Missing description")
        score -= 20
    elif desc_len < MIN_DESCRIPTION_LENGTH:
        issues.append(f"Description too short ({desc_len} chars, recommend ≥{MIN_DESCRIPTION_LENGTH})")
        score -= 10
    else:
        desc_lower = desc.lower()
        if any(phrase in desc_lower for phrase in VAGUE_PHRASES):
            too_vague = True
            issues.append("Description appears to be vague or boilerplate text")
            score -= 10
        if desc_len >= GOOD_DESCRIPTION_LENGTH:
            pass  # good

    # License
    license_id = dataset.get("license_id") or dataset.get("license_title") or ""
    has_license = bool(license_id) and license_id.lower() not in ("", "none", "notspecified", "other")
    if not has_license:
        issues.append("No license specified — users cannot determine reuse rights")
        score -= 15

    # Tags
    tags = dataset.get("tags", [])
    tag_count = len(tags)
    has_tags = tag_count >= 2
    if not has_tags:
        issues.append(f"Too few tags ({tag_count}) — makes dataset undiscoverable")
        score -= 10

    # Author/maintainer
    has_author = bool(dataset.get("author") or dataset.get("maintainer"))
    if not has_author:
        issues.append("No author or maintainer contact listed")
        score -= 5

    # Temporal coverage
    temporal_fields = ("temporal_start", "temporal_end", "temporal_coverage",
                       "date_released", "coverage_start_date", "coverage_end_date")
    has_temporal = any(dataset.get(f) for f in temporal_fields)
    if not has_temporal:
        score -= 5  # soft penalty — many datasets don't have this

    # Spatial coverage
    spatial_fields = ("spatial", "spatial_uri", "coverage", "geographic_coverage", "منطقة")
    has_spatial = any(dataset.get(f) for f in spatial_fields)

    # Title quality
    title = (dataset.get("title") or dataset.get("name") or "").strip()
    if len(title) < 5:
        issues.append("Title is missing or too short")
        score -= 10
    elif re.match(r"^[a-z0-9_-]+$", title):
        issues.append("Title appears to be a technical ID rather than a human-readable name")
        score -= 5

    return MetadataResult(
        score=max(0.0, round(score, 1)),
        has_description=has_desc,
        description_length=desc_len,
        description_too_vague=too_vague,
        has_license=has_license,
        has_tags=has_tags,
        tag_count=tag_count,
        has_author=has_author,
        has_temporal_coverage=has_temporal,
        has_spatial_coverage=has_spatial,
        issues=issues,
    )
