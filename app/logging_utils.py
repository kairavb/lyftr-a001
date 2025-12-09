# --------------------------------------------------
# logging_utils.py
# --------------------------------------------------
# This file sets up application-wide structured JSON logging.
#
# Key Features:
#   - Every log entry is a valid JSON object, one line per record
#   - Includes timestamp, log level, and any additional message fields
#   - Designed for log aggregation, parsing, and observability tools
#
# Used mainly for:
#   - Request logs
#   - Webhook processing logs
#   - Error and metrics logging
#
# --------------------------------------------------

import logging
import sys
import json
from datetime import datetime


class JSONRequestFormatter(logging.Formatter):
    """
    Custom logging formatter that outputs each log record as a clean JSON line.
    If record.msg is already a dict, it embeds it directly.
    Otherwise, it wraps record.getMessage() inside a field called "msg".
    """

    def format(self, record):
        # Extract payload
        if isinstance(record.msg, dict):
            payload = record.msg
        else:
            payload = {"msg": record.getMessage()}

        # Standardized base fields
        base = {
            "ts": datetime.utcnow().isoformat() + "Z",  # UTC timestamp (ISO format)
            "level": record.levelname,
        }

        # Merge app-specific data with base metadata
        base.update(payload)

        # Return one JSON object per log line
        return json.dumps(base)


def setup_logging(level: str = "INFO"):
    """
    Configure root logger to emit JSON logs only through stdout.
    Ensures:
      - No multiple handlers
      - Unified log format
      - Log level is configurable via environment
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONRequestFormatter())

    root = logging.getLogger()
    root.handlers = []       # Remove any existing handlers to avoid duplicates
    root.addHandler(handler)
    root.setLevel(level)
