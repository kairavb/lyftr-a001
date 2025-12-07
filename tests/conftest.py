# --------------------------------------------------
# conftest.py (Test bootstrap)
# --------------------------------------------------
# This file ensures correct environment setup before
# importing the FastAPI app inside test modules.
#
# Responsibilities:
#   - Ensure WEBHOOK_SECRET is always set for tests
#   - Ensure DATABASE_URL points to a temporary SQLite file
#   - Prevent import-time failures due to missing env config
#
# Note:
#   Tests will import app.main only after these env vars
#   are applied, ensuring predictable behavior.
# --------------------------------------------------

import os
import pytest

# --------------------------------------------------
# Test Environment Defaults
# --------------------------------------------------
# Ensure a valid webhook secret for HMAC-based tests
os.environ.setdefault("WEBHOOK_SECRET", "testsecret")

# Point the DB to an isolated temp SQLite file
# (kept simple for test cleanup and determinism)
os.environ.setdefault("DATABASE_URL", "sqlite:////tmp/test_app.db")
