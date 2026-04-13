"""
Dataset clustering — group datasets by quality profile using K-Means.
Finds which ministry/agency consistently produces low-quality data.
"""

from __future__ import annotations
import logging
from typing import Optional

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

N_CLUSTERS = 4

CLUSTER_LABELS = {
    0: "High Quality",
    1: "Acceptable Quality",
    2: "Poor Quality",
    3: "Critical Issues",
}


def cluster_datasets(dimension_scores_list: list[dict]) -> list[int]:
    """
    Takes a list of dimension-score dicts and returns a cluster label per dataset.
    Cluster labels are ordered by quality: 0=best, 3=worst.
    """
    if len(dimension_scores_list) < N_CLUSTERS:
        return [0] * len(dimension_scores_list)

    keys = ["completeness", "freshness", "consistency", "uniqueness",
            "validity", "accessibility", "metadata_quality"]

    X = []
    for scores in dimension_scores_list:
        row = [float(scores.get(k, 50.0)) for k in keys]
        X.append(row)

    X_arr = np.array(X)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_arr)

    kmeans = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    raw_labels = kmeans.fit_predict(X_scaled)

    # Reorder clusters by mean overall score (0 = highest quality)
    means = []
    for c in range(N_CLUSTERS):
        mask = raw_labels == c
        if mask.any():
            means.append((c, X_arr[mask].mean()))
        else:
            means.append((c, 0.0))
    means.sort(key=lambda x: -x[1])  # descending quality
    remap = {old: new for new, (old, _) in enumerate(means)}

    return [remap[int(l)] for l in raw_labels]


def get_cluster_label(cluster_id: int) -> str:
    return CLUSTER_LABELS.get(cluster_id, "Unknown")
