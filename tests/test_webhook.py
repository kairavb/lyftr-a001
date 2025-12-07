# --------------------------------------------------
# test_webhook.py
# --------------------------------------------------
# Purpose:
#   Validate the webhook ingestion behavior:
#       • Reject invalid signatures
#       • Accept valid signatures
#       • Handle duplicate inserts idempotently
#
# Expectations:
#   - Invalid signature → 401
#   - Valid signature → 200
#   - Same valid payload sent twice → still 200 (no duplicates)
# --------------------------------------------------

import hmac
import hashlib
import json
import os
from fastapi.testclient import TestClient
from app.main import app

# In-process FastAPI test client
client = TestClient(app)

# Sample message payload to insert
BODY = {
    "message_id": "m1",
    "from": "+919876543210",
    "to": "+14155550100",
    "ts": "2025-01-15T10:00:00Z",
    "text": "Hello"
}


def make_sig(secret: str, body: bytes) -> str:
    """
    Helper: compute a valid HMAC-SHA256 signature over the raw body.
    """
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_invalid_signature():
    """
    A webhook with a missing or incorrect signature must return 401.
    """
    response = client.post(
        "/webhook",
        json=BODY,
        headers={"X-Signature": "bad"}  # invalid signature
    )
    assert response.status_code == 401


def test_valid_and_duplicate():
    """
    A valid webhook request must:
        • Return 200
        • Insert exactly once (idempotent)
        • A repeated delivery must also return 200 without a new insert
    """
    secret = os.environ.get("WEBHOOK_SECRET")
    body_bytes = json.dumps(BODY).encode()
    signature = make_sig(secret, body_bytes)

    # First insertion — must succeed
    first = client.post(
        "/webhook",
        data=body_bytes,
        headers={
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
    )
    assert first.status_code == 200

    # Second insertion (duplicate) — must still succeed
    # No extra DB insert expected
    second = client.post(
        "/webhook",
        data=body_bytes,
        headers={
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
    )
    assert second.status_code == 200
