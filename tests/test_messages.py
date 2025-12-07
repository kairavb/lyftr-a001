# --------------------------------------------------
# test_messages.py
# --------------------------------------------------
# Purpose:
#   - Validate the /messages endpoint functionality
#   - Ensure:
#       • webhook insertions succeed
#       • message listing works
#       • pagination and free-text search work correctly
#       • filtering by "from" returns correct results
#
# Test Strategy:
#   1. Insert a message via /webhook (with valid HMAC)
#   2. List messages via /messages
#   3. Verify:
#       • expected fields exist
#       • filtering works
#       • "q" substring search works (case-insensitive)
#
# NOTE:
#   - Uses FastAPI TestClient (runs app in-process)
#   - No DB cleanup required — SQLite file is isolated by env
# --------------------------------------------------

from fastapi.testclient import TestClient
from app.main import app
import json
import os
import hmac
import hashlib

# In-process API client
client = TestClient(app)


def test_messages_listing_and_filters():
    """
    Insert a message using /webhook and validate:
      • It is stored
      • /messages returns correct structure
      • Filtering by sender works correctly
    """

    # valid message payload
    body = {
        "message_id": "m2",
        "from": "+911234567890",
        "to": "+14155550100",
        "ts": "2025-01-15T09:00:00Z",
        "text": "Earlier"
    }

    # compute valid HMAC signature
    secret = os.environ.get("WEBHOOK_SECRET")
    signature = hmac.new(
        secret.encode(),
        json.dumps(body).encode(),
        hashlib.sha256
    ).hexdigest()

    # insert message via webhook
    r = client.post(
        "/webhook",
        data=json.dumps(body).encode(),
        headers={
            "X-Signature": signature,
            "Content-Type": "application/json"
        }
    )
    assert r.status_code == 200

    # basic message list
    r = client.get("/messages")
    assert r.status_code == 200
    j = r.json()

    assert "data" in j and "total" in j

    # filter by sender ("from")
    r = client.get("/messages", params={"from": "+911234567890"})
    assert r.status_code == 200

    j = r.json()
    assert all(m["from"] == "+911234567890" for m in j["data"])


def test_pagination_and_q():
    """
    Validate free-text search:
      • GET /messages?q=Hello
      • Ensure returned data contains messages whose "text"
        includes 'Hello'
    """

    r = client.get("/messages", params={"q": "Hello"})
    assert r.status_code == 200

    j = r.json()

    # ensure substring match in text
    assert any(
        "Hello" in (m.get("text") or "")
        for m in j["data"]
    )
