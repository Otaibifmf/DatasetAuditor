"""
Tiny transparent proxy for open.data.gov.sa.
MUST run on a host with a Saudi (KSA) IP — that's the entire point.
Forwards /data/api/... requests to the portal and returns the JSON.

The portal's WAF applies two independent checks and BOTH must pass:
  1. Source IP must be Saudi  → why this runs on a KSA host.
  2. Request must carry full browser-like headers → why BROWSER_HEADERS below
     is not optional. Verified: from a Saudi IP, a bare "Mozilla/5.0"
     User-Agent gets the "Request Rejected" WAF page, while the full header
     set below returns real JSON.
"""

import os
import httpx
from fastapi import FastAPI, Request, Response, HTTPException

PORTAL_BASE = "https://open.data.gov.sa"
ALLOWED_PREFIX = "/data/api/"               # only forward the portal's data API, nothing else
RELAY_KEY = os.getenv("RELAY_KEY", "")      # optional shared secret; set the same value on the backend

# Must stay in sync with backend/ckan_client.py — the WAF rejects anything less.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
}

app = FastAPI()


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/{path:path}")
async def relay(path: str, request: Request):
    # Optional auth so this can't be used as an open proxy by strangers.
    if RELAY_KEY and request.headers.get("x-relay-key") != RELAY_KEY:
        raise HTTPException(status_code=401, detail="bad relay key")

    full_path = "/" + path
    if not full_path.startswith(ALLOWED_PREFIX):
        raise HTTPException(status_code=403, detail="path not allowed")

    target = PORTAL_BASE + full_path
    if request.url.query:
        target += "?" + request.url.query

    async with httpx.AsyncClient(timeout=30) as client:
        upstream = await client.get(
            target,
            headers=BROWSER_HEADERS,
        )

    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
        headers={"Access-Control-Allow-Origin": "*"},
    )
