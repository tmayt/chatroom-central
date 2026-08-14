# Chatroom Central

A centralized chat hub that collects messages from external systems via webhooks, lets admins view and reply from a modern SPA, and delivers outbound replies asynchronously via Celery.

**Languages:** [English](README.md) · [فارسی](README.fa.md)  
**API reference:** [English](docs/API.md) · [فارسی](docs/API.fa.md)

---

## Features

- **Inbound webhooks** — receive messages from Telegram, custom bots, or any HTTP source
- **Admin SPA** — dark-themed React UI with conversation list, search, and reply composer
- **Realtime updates** — WebSocket (Django Channels + ASGI) pushes new messages instantly
- **Async delivery** — Celery worker sends replies to external endpoints with retries
- **Token authentication** — DRF TokenAuth for API and WebSocket
- **OpenAPI docs** — Swagger UI and ReDoc via drf-spectacular
- **Docker Compose** — full stack: Django (ASGI), Celery, Redis, Postgres, frontend, nginx

---

## Architecture

```
External systems ──POST webhook──► Django API
                                      │
                                      ├──► PostgreSQL
                                      ├──► Celery ──POST──► External endpoints
                                      └──► Redis Channel Layer ──WebSocket──► Admin SPA
```

| Component | Technology |
|-----------|------------|
| Backend | Django 4.2 + DRF + Daphne (ASGI) |
| Realtime | Django Channels + Redis |
| Tasks | Celery 5 + Redis broker |
| Database | PostgreSQL (Docker) / SQLite (local) |
| Frontend | React 18 + Vite + Bootstrap 5 |
| Proxy | nginx |

---

## Quick start (Docker Compose)

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — set DJANGO_SECRET_KEY and other secrets
```

### 2. Build and start

```bash
docker compose build
docker compose up -d
```

### 3. Initialize database

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

### 4. Open the app

- **Admin SPA:** http://localhost:8000
- **Django admin:** http://localhost:8000/admin/
- **Swagger UI:** http://localhost:8000/api/schema/swagger-ui/
- **ReDoc:** http://localhost:8000/api/schema/redoc/

### 5. Generate sample data (optional)

```bash
docker compose exec web python manage.py generate_sample_data --count 10
```

---

## Quick start (local virtualenv)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start Redis (required for Channels + Celery)
# e.g. docker run -d -p 6379:6379 redis:7

python manage.py migrate
python manage.py createsuperuser

# Terminal 1 — ASGI server
daphne -b 0.0.0.0 -p 8000 project.asgi:application

# Terminal 2 — Celery worker
celery -A project worker -l info

# Terminal 3 — Frontend dev server
cd frontend && npm install && npm run dev
```

Frontend dev server runs at http://localhost:3000 and proxies `/api` and `/ws` to Django.

---

## Authentication

### Obtain a token

```bash
curl -X POST http://localhost:8000/api/v1/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

Response:

```json
{"token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"}
```

Use the token in all protected requests:

```
Authorization: Token <your-token>
```

For WebSocket, pass the token as a query parameter:

```
ws://localhost:8000/ws/admin/?token=<your-token>
```

> The user must have `is_staff=True` (superuser or staff account).

---

## WebSocket events

Connect to `/ws/admin/?token=<token>` after login. The server sends JSON events:

| Event | Description |
|-------|-------------|
| `connected` | Connection established |
| `message.new` | New inbound or outbound message |
| `message.updated` | Message status or seen flag changed |
| `conversation.updated` | Conversation metadata changed |
| `pong` | Response to client `ping` |

Example `message.new` payload:

```json
{
  "type": "message.new",
  "conversation_id": "uuid",
  "message": { "id": "...", "content": "...", "direction": "IN", ... },
  "conversation": { "id": "...", "last_message": "...", "has_unseen": true, ... }
}
```

The SPA uses WebSocket for realtime updates and falls back to HTTP polling every 60 seconds if disconnected.

---

## Webhook integration (quick example)

### 1. Create a Source in Django admin

- **Slug:** `my-bot`
- **Inbound secret:** `my-secret-key` (optional)
- **Outbound endpoint:** URL where replies are POSTed

### 2. Send an inbound message

```bash
curl -X POST http://localhost:8000/api/webhooks/my-bot/incoming/ \
  -H "Content-Type: application/json" \
  -H "X-Signature: my-secret-key" \
  -d '{
    "external_user_id": "user-123",
    "external_message_id": "msg-001",
    "content": "Hello from external system!",
    "thread_id": "thread-abc"
  }'
```

### 3. Reply from the admin SPA or API

```bash
curl -X POST http://localhost:8000/api/v1/conversations/<conversation-uuid>/reply/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"text": "Thanks for your message!"}'
```

See [docs/API.md](docs/API.md) for the complete endpoint reference.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | `dev-secret` | Django secret key |
| `DJANGO_DEBUG` | `False` | Enable debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hosts |
| `DJANGO_DB_ENGINE` | sqlite | Database engine |
| `DJANGO_DB_NAME` | `db.sqlite3` | Database name |
| `DJANGO_DB_USER` | — | Database user |
| `DJANGO_DB_PASSWORD` | — | Database password |
| `DJANGO_DB_HOST` | — | Database host |
| `DJANGO_DB_PORT` | — | Database port |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker |
| `CHANNEL_LAYERS_REDIS` | same as Celery | Redis for Channels |
| `NGX_EXTERNAL_PORT` | `8000` | Host port for nginx |

---

## Frontend UX improvements

- **Scroll preservation** — reading older messages no longer jumps to top on refresh
- **Smart auto-scroll** — only scrolls to bottom when new messages arrive and you are already at the bottom
- **Batch mark-seen** — single API call instead of one per message
- **Search** — filter conversations by contact, source, or last message
- **Connection badge** — shows Live / Connecting / Offline WebSocket status
- **Message status** — outbound messages show Sending / Sent / Failed
- **Logout button** — properly wired in the header

---

## Development

### Run tests

```bash
pytest
# or inside Docker:
docker compose exec web pytest -q
```

### Rebuild frontend after changes

```bash
docker compose build frontend
docker compose up -d frontend nginx
```

### Custom management commands

```bash
# Add admin user as participant to all conversations
docker compose exec web python manage.py add_admin_participant

# Generate sample conversations
docker compose exec web python manage.py generate_sample_data --count 20
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| WebSocket shows "Offline" | Ensure Redis is running and `CHANNEL_LAYERS_REDIS` is set |
| 401 on API calls | User must be staff; check token is valid |
| Frontend changes not visible | Rebuild frontend Docker image |
| Celery tasks not running | Check worker logs: `docker compose logs worker` |
| Scroll jumps on refresh | Update to latest frontend (WebSocket + merge logic) |

---

## Project structure

```
chatroom-central/
├── chatcore/           # Django app (models, views, consumers, tasks)
├── project/            # Django project (settings, asgi, celery)
├── frontend/           # React SPA (Vite)
├── nginx/              # Reverse proxy config
├── docs/               # API documentation (EN + FA)
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## License

MIT — use freely for prototyping and experimentation.
