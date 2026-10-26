from types import SimpleNamespace

import pytest

from duplicate_checker import (
    calculate_similarity,
    classify_similarity,
    create_hash,
    normalize_phone,
    normalize_text,
)


def test_normalize_text_collapses_whitespace_and_case():
    assert normalize_text("  Asha   PATIL ") == "asha patil"


def test_normalize_phone_keeps_only_digits():
    assert normalize_phone("+91 (98765)-43210") == "919876543210"


def test_hash_is_stable_for_normalized_values():
    first = create_hash("Asha Patil", "ASHA@example.com", "+91 98765 43210")
    second = create_hash(" asha   patil ", "asha@example.com", "919876543210")
    assert first == second


def test_hash_changes_when_identity_data_changes():
    first = create_hash("Asha Patil", "asha@example.com", "9876543210")
    second = create_hash("Asha Patil", "asha@example.com", "9876543211")
    assert first != second


def test_identical_records_have_full_similarity():
    record = SimpleNamespace(name="Asha Patil", email="asha@example.com", phone="9876543210")
    assert calculate_similarity(record, record) == 100.0


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, "duplicate"),
        (95, "duplicate"),
        (94.99, "possible_duplicate"),
        (70, "possible_duplicate"),
        (69.99, "unique"),
        (0, "unique"),
    ],
)
def test_similarity_classification_thresholds(score, expected):
    assert classify_similarity(score) == expected
