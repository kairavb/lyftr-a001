# --------------------------------------------------
# main.py
# --------------------------------------------------
# This file implements the complete FastAPI backend service:
#
# ✔ Secure webhook ingestion with HMAC-SHA256 validation
# ✔ Idempotent message persistence into SQLite
# ✔ /messages pagination, search, and filtering
# ✔ /stats analytical endpoint
# ✔ /metrics Prometheus monitoring
# ✔ Liveness and readiness probes
# ✔ Structured JSON logs for each request
#
# Notes:
#   - NO external DB or cache: SQLite only
#   - DB file location controlled via DATABASE_URL env
#   - WEBHOOK_SECRET required for HMAC signature validation
#   - All logic is async, and uses aiosqlite for DB operations
# --------------------------------------------------

import os
import time
import json
import hmac
import hashlib

from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional

import logging
import aiosqlite

from fastapi import FastAPI, Request, Header, HTTPException, Query
from fastapi.responses import JSONResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .models import init_db
from .schemas import WebhookMessage
from .storage import Storage
from .logging_utils import setup_logging
from .metrics import metrics


# --------------------------------------------------
# Logging Setup
# --------------------------------------------------

setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


# --------------------------------------------------
# FastAPI Initialization + DB Path Resolution
# --------------------------------------------------

app = FastAPI()

# Normalize sqlite URL (sqlite:////path/to/file)
db_url = settings.DATABASE_URL
db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else db_url
DB = Storage(db_path)


# --------------------------------------------------
# Startup: ensure DB + secret
# --------------------------------------------------

@app.on_event("startup")
async def startup():
    """
    Service must fail startup if WEBHOOK_SECRET is not provided.
    DB schema initialization is done here once.
    """
    if not settings.WEBHOOK_SECRET:
        logger.error({"msg": "WEBHOOK_SECRET not set"})
        raise RuntimeError("WEBHOOK_SECRET not set")

    await init_db(DB.db_path)
    await DB.init()

    logger.info({"msg": "startup complete"})


# --------------------------------------------------
# Request Logging Middleware (JSON structured)
# --------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Wraps every HTTP request to:
      - Generate a unique request_id
      - Measure latency
      - Emit structured JSON logs
      - Track basic http + webhook metrics
    """

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        request_id = str(uuid4())
        method = request.method
        path = request.url.path

        try:
            body = await request.body()
        except Exception:
            body = b""

        status = 500
        response = None

        try:
            response = await call_next(request)
            status = response.status_code
            return response

        finally:
            latency_ms = (time.time() - start) * 1000.0

            # Metrics
            metrics.observe_latency(latency_ms)
            metrics.inc_http(path, status)

            # Base log shape
            log_record = {
                "request_id": request_id,
                "method": method,
                "path": path,
                "status": status,
                "latency_ms": latency_ms,
            }

            # Extract message_id on webhook
            try:
                if body:
                    j = json.loads(body.decode("utf-8"))
                    if isinstance(j, dict) and j.get("message_id"):
                        log_record["message_id"] = j["message_id"]
            except Exception:
                pass

            logger.info(log_record)


app.add_middleware(RequestLoggingMiddleware)


# --------------------------------------------------
# POST /webhook
# --------------------------------------------------

@app.post("/webhook")
async def webhook(request: Request, x_signature: str = Header(None)):
    """
    Ingest inbound WhatsApp-like messages.
    Validates:
      - HMAC signature
      - JSON schema (via Pydantic)
    Persists:
      - idempotent rows in SQLite
    """

    raw = await request.body()

    # Signature required
    if not x_signature:
        metrics.inc_webhook("invalid_signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    # Compute HMAC
    expected_sig = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        raw,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, x_signature):
        metrics.inc_webhook("invalid_signature")
        raise HTTPException(status_code=401, detail="invalid signature")

    # Validate inbound JSON payload
    try:
        msg = WebhookMessage.parse_raw(raw)
    except Exception as e:
        metrics.inc_webhook("validation_error")
        raise HTTPException(status_code=422, detail=str(e))

    # Insert + idempotency behavior
    created_at = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    result = await DB.insert_message(
        msg.message_id,
        msg.from_,
        msg.to,
        msg.ts.isoformat().replace("+00:00", "Z"),
        msg.text,
        created_at
    )

    metrics.inc_webhook(result)

    logger.info({
        "msg": "webhook_processed",
        "message_id": msg.message_id,
        "dup": result == "duplicate",
        "result": result
    })

    return JSONResponse({"status": "ok"})


# --------------------------------------------------
# GET /messages
# --------------------------------------------------

@app.get("/messages")
async def get_messages(
    limit: int = 50,
    offset: int = 0,
    from_: Optional[str] = Query(None, alias="from"),
    since: str = None,
    q: str = None,
):
    """
    Returns paginated + filterable message history.
    Supports:
      - limit/offset
      - filter by from=
      - filter by since=
      - text search via q=
    """

    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit out of range")

    if offset < 0:
        raise HTTPException(status_code=422, detail="offset out of range")

    data, total = await DB.list_messages(limit, offset, from_, since, q)

    return {
        "data": data,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# --------------------------------------------------
# GET /stats
# --------------------------------------------------

@app.get("/stats")
async def stats():
    """Aggregate analytics derived from stored messages."""
    return await DB.stats()


# --------------------------------------------------
# Health Checks
# --------------------------------------------------

@app.get("/health/live")
async def live():
    """Always OK once service is running."""
    return PlainTextResponse("OK", status_code=200)


@app.get("/health/ready")
async def ready():
    """
    Ready when:
      - DB is reachable
      - WEBHOOK_SECRET is configured
    """
    if not settings.WEBHOOK_SECRET:
        return PlainTextResponse("SERVICE UNAVAILABLE", status_code=503)

    try:
        async with aiosqlite.connect(DB.db_path) as db:
            await db.execute("SELECT 1")
        return PlainTextResponse("OK", status_code=200)
    except Exception:
        return PlainTextResponse("SERVICE UNAVAILABLE", status_code=503)


# --------------------------------------------------
# Metrics
# --------------------------------------------------

@app.get("/metrics")
async def get_metrics():
    """Prometheus exposition format output."""
    return PlainTextResponse(
        metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4"
    )


# --------------------------------------------------
# Default Home
# --------------------------------------------------

@app.get("/")
def home():
    return PlainTextResponse("API is Running", status_code=200)
