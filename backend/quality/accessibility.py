"""
Accessibility check — are download links alive and in open formats?
"""

from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OPEN_FORMATS = {"CSV", "JSON", "XML", "XLSX", "XLS", "ODS", "GEOJSON", "KML", "RDF"}
PROPRIETARY_FORMATS = {"PDF", "DOC", "DOCX", "PPT", "PPTX"}


@dataclass
class AccessibilityResult:
    score: float
    working_links: int
    broken_links: int
    total_links: int
    open_format_pct: float
    broken_resources: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)


async def _check_url(client: httpx.AsyncClient, url: str) -> tuple[str, bool, int]:
    try:
        resp = await client.head(url, timeout=8.0, follow_redirects=True)
        ok = resp.status_code < 400
        if not ok:
            # Try GET if HEAD fails
            resp = await client.get(url, timeout=8.0)
            ok = resp.status_code < 400
        return url, ok, resp.status_code
    except Exception:
        return url, False, 0


async def check_accessibility(
    dataset: dict,
    http_client: Optional[httpx.AsyncClient] = None,
) -> AccessibilityResult:
    issues: list[str] = []
    resources = dataset.get("resources", [])

    if not resources:
        return AccessibilityResult(
            score=0.0,
            working_links=0,
            broken_links=0,
            total_links=0,
            open_format_pct=0.0,
            issues=["Dataset has no resources"],
        )

    urls = [(r.get("url", ""), r.get("name", r.get("id", "?"))) for r in resources if r.get("url")]
    formats = [r.get("format", "").upper() for r in resources if r.get("format")]

    # Format analysis (no HTTP needed)
    open_count = sum(1 for f in formats if f in OPEN_FORMATS)
    prop_count = sum(1 for f in formats if f in PROPRIETARY_FORMATS)
    open_pct = (open_count / len(formats) * 100) if formats else 0

    if prop_count and not open_count:
        issues.append("All resources are in proprietary formats (PDF/DOC/PPT) — not machine readable")

    # Link checking
    if not http_client or not urls:
        score = open_pct
        return AccessibilityResult(
            score=round(score, 1),
            working_links=0,
            broken_links=0,
            total_links=len(urls),
            open_format_pct=round(open_pct, 1),
            issues=issues,
        )

    tasks = [_check_url(http_client, url) for url, _ in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    working = 0
    broken = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            broken.append(urls[i][0])
        else:
            url, ok, status = result
            if ok:
                working += 1
            else:
                broken.append(url)

    total = len(urls)
    broken_count = len(broken)
    link_score = (working / total * 100) if total else 0

    if broken_count:
        issues.append(f"{broken_count}/{total} resource link(s) are broken or unreachable")

    combined = link_score * 0.6 + open_pct * 0.4

    return AccessibilityResult(
        score=round(combined, 1),
        working_links=working,
        broken_links=broken_count,
        total_links=total,
        open_format_pct=round(open_pct, 1),
        broken_resources=broken,
        issues=issues,
    )
