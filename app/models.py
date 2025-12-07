# --------------------------------------------------
# models.py
# --------------------------------------------------
# This module initializes SQLite schema for message
# storage used by the FastAPI backend.
#
# Table: messages
#   - message_id (PRIMARY KEY)
#   - from_msisdn
#   - to_msisdn
#   - ts (ISO-8601 timestamp)
#   - text (optional)
#   - created_at (server timestamp)
#
# Schema is created automatically at startup if missing.
# --------------------------------------------------

import aiosqlite

# --------------------------------------------------
# SQL statement for creating the messages table
# --------------------------------------------------
CREATE_MESSAGES_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    from_msisdn TEXT NOT NULL,
    to_msisdn TEXT NOT NULL,
    ts TEXT NOT NULL,
    text TEXT,
    created_at TEXT NOT NULL
);
"""

# --------------------------------------------------
# Initialize database file and ensure schema exists
# --------------------------------------------------
async def init_db(db_path: str):
    """
    Initialize SQLite database and ensure the
    required schema is created.

    Args:
        db_path (str): Filesystem path to SQLite DB
                       (e.g. "/data/app.db")

    Behavior:
        - Opens SQLite file if not present
        - Applies table creation SQL
        - Commits once
    """
    async with aiosqlite.connect(db_path) as db:
        await db.execute(CREATE_MESSAGES_SQL)
        await db.commit()
