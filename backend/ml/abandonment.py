"""
Abandonment predictor — estimate probability a dataset will not be updated again.

Uses a heuristic rule-based model that can be replaced by a trained sklearn
classifier once enough historical labelled data is collected.

Features used:
  - days_since_last_update
  - update_frequency_stated (bool)
  - resource_count
  - has_broken_links (bool)
  - description_length
  - tag_count
  - download_count (if available)
"""

from __future__ import annotations
import pickle
import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent / "abandonment_model.pkl"


def _feature_vector(
    days_since_update: Optional[int],
    update_frequency_stated: bool,
    resource_count: int,
    has_broken_links: bool,
    description_length: int,
    tag_count: int,
) -> np.ndarray:
    return np.array([
        min(days_since_update or 9999, 9999) / 9999,
        1.0 if update_frequency_stated else 0.0,
        min(resource_count, 20) / 20,
        1.0 if has_broken_links else 0.0,
        min(description_length, 1000) / 1000,
        min(tag_count, 20) / 20,
    ], dtype=np.float32)


def _heuristic_predict(features: np.ndarray) -> float:
    """Rule-based fallback when no trained model is available."""
    days_norm, has_freq, res_norm, broken, desc_norm, tag_norm = features

    score = 0.0
    score += days_norm * 0.4          # older = more likely abandoned
    score += (1 - has_freq) * 0.15   # no stated frequency = red flag
    score += broken * 0.2            # broken links
    score += (1 - desc_norm) * 0.1   # short/no description
    score += (1 - tag_norm) * 0.1    # no tags
    score += (1 - res_norm) * 0.05   # no resources

    return float(np.clip(score, 0.0, 1.0))


def predict_abandonment(
    days_since_update: Optional[int],
    update_frequency_stated: bool,
    resource_count: int,
    has_broken_links: bool,
    description_length: int,
    tag_count: int,
) -> float:
    """Returns a probability 0–1 that this dataset is abandoned."""
    features = _feature_vector(
        days_since_update,
        update_frequency_stated,
        resource_count,
        has_broken_links,
        description_length,
        tag_count,
    )

    # Try to load trained sklearn model
    if MODEL_PATH.exists():
        try:
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            prob = model.predict_proba(features.reshape(1, -1))[0][1]
            return float(prob)
        except Exception as exc:
            logger.warning("Could not use trained model: %s — falling back to heuristics", exc)

    return _heuristic_predict(features)
