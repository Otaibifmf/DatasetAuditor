"""
Portal API client for open.data.gov.sa

Uses the official developer REST API (not CKAN) at /data/api/:
  - GET /data/api/datasets?version=-1&dataset=<id>           → dataset metadata
  - GET /data/api/datasets/resources?version=-1&dataset=<id> → resource list
"""

import asyncio
import logging
from typing import Optional
import httpx

from config import HTTP_TIMEOUT, PORTAL_API_BASE, RELAY_KEY

logger = logging.getLogger(__name__)

# Resolved in config.py — points at the portal directly, or at a Saudi-IP relay
# that mirrors the same /data/api/ path layout.
PORTAL_BASE = PORTAL_API_BASE
TIMEOUT = HTTP_TIMEOUT

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}


class CKANClient:
    """
    Wraps the portal's official /data/api/ endpoints and normalises
    responses into the CKAN-style dicts the rest of the codebase expects.
    """

    def __init__(self, base_url: str = PORTAL_BASE):
        self._base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        headers = dict(BROWSER_HEADERS)
        if RELAY_KEY:
            headers["x-relay-key"] = RELAY_KEY
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=TIMEOUT,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_):
        if self._client:
            await self._client.aclose()

    # ── Core fetch ────────────────────────────────────────────────────────────

    async def _get_json(self, path: str, **params) -> dict:
        url = f"{self._base_url}{path}"
        resp = await self._client.get(url, params={"version": -1, **params})
        resp.raise_for_status()
        return resp.json()

    # ── Public interface ──────────────────────────────────────────────────────

    async def package_show(self, dataset_id: str) -> dict:
        """Fetch full dataset metadata normalised to a CKAN-style dict."""
        info_task = self._get_json("/datasets", dataset=dataset_id)
        res_task  = self._get_json("/datasets/resources", dataset=dataset_id)

        info, res_data = await asyncio.gather(info_task, res_task,
                                              return_exceptions=True)

        if isinstance(info, Exception):
            raise ValueError(
                f"Could not fetch dataset {dataset_id}: {type(info).__name__}: {info}"
            )

        resources = []
        if not isinstance(res_data, Exception):
            resources = res_data.get("resources", [])

        pkg = _normalize_dataset(info, resources)
        logger.info("Fetched dataset %s — title=%s resources=%d",
                    dataset_id, pkg.get("title"), len(resources))
        return pkg

    async def get_all_datasets(self, limit: int = 500, progress_cb=None) -> list[dict]:
        """
        No public search/listing endpoint is available on this portal.
        Use the 'Paste URLs' seed feature to audit specific datasets.
        """
        logger.info("No listing endpoint available — use the seed/URL audit feature.")
        return []

    async def check_resource_url(self, url: str) -> tuple[bool, int]:
        """Check whether a resource URL is reachable."""
        try:
            resp = await self._client.head(url, timeout=10.0)
            return resp.status_code < 400, resp.status_code
        except Exception:
            try:
                resp = await self._client.get(url, timeout=10.0)
                return resp.status_code < 400, resp.status_code
            except Exception:
                return False, 0


# ── Normalisation ─────────────────────────────────────────────────────────────

def _normalize_dataset(info: dict, raw_resources: list) -> dict:
    """
    Map the portal's /data/api/datasets response to the CKAN-style dict
    expected by quality checkers and ML modules.
    """
    org_id   = info.get("organizationId", "")
    org_name = info.get("providerNameEn") or info.get("providerNameAr") or "Unknown"

    # Normalise tags: [{id, nameEn, nameAr}] → [{name: ...}]
    tags = [
        {"name": t.get("nameEn") or t.get("nameAr", "")}
        for t in info.get("tags", [])
        if t.get("nameEn") or t.get("nameAr")
    ]

    # Normalise resources
    resources = [_normalize_resource(r) for r in raw_resources]

    return {
        # Identity
        "id":   info.get("id", ""),
        "name": info.get("id", ""),

        # Title / description
        "title":       info.get("titleEn") or info.get("titleAr", ""),
        "notes":       info.get("descriptionEn") or info.get("descriptionAr", ""),
        "description": info.get("descriptionEn") or info.get("descriptionAr", ""),

        # Ownership
        "author":     org_name,
        "maintainer": org_name,
        "organization": {"id": org_id, "title": org_name, "name": org_id},

        # Licence — not exposed by the portal API
        "license_id":    "",
        "license_title": "",

        # Dates
        "metadata_modified": info.get("updatedAt", ""),
        "metadata_created":  info.get("createdAt", ""),
        "last_modified":     info.get("updatedAt", ""),

        # Update frequency (map to all aliases the quality checkers look for)
        "update_frequency":    info.get("updateFrequency", ""),
        "frequency":           info.get("updateFrequency", ""),
        "accrual_periodicity": info.get("updateFrequency", ""),

        # Coverage
        "temporal_coverage": info.get("timePeriod", ""),
        "language":          info.get("language", ""),

        # Taxonomy
        "tags":   tags,
        "groups": info.get("categories", []),

        # Resources
        "resources": resources,
    }


def _normalize_resource(r: dict) -> dict:
    return {
        "id":            r.get("id", ""),
        "name":          r.get("name", ""),
        "description":   r.get("descriptionEn") or r.get("descriptionAr", ""),
        "format":        r.get("format", ""),
        "url":           r.get("downloadUrl", ""),
        "last_modified": r.get("updatedAt", ""),
        "created":       r.get("createdAt", ""),
        "metadata_modified": r.get("updatedAt", ""),
    }
