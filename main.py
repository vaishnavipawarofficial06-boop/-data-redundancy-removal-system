from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Record
from validator import RecordInput

from duplicate_checker import (
    create_hash,
    calculate_similarity,
    classify_similarity
)


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Data Redundancy Removal System",
    version="1.0.0"
)


@app.get("/")
def home():
    return {
        "message": "Data Redundancy Removal System is running"
    }


@app.post("/records")
def add_record(
    record: RecordInput,
    db: Session = Depends(get_db)
):

    # Create hash for exact duplicate detection
    record_hash = create_hash(
        record.name,
        record.email,
        record.phone
    )

    # Check exact duplicate
    existing_record = (
        db.query(Record)
        .filter(Record.record_hash == record_hash)
        .first()
    )

    if existing_record:
        return {
            "status": "duplicate",
            "classification": "duplicate",
            "message": "Duplicate record detected. Data was not added.",
            "existing_record_id": existing_record.id
        }

    # Check similar records
    all_records = db.query(Record).all()

    for existing in all_records:

        similarity = calculate_similarity(
            record,
            existing
        )

        classification = classify_similarity(
            similarity
        )

        if classification == "duplicate":
            return {
                "status": "duplicate",
                "classification": "duplicate",
                "similarity_score": similarity,
                "message": "Very similar record detected. Data was not added.",
                "existing_record_id": existing.id
            }

        if classification == "possible_duplicate":
            return {
                "status": "review",
                "classification": "possible_duplicate",
                "similarity_score": similarity,
                "message": "Possible duplicate detected. Manual review required.",
                "existing_record_id": existing.id
            }

    # Add unique record
    new_record = Record(
        name=record.name.strip(),
        email=str(record.email).lower().strip(),
        phone=record.phone,
        record_hash=record_hash
    )

    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return {
        "status": "success",
        "classification": "unique",
        "message": "Unique record added successfully.",
        "record_id": new_record.id
    }


@app.get("/records")
def get_records(
    db: Session = Depends(get_db)
):

    records = db.query(Record).all()

    return [
        {
            "id": record.id,
            "name": record.name,
            "email": record.email,
            "phone": record.phone
        }
        for record in records
    ]