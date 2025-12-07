# --------------------------------------------------
# test_stats.py
# --------------------------------------------------
# Purpose:
#   Validate the /stats endpoint behavior.
#
# Expectations:
#   - Endpoint returns 200 OK
#   - Response JSON includes:
#       • total_messages
#       • senders_count
#
# Notes:
#   - This test does not assert the numerical correctness
#     (that is covered indirectly by webhook tests)
#   - Only verifies schema & availability
# --------------------------------------------------

from fastapi.testclient import TestClient
from app.main import app

# In-process FastAPI client
client = TestClient(app)


def test_stats():
    """
    Ensure /stats endpoint is reachable and exposes expected fields.
    """
    response = client.get("/stats")
    assert response.status_code == 200

    data = response.json()
    assert "total_messages" in data
    assert "senders_count" in data
