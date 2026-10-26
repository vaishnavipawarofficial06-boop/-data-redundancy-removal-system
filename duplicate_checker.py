import hashlib
import re

from rapidfuzz.fuzz import ratio


def normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def normalize_phone(value: str) -> str:
    return re.sub(r"\D", "", value)


def create_hash(name: str, email: str, phone: str) -> str:
    data = normalize_text(name) + "|" + normalize_text(email) + "|" + normalize_phone(phone)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def classify_similarity(score: float) -> str:
    if score >= 95:
        return "duplicate"
    if score >= 70:
        return "possible_duplicate"
    return "unique"


def calculate_similarity_details(new_record, existing_record):
    """Return explainable weighted fuzzy scores for each identity field."""
    name_score = ratio(normalize_text(new_record.name), normalize_text(existing_record.name))
    email_score = ratio(normalize_text(new_record.email), normalize_text(existing_record.email))
    phone_score = ratio(normalize_phone(new_record.phone), normalize_phone(existing_record.phone))
    overall = round(name_score * 0.4 + email_score * 0.3 + phone_score * 0.3, 2)
    return {
        "overall_score": overall,
        "classification": classify_similarity(overall),
        "field_scores": {
            "name": round(name_score, 2),
            "email": round(email_score, 2),
            "phone": round(phone_score, 2),
        },
        "weights": {"name": 0.4, "email": 0.3, "phone": 0.3},
    }


def calculate_similarity(new_record, existing_record):
    return calculate_similarity_details(new_record, existing_record)["overall_score"]
