"""
Scoring system — combine all dimension scores into a single quality score.
Like a credit score but for government datasets.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .completeness import CompletenessResult
from .freshness import FreshnessResult
from .consistency import ConsistencyResult
from .uniqueness import UniquenessResult
from .validity import ValidityResult
from .accessibility import AccessibilityResult
from .metadata_quality import MetadataResult


# Weights must sum to 1.0
WEIGHTS = {
    "completeness":      0.20,
    "freshness":         0.20,
    "consistency":       0.15,
    "uniqueness":        0.10,
    "validity":          0.15,
    "accessibility":     0.10,
    "metadata_quality":  0.10,
}

GRADE_THRESHOLDS = [
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
    (0,  "F"),
]


def _grade(score: float) -> str:
    for threshold, letter in GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "F"


@dataclass
class QualityReport:
    dataset_id: str
    dataset_title: str
    organization: str
    overall_score: float
    grade: str
    dimension_scores: dict[str, float]
    all_issues: list[str]
    completeness: Optional[CompletenessResult] = None
    freshness: Optional[FreshnessResult] = None
    consistency: Optional[ConsistencyResult] = None
    uniqueness: Optional[UniquenessResult] = None
    validity: Optional[ValidityResult] = None
    accessibility: Optional[AccessibilityResult] = None
    metadata_quality: Optional[MetadataResult] = None
    ml_topic: Optional[str] = None
    ml_abandoned_probability: Optional[float] = None
    ml_quality_cluster: Optional[int] = None
    audited_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "dataset_id": self.dataset_id,
            "dataset_title": self.dataset_title,
            "organization": self.organization,
            "overall_score": self.overall_score,
            "grade": self.grade,
            "dimension_scores": self.dimension_scores,
            "all_issues": self.all_issues,
            "ml_topic": self.ml_topic,
            "ml_abandoned_probability": self.ml_abandoned_probability,
            "ml_quality_cluster": self.ml_quality_cluster,
            "audited_at": self.audited_at,
            "details": {
                "completeness": _result_to_dict(self.completeness),
                "freshness": _result_to_dict(self.freshness),
                "consistency": _result_to_dict(self.consistency),
                "uniqueness": _result_to_dict(self.uniqueness),
                "validity": _result_to_dict(self.validity),
                "accessibility": _result_to_dict(self.accessibility),
                "metadata_quality": _result_to_dict(self.metadata_quality),
            },
        }


def _result_to_dict(result) -> Optional[dict]:
    if result is None:
        return None
    return result.__dict__


def compute_scores(
    dataset_id: str,
    dataset_title: str,
    organization: str,
    completeness: CompletenessResult,
    freshness: FreshnessResult,
    consistency: ConsistencyResult,
    uniqueness: UniquenessResult,
    validity: ValidityResult,
    accessibility: AccessibilityResult,
    metadata_quality: MetadataResult,
) -> QualityReport:
    dim_scores = {
        "completeness":     completeness.score,
        "freshness":        freshness.score,
        "consistency":      consistency.score,
        "uniqueness":       uniqueness.score,
        "validity":         validity.score,
        "accessibility":    accessibility.score,
        "metadata_quality": metadata_quality.score,
    }

    overall = sum(dim_scores[k] * WEIGHTS[k] for k in WEIGHTS)
    overall = round(overall, 1)

    all_issues = []
    for result in [completeness, freshness, consistency, uniqueness, validity, accessibility, metadata_quality]:
        if result:
            all_issues.extend(result.issues)

    return QualityReport(
        dataset_id=dataset_id,
        dataset_title=dataset_title,
        organization=organization,
        overall_score=overall,
        grade=_grade(overall),
        dimension_scores=dim_scores,
        all_issues=all_issues,
        completeness=completeness,
        freshness=freshness,
        consistency=consistency,
        uniqueness=uniqueness,
        validity=validity,
        accessibility=accessibility,
        metadata_quality=metadata_quality,
    )
