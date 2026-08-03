# portal-relay

Transparent proxy for `open.data.gov.sa/data/api/*`. Only needed when the backend runs
**outside** Saudi Arabia.

The portal applies three independent checks, and a request must clear all three:

1. **Source IP must be Saudi.** Non-Saudi IPs get a TCP connect timeout — the connection is
   dropped before TLS, so no header or User-Agent trick can work around it. This is the
   reason the relay exists and why it must run on a KSA host.
2. **Full browser headers.** A bare `Mozilla/5.0` gets the `Request Rejected` WAF page even
   from a correct Saudi IP. `BROWSER_HEADERS` in `relay.py` handles this and must stay in
   sync with `backend/ckan_client.py`.
3. **Path allowlist.** Only `/data/api/datasets` and `/data/api/datasets/resources` are
   permitted; other paths under `/data/api/` are rejected.

## Deploy

```bash
docker build -t portal-relay .
docker run -d --restart unless-stopped -p 8080:8080 \
  -e RELAY_KEY="<pick-a-long-random-string>" \
  --name portal-relay portal-relay
```

Put HTTPS in front of it (e.g. Caddy with automatic Let's Encrypt):

```
# Caddyfile
relay.<yourdomain>.com {
    reverse_proxy localhost:8080
}
```

## Verify

```bash
curl "https://relay.<yourdomain>.com/data/api/datasets?version=-1&dataset=test" \
  -H "x-relay-key: <your-key>"
```

Expect the portal's JSON — `404 {"message":"Dataset Not Found"}` for a fake id. Anything
else means the relay host is not usable:

| Symptom | Cause |
|---------|-------|
| `ConnectTimeout` | The host's IP is not Saudi, or its datacenter range is blocked. Try a different Saudi host. |
| `Request Rejected` HTML | Reached the portal but the WAF refused it — check `BROWSER_HEADERS` and that the path is allowlisted. |

**Verify this returns JSON before pointing the backend at the relay.** A Saudi *consumer
ISP* address is known to work; whether Saudi *datacenter* ranges (AWS me-central-2, Oracle
Jeddah, local VPS providers) also pass gate 1 must be confirmed per-host with the curl above.
