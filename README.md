# Chatroom central

Minimal Django + Celery scaffold that centralizes messages from site users and external chat systems, lets admins view and reply from a single admin UI, and delivers replies back to the original sources reliably.

This README documents the project's abilities, configuration options, how to run it (local or Docker Compose), where to find API docs, and developer tips.

Table of contents
<!-- top navigation -->
**Quick links:**

- [Features & Abilities](#features--abilities)
- [Architecture & components](#architecture--components)
- [Run (quick) — venv](#quick-run-locally-using-a-virtualenv)
- [Run with Docker Compose](#run-with-docker-compose-recommended)
- [Configuration & environment variables](#configuration--environment-variables)
- [API docs (Swagger / ReDoc)](#api-documentation-swagger--redoc)
- [Authentication](#authentication)
- [Admin SPA](#admin-spa)
- [Dev & Tests](#developer-notes-build--tests)
- [Commands & Testing](#custom-django-commands--testing)
- [Troubleshooting & tips](#troubleshooting--tips)


Custom Django commands & testing
--------------------------------
This section explains how to add a custom Django management command and how to run tests locally or inside the Docker Compose environment.

1) Create a custom management command

Inside a Django app (for example `chatcore`) create the directories:

```
chatcore/management/commands/
```

Add a Python file with the command name, e.g. `chatcore/management/commands/create_sample_data.py`.

Example minimal command (paste into that file):

```python
from django.core.management.base import BaseCommand

class Command(BaseCommand):
		help = 'Create sample conversations/messages for development'

		def add_arguments(self, parser):
				parser.add_argument('--count', type=int, default=5, help='How many conversations to create')

		def handle(self, *args, **options):
				count = options['count']
				# implement creation logic here
				self.stdout.write(self.style.SUCCESS(f'Created {count} sample conversations'))
```

Once placed in the correct path, Django will auto-discover the command.

Run it locally (venv):

```bash
python manage.py create_sample_data --count 10
```

Run it inside Docker Compose:

```bash
docker compose exec web python manage.py create_sample_data --count 10
```

2) Run tests

The project includes pytest in `requirements.txt`. You can run tests either with pytest or with Django's `manage.py test`.

Locally (venv):

```bash
# install test deps
pip install -r requirements.txt

# run all tests with pytest
pytest

# or run Django test runner
python manage.py test

# run a single test module or function with pytest
pytest tests/test_some_module.py::test_function_name -q
```

With Docker Compose (inside the `web` service):

```bash
# run pytest inside the container
docker compose exec web pytest -q

# or use manage.py test
docker compose exec web python manage.py test
```

3) Helpful tips

- Use `docker compose exec web bash` to open a shell in the web container for interactive debugging.
- If tests rely on DB state, ensure migrations are applied first:

	```bash
	docker compose exec web python manage.py migrate
	```

- For fast feedback during frontend changes, run the Vite dev server locally (`cd frontend && npm run dev`) instead of rebuilding the Docker image on every change.

- If you want, I can add an example management command file to the repository (for example `create_sample_data`) and a couple of example pytest tests to demonstrate the pattern — say yes and I will create them.
Features & Abilities
--------------------
- Accept messages from site users and external chat systems (webhooks).
- Store conversations and messages in a central Postgres-backed store.
- Admin SPA to list conversations, view details, and send replies.
- Deliver admin replies back to original systems via Celery tasks (async delivery).
- Token-based authentication for the API (DRF TokenAuth). Simple admin login flow available in the SPA.
- OpenAPI schema + interactive docs (Swagger UI and ReDoc) using drf-spectacular.
- Docker Compose configuration for full-stack local development: Django web, Celery worker, Redis, Postgres, frontend assets (Vite + React), and nginx reverse proxy.

Architecture & components
-------------------------
- Backend: Django + Django REST Framework (API endpoints for conversations, messages, and webhook handling).
- Tasks: Celery worker using Redis as broker for outbound message delivery and retries.
- Database: Postgres (or sqlite for quick local testing if not configured).
- Frontend: Vite + React SPA (admin UI) compiled into static assets and served by an nginx container.
- Reverse Proxy: nginx routes `/api/` to Django and `/` to the SPA static files.

Quick: Run locally using a virtualenv
-----------------------------------
1. Create a virtualenv and install requirements:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run migrations, create a superuser and start the web server:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

3. (Optional) Start a Celery worker (requires Redis available):

```bash
celery -A project worker -l info
```

Run with Docker Compose (recommended)
------------------------------------
Use Docker Compose to bring up a fully-working environment (web, worker, redis, db, frontend, nginx):

```bash
# build all images (frontend and web will run their respective build steps)
docker compose build

# start everything in the background
docker compose up -d

# run migrations (after DB is ready)
docker compose exec web python manage.py migrate

# create a superuser interactively
docker compose exec web python manage.py createsuperuser

# follow logs (helpful to see Celery and web activity)
docker compose logs -f

# stop and remove containers
docker compose down
```

Notes
- The frontend is built in a multi-stage Dockerfile (Node build stage → static assets copied into nginx runtime). Rebuilding the frontend image is required after changing SPA source files.

Configuration & environment variables
-----------------------------------
Configuration is read from environment variables. The important ones include:

- DJANGO_SECRET_KEY: Django SECRET_KEY (default: dev-secret in settings for local dev).
- DJANGO_DB_ENGINE, DJANGO_DB_NAME, DJANGO_DB_USER, DJANGO_DB_PASSWORD, DJANGO_DB_HOST, DJANGO_DB_PORT: Database connection. By default the project uses sqlite when not configured.
- CELERY_BROKER_URL: Celery broker (default: redis://localhost:6379/0).
- FRONTEND_API_KEY: Simple dev API key for the frontend (default: dev-frontend-token). For production use proper auth.

If you run under Docker Compose the compose file contains sensible defaults for Postgres and Redis; override via an `.env` file or environment when deploying.

IMPORTANT: fill your `.env`
-------------------------
Before running the app (locally or with Docker Compose) copy the example env file and fill in real values for secrets and DB credentials. Do NOT commit your `.env` file to version control.

```bash
cp .env.example .env
# edit .env and set secure values (SECRET_KEY, DB credentials, etc.)
```


API documentation (Swagger / ReDoc)
---------------------------------
The project exposes an OpenAPI schema and interactive docs using drf-spectacular. Start the web service, then open:

- OpenAPI JSON:    http://localhost:8000/api/schema/
- Swagger UI:      http://localhost:8000/api/schema/swagger-ui/
- ReDoc UI:        http://localhost:8000/api/schema/redoc/

These endpoints are registered in `project/urls.py` and reflect the current API surface. If you add or change view/serializer docstrings, the generated schema will include them after rebuilding/restarting the web service.

Authentication
--------------
- TokenAuth (DRF Token) is provided. Obtain a token by POSTing credentials to:

	POST /api/v1/auth/token/  with JSON {"username": "<user>", "password": "<pass>"}

	The endpoint returns `{ "token": "<token>" }` on success. The SPA stores this in `localStorage` and sends `Authorization: Token <token>` on protected requests.

- The SPA also provides a fallback input where you can paste a token manually (useful for admin testing).

Admin SPA
---------
- Features:
	- Conversation list (left) with independent scrolling.
	- Conversation detail (right): shows inbound/outbound messages, timestamps, and sender info.
	- Reply composer: send replies which are delivered asynchronously via Celery.
	- Jump-to-latest button and auto-scroll behavior (only auto-scrolls if you are at the bottom).
	- Simple login UI (username + password -> token) or paste a token directly.

Developer notes (build & tests)
------------------------------
- Frontend
	- Built with Vite + React. To build locally (outside Docker):

		```bash
		cd frontend
		npm ci
		npm run build
		```

	- The Docker image builds the frontend automatically; run `docker compose build frontend` to recompile and update the nginx-served assets.

- Backend
	- Install Python deps and run tests:

		```bash
		pip install -r requirements.txt
		pytest
		```

Troubleshooting & tips
----------------------
- If the frontend changes don't appear in the runtime nginx container, rebuild the frontend image with `docker compose build frontend` and restart the frontend+nginx services:

	```bash
	docker compose build frontend
	docker compose up -d frontend nginx
	```

- If `npm` is not available on your host and you attempted to build locally, use the Docker build instead (multi-stage solves this).
- If API docs (Swagger/ReDoc) show unexpected errors, ensure `drf-spectacular` is installed and the `web` image has been rebuilt.

Useful commands summary
-----------------------
- Build & start everything (background):

	docker compose build
	docker compose up -d

- Rebuild frontend only:

	docker compose build frontend
	docker compose up -d frontend nginx

- Run Django migrations:

	docker compose exec web python manage.py migrate

- Create superuser:

	docker compose exec web python manage.py createsuperuser

Next steps & ideas
------------------
- Add websocket (channels) or Server-Sent Events to enable realtime inbound messages without polling.
- Add RBAC or more advanced auth (JWT, OAuth) for production deployments.
- Harden webhook verification (HMAC signatures, replay protection) and more granular delivery receipts.
- Improve frontend UX: message search, conversation filters, mobile optimizations, and dark/light theme toggle.

Credits
-------
This project scaffold was assembled to demonstrate a minimal but practical pattern for integrating multiple chat inputs into a single admin UI, with async reply delivery.

License
-------
MIT-style / use as you like for prototyping and experimentation. No warranty.


