import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from auth import LoginInput, _decode_token, authenticate, create_access_token
from duplicate_checker import calculate_similarity_details


def test_similarity_details_explain_each_field():
    record = SimpleNamespace(name="Asha Patil", email="asha@example.com", phone="+91 9876543210")
    details = calculate_similarity_details(record, record)
    assert details["overall_score"] == 100.0
    assert details["classification"] == "duplicate"
    assert details["field_scores"] == {"name": 100.0, "email": 100.0, "phone": 100.0}
    assert sum(details["weights"].values()) == pytest.approx(1.0)


def test_jwt_token_contains_admin_role(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-that-is-at-least-32-characters-long")
    token = create_access_token("admin-user")
    payload = _decode_token(token)
    assert payload["sub"] == "admin-user"
    assert payload["role"] == "admin"


def test_invalid_jwt_signature_is_rejected(monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-that-is-at-least-32-characters-long")
    token = create_access_token("admin-user")
    with pytest.raises(HTTPException) as error:
        _decode_token(token + "tampered")
    assert error.value.status_code == 401


def test_admin_login_uses_environment_credentials(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-that-is-at-least-32-characters-long")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-strong-test-password")
    token = authenticate(LoginInput(username="admin", password="a-strong-test-password"))
    assert _decode_token(token)["role"] == "admin"


def test_bad_admin_login_is_rejected(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-that-is-at-least-32-characters-long")
    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-strong-test-password")
    with pytest.raises(HTTPException) as error:
        authenticate(LoginInput(username="admin", password="wrong-password"))
    assert error.value.status_code == 401
