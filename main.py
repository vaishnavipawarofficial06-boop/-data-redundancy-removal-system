import csv
import io
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Record
from validator import RecordInput
from duplicate_checker import create_hash, calculate_similarity, classify_similarity

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Data Redundancy Removal System",
    description="Detect, review, search, and remove duplicate records.",
    version="2.0.0",
)


@app.get("/", response_class=HTMLResponse)
def home():
    from pathlib import Path
    index = Path(__file__).parent / "static" / "index.html"
    if index.exists():
        return index.read_text(encoding="utf-8")
    return "<h1>Data Redundancy Removal System</h1><p>API docs: <a href='/docs'>/docs</a></p>"


@app.get("/health")
def health():
    return {"status": "ok", "service": "data-redundancy-removal-system"}


@app.post("/records")
def add_record(record: RecordInput, db: Session = Depends(get_db)):
    clean_name = " ".join(record.name.split())
    clean_email = str(record.email).lower().strip()
    clean_phone = record.phone.strip()
    normalized = RecordInput(name=clean_name, email=clean_email, phone=clean_phone)
    record_hash = create_hash(normalized.name, normalized.email, normalized.phone)

    existing_record = db.query(Record).filter(Record.record_hash == record_hash).first()
    if existing_record:
        return {
            "status": "duplicate",
            "classification": "duplicate",
            "message": "Exact duplicate detected. Data was not added.",
            "existing_record_id": existing_record.id,
            "similarity_score": 100.0,
        }

    all_records = db.query(Record).all()
    best_match = None
    best_score = 0.0
    for existing in all_records:
        similarity = calculate_similarity(normalized, existing)
        if similarity > best_score:
            best_score, best_match = similarity, existing

    classification = classify_similarity(best_score)
    if best_match and classification == "duplicate":
        return {
            "status": "duplicate",
            "classification": "duplicate",
            "similarity_score": best_score,
            "message": "Very similar record detected. Data was not added.",
            "existing_record_id": best_match.id,
        }
    if best_match and classification == "possible_duplicate":
        return {
            "status": "review",
            "classification": "possible_duplicate",
            "similarity_score": best_score,
            "message": "Possible duplicate detected. Review the matching record before adding.",
            "existing_record_id": best_match.id,
        }

    new_record = Record(
        name=normalized.name,
        email=normalized.email,
        phone=normalized.phone,
        record_hash=record_hash,
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return {
        "status": "success",
        "classification": "unique",
        "message": "Unique record added successfully.",
        "record_id": new_record.id,
    }


@app.get("/records")
def get_records(
    q: str | None = None,
    page: int | None = Query(default=None, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Record)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(or_(
            Record.name.ilike(term),
            Record.email.ilike(term),
            Record.phone.ilike(term),
        ))
    total = query.count()
    records_query = query.order_by(Record.id.desc())
    if page is None and q is None:
        return [
            {"id": r.id, "name": r.name, "email": r.email, "phone": r.phone}
            for r in records_query.all()
        ]
    current_page = page or 1
    records = records_query.offset((current_page - 1) * page_size).limit(page_size).all()
    return {
        "items": [{"id": r.id, "name": r.name, "email": r.email, "phone": r.phone} for r in records],
        "total": total,
        "page": current_page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Record.id)).scalar() or 0
    domains = db.query(
        func.lower(func.substr(Record.email, func.instr(Record.email, "@") + 1)).label("domain"),
        func.count(Record.id).label("count"),
    ).group_by("domain").order_by(func.count(Record.id).desc()).limit(5).all()
    recent = db.query(Record).order_by(Record.id.desc()).limit(5).all()
    return {
        "total_records": total,
        "unique_records": total,
        "top_email_domains": [{"domain": d, "count": count} for d, count in domains],
        "recent_records": [
            {"id": r.id, "name": r.name, "email": r.email, "phone": r.phone}
            for r in recent
        ],
    }


@app.get("/records/export.csv")
def export_records(db: Session = Depends(get_db)):
    records = db.query(Record).order_by(Record.id.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "email", "phone"])
    for record in records:
        values = [record.id, record.name, record.email, record.phone]
        safe_values = []
        for value in values:
            text = str(value or "")
            if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
                text = "'" + text
            safe_values.append(text)
        writer.writerow(safe_values)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="records-export.csv"'},
    )


@app.delete("/records/{record_id}", status_code=204)
def delete_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(Record).filter(Record.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    db.delete(record)
    db.commit()
    return None


@app.post("/records/bulk")
def bulk_add_records(records: list[RecordInput], db: Session = Depends(get_db)):
    if len(records) > 500:
        raise HTTPException(status_code=413, detail="Maximum 500 records per import")
    result = {"added": 0, "duplicates": 0, "review": 0, "errors": []}
    for index, record in enumerate(records, start=1):
        clean_name = " ".join(record.name.split())
        clean_email = str(record.email).lower().strip()
        clean_phone = record.phone.strip()
        record_hash = create_hash(clean_name, clean_email, clean_phone)
        if db.query(Record).filter(Record.record_hash == record_hash).first():
            result["duplicates"] += 1
            continue
        normalized = RecordInput(name=clean_name, email=clean_email, phone=clean_phone)
        match = None
        score = 0.0
        for existing in db.query(Record).all():
            current = calculate_similarity(normalized, existing)
            if current > score:
                score, match = current, existing
        classification = classify_similarity(score)
        if match and classification == "duplicate":
            result["duplicates"] += 1
            continue
        if match and classification == "possible_duplicate":
            result["review"] += 1
            result["errors"].append({
                "row": index,
                "classification": "possible_duplicate",
                "similarity_score": score,
                "existing_record_id": match.id,
            })
            continue
        db.add(Record(name=clean_name, email=clean_email, phone=clean_phone, record_hash=record_hash))
        db.flush()
        result["added"] += 1
    db.commit()
    return {"status": "completed", **result}


@app.get("/docs-info")
def docs_info():
    return {
        "api_docs": "/docs",
        "openapi": "/openapi.json",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
