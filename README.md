# Data Redundancy Removal System

A FastAPI + SQLAlchemy service that normalizes incoming records, blocks exact duplicates, detects fuzzy matches, and stores unique records.

## Advanced features
- Responsive dashboard UI with live record totals and top email domains
- Exact and fuzzy duplicate detection with similarity scores
- Search by name, email, or phone
- Pagination for large record sets
- Delete records from the dashboard or API
- CSV export with spreadsheet-formula injection protection
- Bulk JSON import (up to 500 records per request) with duplicate/review counts
- Health endpoint and interactive OpenAPI documentation

## Run locally
```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```
Open http://127.0.0.1:8000 for the dashboard and http://127.0.0.1:8000/docs for API docs.

## API endpoints
- `POST /records` — validate, normalize, detect duplicates, and store unique records
- `GET /records` — list records (legacy list response when no query parameters are supplied)
- `GET /records?q=patil&page=1&page_size=10` — search and paginate
- `GET /stats` — dashboard summary and top email domains
- `GET /records/export.csv` — download CSV
- `POST /records/bulk` — bulk JSON import, maximum 500 rows
- `DELETE /records/{id}` — delete a stored record
- `GET /health` — health check
- `GET /docs` — interactive API docs

### Bulk import example
Send an array to `POST /records/bulk`:
```json
[
  {"name":"Asha Patil","email":"asha@example.com","phone":"+919876543210"},
  {"name":"Rohan Shah","email":"rohan@example.com","phone":"+919876543211"}
]
```

The database URL can be configured in `database.py`. Review the service before exposing it publicly; production deployments should add authentication, rate limiting, migrations, and operational monitoring.
