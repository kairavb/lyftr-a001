# --------------------------------------------------
# schemas.py
# --------------------------------------------------
# This file defines the WebhookMessage data model,
# used for validating inbound requests in /webhook.
#
# Features:
#   ✔ Supports Pydantic v2 (preferred)
#   ✔ Falls back to Pydantic v1 if necessary
#   ✔ Fully functional even if Pydantic is not installed
#
# Validations:
#   - message_id: non-empty string
#   - from/to: E.164-like format (+ followed by digits)
#   - ts: ISO-8601 datetime
#   - text: optional, max length = 4096
#
# parse_raw() is used by webhook ingestion to validate
# inbound JSON before insertion into SQLite.
# --------------------------------------------------

import json
from datetime import datetime
from typing import Optional

try:
    # Try Pydantic v2 style imports
    from pydantic import BaseModel, Field
    from typing import Annotated

    # --------------------------------------------------
    # Typed field annotations with constraints
    # --------------------------------------------------
    E164 = Annotated[str, Field(regex=r'^\+[0-9]+$')]
    TextMax = Annotated[Optional[str], Field(max_length=4096)]
    MsgId = Annotated[str, Field(min_length=1)]

    class WebhookMessage(BaseModel):
        """
        Pydantic v2 model for validating inbound webhook payloads.
        """

        message_id: MsgId
        from_: E164 = Field(alias="from")
        to: E164
        ts: datetime
        text: TextMax = None

        # Enable alias population: incoming JSON has `from`
        model_config = {"populate_by_name": True}

# --------------------------------------------------
# If Annotated or v2 style fails, fallback to Pydantic v1
# --------------------------------------------------
except Exception:
    try:
        from pydantic import BaseModel, Field, constr

        E164 = constr(regex=r'^\+[0-9]+$')

        class WebhookMessage(BaseModel):
            """
            Pydantic v1 fallback model.
            """

            message_id: constr(min_length=1)
            from_: E164 = Field(alias="from")
            to: E164
            ts: datetime
            text: Optional[constr(max_length=4096)] = None

            class Config:
                # Allow using field names or aliases
                allow_population_by_field_name = True

    # --------------------------------------------------
    # If Pydantic not available at all, basic runtime validator
    # --------------------------------------------------
    except Exception:

        class WebhookMessage:
            """
            Manual runtime validator used only when Pydantic is missing.
            """

            def __init__(self, message_id: str, from_: str, to: str, ts: str, text: Optional[str]):
                # message_id required
                if not message_id or not isinstance(message_id, str):
                    raise ValueError("message_id required")

                # from must match E.164-like string
                if not isinstance(from_, str) or not from_.startswith('+') or not from_[1:].isdigit():
                    raise ValueError("from must be E.164-like")

                # to must match E.164-like string
                if not isinstance(to, str) or not to.startswith('+') or not to[1:].isdigit():
                    raise ValueError("to must be E.164-like")

                # ts must be ISO-8601
                try:
                    self.ts = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except Exception:
                    raise ValueError("ts must be ISO format")

                # text length capped
                if text is not None and len(text) > 4096:
                    raise ValueError("text too long")

                # Assign fields
                self.message_id = message_id
                self.from_ = from_
                self.to = to
                self.text = text

            @classmethod
            def parse_raw(cls, raw: bytes):
                """
                Minimal replacement for BaseModel.parse_raw()
                """
                obj = json.loads(raw.decode("utf-8"))
                return cls(
                    obj.get("message_id"),
                    obj.get("from"),
                    obj.get("to"),
                    obj.get("ts"),
                    obj.get("text"),
                )
