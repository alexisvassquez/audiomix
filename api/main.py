# AudioMIX
# api/main.py
#
# FastAPI application entrypoint for the AudioMIX
# bridge layer.
# This is a local-first bridge and should only ever be
# reached by the AudioMIX Electron client on the same
# machine, not over network.
# Auth is always required with no dev-mode bypass.
# Token must be set for the server to start.

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os
import secrets
import logging
from fastapi import FastAPI, Request, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from api.routes import shell, session, transport

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Security config
# CORS locked to known Electron origins
# Shared-secret token via .env var checked on every HTTP request
# Network exposure is ruled out by binding to 127.0.0.1
ALLOWED_ORIGINS = [
    # electron-vite dev server default
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    # packaged app loading index.html directly
    "file://",
]

API_TOKEN: str = os.environ.get("AUDIOMIX_API_TOKEN") or ""

if not API_TOKEN:
    # Fail loudly at startup, must have auth to run
    raise RuntimeError(
        "AUDIOMIX_API_TOKEN is not set. Copy .env.example to .env and "
        "generate a token before starting the server:\n"
        " python -c \"import secrets; print(secrets.token_hex(32))\""
    )

app = FastAPI(
    title="AudioMIX Bridge",
    description="Local FastAPI bridge between the AudioMIX core engine and the Electron UI.",
    version="0.1.0",
    docs_url="/docs" if os.environ.get("AUDIOMIX_ENV") == "dev" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

async def verify_token(x_audiomix_token: str = Header(default=None)) -> None:
    """
    Per-route auth dependency.
    Attach with Depends(verify_token) on any router that should
    require the shared token.
    Routes that don't declare this dependency are public by default
    (e.g., /healt).
    No exemption list to maintain as routes are added.
    """
    if not x_audiomix_token or not secrets.compare_digest(x_audiomix_token, API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid or missing token")

app.include_router(shell.router, dependencies=[Depends(verify_token)])
app.include_router(session.router, dependencies=[Depends(verify_token)])
app.include_router(transport.router, dependencies=[Depends(verify_token)])

@app.get("/health")
async def health():
    """
    Liveness check, no auth required.
    Electron polls on startup.
    """
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="127.0.0.1",    # localhost only
        port=int(os.environ.get("AUDIOMIX_API_PORT", 8000)),
        reload=os.environ.get("AUDIOMIX_ENV") == "dev",
    )
