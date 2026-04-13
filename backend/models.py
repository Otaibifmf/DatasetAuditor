"""
SQLAlchemy ORM models for persisting audit results over time.
"""

from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Float, Integer, Text, DateTime, JSON, Boolean, Index
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class AuditResult(Base):
    __tablename__ = "audit_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(255), nullable=False, index=True)
    dataset_title = Column(Text)
    organization_id = Column(String(255), index=True)
    organization_name = Column(Text)

    # Scores
    overall_score = Column(Float)
    grade = Column(String(2))
    completeness_score = Column(Float)
    freshness_score = Column(Float)
    consistency_score = Column(Float)
    uniqueness_score = Column(Float)
    validity_score = Column(Float)
    accessibility_score = Column(Float)
    metadata_quality_score = Column(Float)

    # ML outputs
    ml_topic = Column(String(100))
    ml_abandoned_probability = Column(Float)
    ml_quality_cluster = Column(Integer)

    # Detail blobs
    dimension_scores = Column(JSON)
    all_issues = Column(JSON)
    details = Column(JSON)

    # Metadata
    days_since_update = Column(Integer)
    total_rows = Column(Integer)
    total_resources = Column(Integer)
    has_csv = Column(Boolean, default=False)

    audited_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_audit_org_date", "organization_id", "audited_at"),
        Index("ix_audit_dataset_date", "dataset_id", "audited_at"),
    )


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(255), primary_key=True)
    name = Column(Text)
    display_name = Column(Text)
    dataset_count = Column(Integer, default=0)
    avg_score = Column(Float)
    last_synced = Column(DateTime(timezone=True))
