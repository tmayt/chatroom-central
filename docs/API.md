# API Reference — Chatroom Central

Base URL: `http://localhost:8000` (or your deployed domain)

All authenticated endpoints require:

```
Authorization: Token <your-admin-token>
```

The user associated with the token must have `is_staff=True`.

---

## Table of contents

1. [Authentication](#authentication)
2. [Conversations API](#conversations-api)
3. [Messages API](#messages-api)
4. [Webhooks (inbound)](#webhooks-inbound)
5. [Mock provider](#mock-provider)
6. [WebSocket](#websocket)
7. [Data models](#data-models)
8. [Error responses](#error-responses)

---

## Authentication

### Obtain token

```
POST /api/v1/auth/token/
```

**Request body:**

```json
{
  "username": "admin",
  "password": "your-password"
}
```

**Success (200):**

```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

**Errors:**

| Status | Reason |
|--------|--------|
| 400 | Missing username or password |
| 401 | Invalid credentials |

---

## Conversations API

### List conversations

```
GET /api/v1/conversations/
```

**Query parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `mine` | `1` / `true` | Only conversations where the authenticated user is a participant |

**Success (200):**

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "source": "telegram-bot",
    "external_contact": "user-12345",
    "last_message": "Hello, I need help",
    "updated_at": "2026-08-14T12:30:00Z",
    "has_unseen": true
  }
]
```

Returns up to 100 conversations, ordered by latest message time (newest first).

---

### Get conversation detail

```
GET /api/v1/conversations/<uuid>/
```

**Success (200):**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "uuid-of-source",
  "external_contact": "uuid-of-contact",
  "title": null,
  "metadata": {},
  "is_closed": false,
  "created_at": "2026-08-01T10:00:00Z",
  "updated_at": "2026-08-14T12:30:00Z",
  "messages": [
    {
      "id": "msg-uuid",
      "conversation": "conv-uuid",
      "direction": "IN",
      "sender_name": "John",
      "content": "Hello!",
      "status": "RECEIVED",
      "seen": false,
      "created_at": "2026-08-14T12:00:00Z",
      "updated_at": "2026-08-14T12:00:00Z"
    }
  ]
}
```

Messages are ordered chronologically (`created_at` ascending).

---

### Send reply

```
POST /api/v1/conversations/<uuid>/reply/
```

**Request body:**

```json
{
  "text": "Thanks for reaching out! We'll help you shortly."
}
```

**Success (200):**

```json
{
  "id": "new-message-uuid",
  "status": "PENDING",
  "message": {
    "id": "new-message-uuid",
    "direction": "OUT",
    "content": "Thanks for reaching out!",
    "status": "PENDING",
    ...
  }
}
```

The message is enqueued for delivery via Celery. Status changes to `SENT` or `FAILED` asynchronously. A `message.new` WebSocket event is broadcast immediately.

**Errors:**

| Status | Reason |
|--------|--------|
| 400 | Missing `text` field |
| 401 | Not authenticated |
| 403 | User is not staff |
| 404 | Conversation not found |

---

### Mark all messages as seen

```
POST /api/v1/conversations/<uuid>/seen/
```

Marks all inbound (`direction=IN`) unseen messages in the conversation as seen.

**Success (200):**

```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "marked_seen": 3
}
```

---

## Messages API

### Mark single message as seen

```
POST /api/v1/messages/<uuid>/seen/
```

**Success (200):**

```json
{
  "id": "message-uuid",
  "seen": true
}
```

---

## Webhooks (inbound)

External systems POST messages to this endpoint. No token auth — uses optional signature header instead.

### Receive inbound message

```
POST /api/webhooks/<source_slug>/incoming/
```

**Headers:**

| Header | Required | Description |
|--------|----------|-------------|
| `Content-Type` | Yes | `application/json` |
| `X-Signature` | If source has secret | Must match the source's `inbound_secret` |

**Request body:**

```json
{
  "external_user_id": "user-12345",
  "external_message_id": "ext-msg-001",
  "content": "Hello from Telegram!",
  "thread_id": "optional-thread-id",
  "timestamp": "2026-08-14T12:00:00Z"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `external_user_id` | **Yes** | Unique user ID in the external system |
| `external_message_id` | No | Idempotency key — duplicate IDs are ignored |
| `content` | No | Message text |
| `thread_id` | No | Groups messages into a conversation |
| `timestamp` | No | Original message timestamp (stored in metadata) |

**Success (200):**

```json
{
  "status": "ok",
  "message_id": "new-internal-uuid"
}
```

**Duplicate (200):**

```json
{
  "status": "duplicate"
}
```

**Errors:**

| Status | Reason |
|--------|--------|
| 400 | Invalid payload |
| 401 | Invalid `X-Signature` |
| 404 | Source slug not found or inactive |

### Setting up a Source

1. Go to Django admin → **Sources** → Add
2. Set **Slug** (used in URL), **Display name**, optional **Inbound secret**
3. Set **Outbound endpoint template** — URL where admin replies are POSTed

### Outbound delivery payload

When an admin sends a reply, Celery POSTs to the source's outbound endpoint:

```json
{
  "conversation_id": "internal-conversation-uuid",
  "external_user_id": "user-12345",
  "content": "Admin reply text",
  "message_id": "internal-message-uuid"
}
```

---

## Mock provider

For local testing, point a Source's outbound endpoint to:

```
http://web:8000/api/mock/provider/receive/
```

```
POST /api/mock/provider/receive/
```

Accepts any JSON body and logs it to stdout. No authentication required.

---

## WebSocket

### Connect

```
ws://localhost:8000/ws/admin/?token=<admin-token>
```

Or via WSS in production:

```
wss://yourdomain.com/ws/admin/?token=<admin-token>
```

### Client → Server

**Ping (keepalive):**

```json
{"type": "ping"}
```

**Server response:**

```json
{"type": "pong"}
```

### Server → Client events

#### `connected`

Sent immediately after successful authentication.

```json
{"type": "connected"}
```

#### `message.new`

New message created (inbound webhook or admin reply).

```json
{
  "type": "message.new",
  "conversation_id": "uuid",
  "message": {
    "id": "uuid",
    "direction": "IN",
    "content": "Hello",
    "status": "RECEIVED",
    "seen": false,
    "created_at": "2026-08-14T12:00:00Z",
    ...
  },
  "conversation": {
    "id": "uuid",
    "source": "my-bot",
    "external_contact": "user-123",
    "last_message": "Hello",
    "updated_at": "2026-08-14T12:00:00Z",
    "has_unseen": true
  }
}
```

#### `message.updated`

Message status or seen flag changed (e.g. after Celery delivery).

```json
{
  "type": "message.updated",
  "conversation_id": "uuid",
  "message": {
    "id": "uuid",
    "status": "SENT",
    ...
  }
}
```

#### `conversation.updated`

Conversation metadata changed (e.g. bulk mark-seen).

```json
{
  "type": "conversation.updated",
  "conversation_id": "uuid"
}
```

### Connection errors

| Close code | Reason |
|------------|--------|
| 4001 | Invalid or missing token, or user is not staff |

---

## Data models

### Message directions

| Value | Meaning |
|-------|---------|
| `IN` | Inbound (from external system) |
| `OUT` | Outbound (admin reply) |

### Message statuses

| Value | Meaning |
|-------|---------|
| `RECEIVED` | Inbound message stored |
| `PENDING` | Outbound message queued for delivery |
| `SENT` | Successfully delivered to external endpoint |
| `FAILED` | Delivery failed after retries |

---

## Error responses

DRF returns errors in this format:

```json
{
  "detail": "Error description"
}
```

Or for validation errors:

```json
{
  "field_name": ["Error message"]
}
```

Common HTTP status codes:

| Code | Meaning |
|------|---------|
| 400 | Bad request / validation error |
| 401 | Authentication required or invalid |
| 403 | Permission denied (not staff) |
| 404 | Resource not found |
| 500 | Server error |

---

## OpenAPI / Interactive docs

When the server is running:

- **OpenAPI JSON:** `/api/schema/`
- **Swagger UI:** `/api/schema/swagger-ui/`
- **ReDoc:** `/api/schema/redoc/`

---

## Example: full integration flow

```bash
# 1. Get admin token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"pass"}' | jq -r .token)

# 2. Simulate inbound webhook
curl -X POST http://localhost:8000/api/webhooks/my-bot/incoming/ \
  -H "Content-Type: application/json" \
  -H "X-Signature: my-secret" \
  -d '{"external_user_id":"u1","content":"Hi there","thread_id":"t1"}'

# 3. List conversations
curl -H "Authorization: Token $TOKEN" \
  http://localhost:8000/api/v1/conversations/

# 4. Reply (replace CONV_ID)
curl -X POST http://localhost:8000/api/v1/conversations/CONV_ID/reply/ \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello! How can I help?"}'

# 5. Connect WebSocket (use wscat or browser)
wscat -c "ws://localhost:8000/ws/admin/?token=$TOKEN"
```
