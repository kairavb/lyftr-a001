# --------------------------------------------------
# storage.py
# --------------------------------------------------
# This file provides the Storage class which encapsulates
# all SQLite database interactions used by the FastAPI app.
#
# Responsibilities:
#   ✔ Initialize SQLite DB with WAL mode
#   ✔ Insert webhook messages (idempotent via UNIQUE message_id)
#   ✔ List messages with:
#       - Pagination (limit + offset)
#       - Filtering by sender (from_msisdn)
#       - Filtering by timestamp (since)
#       - Full text search via q (Python-side)
#       - Deterministic ordering: ts ASC, message_id ASC
#   ✔ Compute stats for /stats endpoint
#
# --------------------------------------------------

import aiosqlite
from typing import Optional, Tuple, List, Dict, Any


class Storage:
    """
    A thin abstraction over SQLite providing:
      - insert_message()
      - list_messages()
      - stats()
    """

    def __init__(self, db_path: str):
        """
        db_path should be a filesystem path (e.g. /data/app.db).
        If your DATABASE_URL includes sqlite:/// prefix,
        caller strips it before constructing Storage.
        """
        self.db_path = db_path

    # --------------------------------------------------
    # DB Initialization
    # --------------------------------------------------
    async def init(self):
        """
        Enable SQLite WAL mode for better concurrency.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.commit()

    # --------------------------------------------------
    # Insert Message with Idempotency (via UNIQUE message_id)
    # --------------------------------------------------
    async def insert_message(
        self,
        message_id: str,
        from_msisdn: str,
        to_msisdn: str,
        ts: str,
        text: Optional[str],
        created_at: str,
    ) -> str:
        """
        Insert a message. If the message_id already exists,
        return "duplicate" (idempotent behavior).
        """
        query = """
        INSERT INTO messages (
            message_id,
            from_msisdn,
            to_msisdn,
            ts,
            text,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """

        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    query,
                    (message_id, from_msisdn, to_msisdn, ts, text, created_at),
                )
                await db.commit()
            return "created"
        except aiosqlite.IntegrityError:
            return "duplicate"

    # --------------------------------------------------
    # Listing Messages with Filtering + Pagination
    # --------------------------------------------------
    async def list_messages(
        self,
        limit: int,
        offset: int,
        from_filter: Optional[str],
        since: Optional[str],
        q: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Retrieve messages with filters:
          - from_filter → exact match on from_msisdn
          - since       → ts >= since
          - q           → substring search (Python-side)
          - Ordered     → ts ASC, message_id ASC
          - Pagination  → limit & offset applied after filtering
        """

        where = []
        params: list[Any] = []

        # SQL filters (from + since)
        if from_filter:
            where.append("from_msisdn = ?")
            params.append(from_filter)

        if since:
            where.append("ts >= ?")
            params.append(since)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        # Base SELECT without q filtering
        base_select = f"""
        SELECT
            message_id,
            from_msisdn AS 'from',
            to_msisdn   AS 'to',
            ts,
            text
        FROM messages
        {where_sql}
        ORDER BY ts ASC, message_id ASC
        """

        # Fetch rows matching SQL-side filters
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(base_select, params)
            rows = [dict(r) for r in await cur.fetchall()]

        # Python-side full text search (q filter)
        if q:
            q_lower = q.lower()
            rows = [
                r for r in rows
                if q_lower in (r.get("text") or "").lower()
            ]

        total = len(rows)

        # Apply pagination last
        data = rows[offset: offset + limit]

        return data, total

    # --------------------------------------------------
    # Stats Aggregation
    # --------------------------------------------------
    async def stats(self):
        """
        Compute analytics required for /stats endpoint:
          - total_messages
          - senders_count
          - top 10 senders with counts
          - first_message_ts
          - last_message_ts
        """
        async with aiosqlite.connect(self.db_path) as db:
            # total count
            cur = await db.execute("SELECT COUNT(*) FROM messages")
            total = (await cur.fetchone())[0]

            # distinct senders
            cur = await db.execute("SELECT COUNT(DISTINCT from_msisdn) FROM messages")
            senders = (await cur.fetchone())[0]

            # top senders
            cur = await db.execute("""
                SELECT from_msisdn, COUNT(*) AS c
                FROM messages
                GROUP BY from_msisdn
                ORDER BY c DESC
                LIMIT 10
            """)
            rows = await cur.fetchall()
            messages_per_sender = [
                {"from": r[0], "count": r[1]} for r in rows
            ]

            # first + last timestamps
            cur = await db.execute("SELECT MIN(ts), MAX(ts) FROM messages")
            mnmx = await cur.fetchone()
            first_ts = mnmx[0]
            last_ts = mnmx[1]

        return {
            "total_messages": total,
            "senders_count": senders,
            "messages_per_sender": messages_per_sender,
            "first_message_ts": first_ts,
            "last_message_ts": last_ts,
        }
