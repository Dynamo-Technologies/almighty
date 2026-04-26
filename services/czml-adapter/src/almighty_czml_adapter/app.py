"""FastAPI shell — exposes only ``/healthz`` for liveness probes.

The adapter's actual work runs in the async ``AdapterRunner`` (see
runner.py); the FastAPI app exists so the service can be deployed
behind a standard HTTP probe and admin tooling can introspect.
"""

from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(
    title="Almighty CZML adapter",
    version="0.1.0",
    description="Live PyRapide -> CZML adapter (WS-503).",
)


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
