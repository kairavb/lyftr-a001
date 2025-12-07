# 📡 Lyftr.ai Backend Assignment — FastAPI + SQLite + Docker

build by Kairav

A production-style backend implementing Lyftr’s technical assignment with:

- Secure HMAC webhook ingestion
- Idempotent message storage (exactly-once)
- SQLite persistence with Docker volume
- Pagination, filtering & free-text search
- Prometheus operational metrics
- Health/liveness probes
- Structured JSON logs per request
- Environment-based configuration
- Automated tests with pytest

---

## 🏗 Architecture Overview

**Purpose**: A WhatsApp-like ingestion API where every inbound message:

1. Is verified using HMAC-SHA256 (shared secret)
2. Is inserted into SQLite exactly once
3. Can be listed using pagination, filtering & search
4. Contributes to analytics (/stats)
5. Exposes metrics and JSON logs for observability

---

## 📁 Project Structure

```
app/
 ├── main.py              # FastAPI routes, middleware, health, metrics
 ├── config.py            # env config
 ├── models.py            # SQLite schema bootstrap
 ├── storage.py           # DB operations + idempotency logic
 ├── schemas.py           # Pydantic validation
 ├── logging_utils.py     # structured JSON logging
 ├── metrics.py           # counters, latency buckets

tests/
 ├── test_webhook.py
 ├── test_messages.py
 ├── test_stats.py

Dockerfile
docker-compose.yml
Makefile
README.md
```

---

# ⚙️ Environment Variables

| Variable         | Required | Description                            |
| ---------------- | -------- | -------------------------------------- |
| `WEBHOOK_SECRET` | YES      | HMAC secret for signature validation   |
| `DATABASE_URL`   | YES      | Must be like: `sqlite:////data/app.db` |
| `LOG_LEVEL`      | NO       | Default: `INFO`                        |

Example export:

```bash
export WEBHOOK_SECRET="testsecret"
export DATABASE_URL="sqlite:////data/app.db"
```

---

# 🐳 Run Instructions

### Start API (recommended)

```bash
make up
```

(Internally: `docker compose up -d --build`)

### Stop + delete state

```bash
make down
```

### Follow API logs

```bash
make logs
```

### Run automated tests

```bash
make test
```

The API runs at:

```
http://localhost:8000
```

---

# 🔐 Webhook Signature (HMAC-SHA256)

Every inbound webhook request MUST include:

```
X-Signature: <hex-HMAC>
```

Where:

```
HMAC = SHA256(secret=WEBHOOK_SECRET, message=<raw body bytes>)
```

### Example

```bash
BODY='{"message_id":"m1","from":"+919876543210","to":"+14155550100","ts":"2025-01-15T10:00:00Z","text":"Hello"}'

SIG=$(printf '%s' "$BODY" \
  | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" -binary \
  | xxd -p -c 256)

curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "X-Signature: $SIG" \
  -d "$BODY"
```

Success response:

```json
{ "status": "ok" }
```

### Behavior

- Missing / invalid signature → HTTP **401**
- Pydantic validation error → **422**
- First valid insert → stored
- Duplicate insert (same message_id) → ignored, still **200**

---

# 📬 Endpoints

## 1️⃣ POST `/webhook`

Validates signature, validates payload, inserts exactly once.

Payload:

```json
{
  "message_id": "m99",
  "from": "+919876543210",
  "to": "+14155550100",
  "ts": "2025-01-15T10:00:00Z",
  "text": "Hello"
}
```

---

## 2️⃣ GET `/messages`

Query params:

| Param    | Meaning                             |
| -------- | ----------------------------------- |
| `limit`  | Page size (1–100), default 50       |
| `offset` | Pagination offset                   |
| `from`   | Filter by sender                    |
| `since`  | Filter by timestamp                 |
| `q`      | Substring search (case-insensitive) |

Deterministic sorting:

```
ORDER BY ts ASC, message_id ASC
```

### Example

```bash
curl "http://localhost:8000/messages?from=+919876543210&limit=2"
```

Response:

```json
{
  "data": [...],
  "total": 4,
  "limit": 2,
  "offset": 0
}
```

**`total` always reflects total matching rows (not page size)**

---

## 3️⃣ GET `/stats`

Provides message-level analytics:

```json
{
  "total_messages": 25,
  "senders_count": 4,
  "messages_per_sender": [
    { "from": "+919876543210", "count": 10 },
    { "from": "+911234567890", "count": 6 }
  ],
  "first_message_ts": "2025-01-10T09:00:00Z",
  "last_message_ts": "2025-01-15T10:00:00Z"
}
```

---

## 4️⃣ Health

### `/health/live`

Always returns `200` after startup.

### `/health/ready`

Returns `200` only if:

- Database reachable
- `WEBHOOK_SECRET` is set

Else: `503`

---

## 5️⃣ GET `/metrics` (Prometheus)

Outputs operational metrics such as:

```
http_requests_total{path="/webhook",status="200"} 15
http_requests_total{path="/messages",status="200"} 42
webhook_requests_total{result="created"} 10
webhook_requests_total{result="duplicate"} 5
```

Also tracks request latency buckets.

---

# 🧾 Structured JSON Logs

Every request emits **one JSON log line** with fields:

- ts (ISO-8601)
- level
- method
- path
- status
- latency_ms
- request_id

Extra fields for `/webhook`:

- message_id
- dup (boolean)
- result: `created`, `duplicate`, `invalid_signature`, `validation_error`

Inspect with:

```bash
docker compose logs api | jq .
```

---

# 🧠 Design Decisions

### HMAC Signature

- Computed from raw body
- Compared using `hmac.compare_digest` (timing safe)
- Invalid signature → 401 with no DB writes

### Idempotency

- SQLite enforces `PRIMARY KEY(message_id)`
- First valid insert creates record
- Subsequent valid duplicates return OK without re-insert

### Pagination & Filters

- `limit`, `offset`
- Filter by `from`, `since`, and substring search `q`
- `total` computed **after filters**
- Deterministic ordering ensures stable pagination

### Stats

- Efficient SQL aggregation for:
  - total messages
  - distinct senders
  - messages per sender (top 10)
  - first & last timestamps

### Metrics

- HTTP counters by path + status
- Webhook outcome counters
- Latency histogram buckets

---

# 🧰 Development Setup Used

**VSCode + GitHub Copilot + occasional ChatGPT help**

No services beyond SQLite + Docker volume.

---
