# Advanced Python Project Guide

This repository is a FastAPI + SQLAlchemy data redundancy removal application.

## Included project capabilities

- Normalize contact records before comparison.
- SHA-256 identity fingerprints for exact-match checks.
- Fuzzy similarity scoring and duplicate/review classifications.
- Search and pagination, CSV export, bulk import, dashboard statistics.
- Automated unit tests for normalization, hashing, and classification.
- GitHub Actions CI matrix for Python 3.10–3.13.
- Docker image build recipe.

## Local development

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest-cov ruff
pytest --cov=duplicate_checker --cov-report=term-missing
ruff check .
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000` for the dashboard and `http://127.0.0.1:8000/docs` for OpenAPI docs.

## Docker

```bash
docker build -t data-redundancy-removal-system .
docker run --rm -p 8000:8000 data-redundancy-removal-system
```

## Production hardening checklist

Before deploying to the public internet, implement and verify:

1. Authentication and role-based authorization.
2. Rate limiting and request-size limits at the API gateway.
3. Database migrations (for example, Alembic) instead of relying on startup table creation.
4. A configurable database URL and production database connection pooling.
5. Structured logging, request IDs, metrics, and error monitoring.
6. Backups, retention policy, and recovery tests.
7. A review workflow for possible duplicates rather than silently discarding records.
8. Integration tests using an isolated test database.
9. Dependency pinning and automated dependency/security updates.
10. A privacy policy and access controls for personal data.

The Dockerfile is a deployment starting point, not a claim that the app is production-secure. Do not expose real contact data or secrets in sample data, logs, or test fixtures.
