# Advanced Python Project Guide

## Implemented engineering features

- FastAPI API with OpenAPI documentation.
- SQLAlchemy storage using SQLite by default or PostgreSQL through `DATABASE_URL`.
- Optional HS256 JWT authentication for a single environment-configured admin account.
- Admin-only record API access when `AUTH_ENABLED=true`.
- Exact SHA-256 fingerprints and explainable weighted fuzzy matching (name 40%, email 30%, phone 30%).
- Duplicate preview endpoint with per-field scores.
- Optional Redis cache for dashboard statistics with database fallback.
- CSV formula-injection mitigation, paginated search, bulk import limits, analytics, and tests.
- GitHub Actions CI, Docker build support, and environment examples.

## Development commands

```bash
python -m pip install -r requirements.txt
pytest
ruff check .
uvicorn main:app --reload
```

## Configure authentication

Copy `.env.example` to `.env`, set `AUTH_ENABLED=true`, configure a unique `ADMIN_USERNAME`, a strong `ADMIN_PASSWORD`, and a random `JWT_SECRET_KEY` with at least 32 characters. The initial implementation intentionally uses one configured administrator rather than storing user accounts in the database.

## PostgreSQL and Redis

Set `DATABASE_URL=postgresql+psycopg://...` to use PostgreSQL. Set `REDIS_URL=redis://...` to enable short-lived statistics caching. Both are optional; SQLite and direct database reads are the defaults.

## Remaining production hardening

- Add Alembic migrations and database backup/restore tests.
- Add rate limiting, security monitoring, and structured request logging.
- Replace the single-admin environment login with a proper user table and password hashing if multi-user access is required.
- Add integration tests against disposable PostgreSQL/Redis services.
- Fuzzy matching is explainable heuristic scoring, not AI/ML. Train and validate a model against labeled examples before describing it as AI-based.
