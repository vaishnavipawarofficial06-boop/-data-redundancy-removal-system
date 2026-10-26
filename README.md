# Data Redundancy Removal System

A FastAPI + SQLAlchemy application that normalizes contact records, detects exact and fuzzy duplicates, and provides a dashboard, CSV export, bulk import, analytics, and optional JWT-protected admin access.

## Features

- Normalize names, emails, and phone numbers before comparison.
- SHA-256 fingerprints for exact duplicate checks.
- Explainable fuzzy matching with per-field name/email/phone scores.
- Preview possible matches with `POST /records/check-duplicates` without saving.
- Search, pagination, CSV export with spreadsheet formula-injection protection.
- Bulk JSON import with a 500-record limit.
- Analytics overview, email-domain distribution, and phone-length distribution.
- Optional JWT authentication for the admin role.
- SQLite by default, configurable PostgreSQL support.
- Optional Redis cache for dashboard statistics; the app falls back to database queries if Redis is unavailable.
- GitHub Actions CI, tests, and Docker support.

## Quick start

Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` for the dashboard and `http://127.0.0.1:8000/docs` for interactive API docs.

Run tests:

```bash
pytest
```

## Authentication and admin access

Authentication is disabled by default for local backwards compatibility. For a deployment, copy `.env.example` to `.env` and set:

- `AUTH_ENABLED=true`
- `ADMIN_USERNAME` to your admin username
- `ADMIN_PASSWORD` to a unique, strong password
- `JWT_SECRET_KEY` to a random secret of at least 32 characters

With authentication enabled, record data endpoints require an admin bearer token. The dashboard displays a login screen and sends the token for API requests.

Login using `POST /auth/token` with JSON:

```json
{"username":"your-admin-user","password":"your-admin-password"}
```

The response contains `access_token`; use it as `Authorization: Bearer <access_token>` for API calls. Tokens expire after one hour. This initial implementation supports one environment-configured admin account, not multi-user registration or per-user database roles.

**Never commit your real `.env`, credentials, or JWT secret.** Use your hosting provider's secret/environment-variable manager in production. Use HTTPS when deployed.

## PostgreSQL

Set `DATABASE_URL` to a PostgreSQL connection string, for example:

```text
DATABASE_URL=postgresql+psycopg://app_user:password@localhost:5432/dataguard
```

Ensure the database exists before starting the application. SQLite remains the default. Existing deployments should back up their data before changing database engines; this project does not automatically migrate data between databases.

## Optional Redis cache

Set `REDIS_URL=redis://localhost:6379/0` to enable a short-lived cache for dashboard statistics. If Redis is not configured or unreachable, the API continues to query the database. Redis is an optimization, not a required service.

## Docker

```bash
docker build -t dataguard .
docker run --rm -p 8000:8000 --env-file .env dataguard
```

## API endpoints

- `POST /records` — detect duplicates and add unique records
- `POST /records/check-duplicates` — preview exact/fuzzy matches with field scores
- `GET /records` — list/search/paginate records
- `GET /stats` — dashboard summary
- `GET /analytics/overview` — domain and phone-length analytics
- `GET /records/export.csv` — download CSV
- `POST /records/bulk` — bulk JSON import, maximum 500 records
- `DELETE /records/{id}` — delete a record
- `POST /auth/token` — issue admin JWT when authentication is enabled
- `GET /auth/status` — report whether authentication is enabled
- `GET /auth/me` — inspect the current authentication context
- `GET /health` — health check
- `GET /docs` — OpenAPI docs

## Production checklist

Before exposing the service publicly, configure strong secrets, enable authentication, enforce HTTPS, set up database backups, use a production ASGI process, add request rate limiting and monitoring, and plan schema migrations (for example, Alembic). Fuzzy similarity is a heuristic, not a machine-learning model; review possible duplicates before taking irreversible action.
