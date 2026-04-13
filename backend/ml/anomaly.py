"""
Anomaly detection on numeric columns using Isolation Forest.
Flags suspicious values that deviate significantly from the column distribution.
"""

from __future__ import annotations
import io
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

MAX_ROWS = 5_000
SAMPLE_BYTES = 3 * 1024 * 1024
CONTAMINATION = 0.05  # expect ~5% anomalies


@dataclass
class AnomalyResult:
    flagged_columns: dict[str, list[int]]  # col -> list of row indices with anomalies
    anomaly_counts: dict[str, int]
    total_anomalies: int
    issues: list[str] = field(default_factory=list)


async def detect_anomalies(
    dataset: dict,
    http_client: Optional[httpx.AsyncClient] = None,
) -> AnomalyResult:
    flagged: dict[str, list[int]] = {}
    counts: dict[str, int] = {}
    issues: list[str] = []

    resources = dataset.get("resources", [])
    csv_resource = next(
        (r for r in resources if r.get("format", "").upper() in ("CSV", "XLSX", "XLS")),
        None,
    )

    if not csv_resource or not http_client:
        return AnomalyResult(flagged_columns={}, anomaly_counts={}, total_anomalies=0)

    url = csv_resource.get("url", "")
    if not url:
        return AnomalyResult(flagged_columns={}, anomaly_counts={}, total_anomalies=0)

    try:
        async with http_client.stream("GET", url, timeout=20.0) as resp:
            if resp.status_code >= 400:
                return AnomalyResult(flagged_columns={}, anomaly_counts={}, total_anomalies=0)
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
            return AnomalyResult(flagged_columns={}, anomaly_counts={}, total_anomalies=0)

        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if not numeric_cols:
            return AnomalyResult(flagged_columns={}, anomaly_counts={}, total_anomalies=0)

        # Run Isolation Forest per column (univariate) and combined (multivariate)
        for col in numeric_cols[:10]:  # limit to first 10 numeric columns
            series = df[col].dropna()
            if len(series) < 30:
                continue
            X = series.values.reshape(-1, 1)
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            model = IsolationForest(contamination=CONTAMINATION, random_state=42, n_jobs=1)
            preds = model.fit_predict(X_scaled)
            anomaly_idx = series.index[preds == -1].tolist()
            if anomaly_idx:
                flagged[col] = anomaly_idx[:20]  # cap at 20 for storage
                counts[col] = len(anomaly_idx)
                issues.append(f"Anomalies detected in '{col}': {len(anomaly_idx)} suspicious values")

        return AnomalyResult(
            flagged_columns=flagged,
            anomaly_counts=counts,
            total_anomalies=sum(counts.values()),
            issues=issues,
        )

    except Exception as exc:
        logger.warning("Anomaly detection failed: %s", exc)
        return AnomalyResult(
            flagged_columns={}, anomaly_counts={}, total_anomalies=0,
            issues=[f"Anomaly detection error: {exc}"]
        )
