"""
Tests for the RAG retriever and input guardrails added in the final project.

Run with: pytest test/test_rag.py -v
"""
import pytest
from pathlib import Path

from guardrails import (
    ValidationError,
    validate_duration,
    validate_priority,
    validate_time_available,
    validate_time_format,
    validate_pet_name,
)
from rag.retriever import Retriever


# ── Retriever tests ────────────────────────────────────────────────────────────

def test_retriever_loads_chunks():
    """Retriever should load at least one chunk from the knowledge base documents."""
    r = Retriever()
    assert len(r.chunks) > 0, "Retriever found no chunks — check rag/documents/*.txt"


def test_retriever_returns_list():
    """retrieve() should always return a list."""
    r = Retriever()
    result = r.retrieve("dog walk exercise", top_k=3)
    assert isinstance(result, list)


def test_retriever_finds_dog_content():
    """A query about dogs should return chunks that mention dogs."""
    r = Retriever()
    results = r.retrieve("dog exercise walk daily", top_k=3)
    assert results, "No chunks returned for dog query"
    combined = " ".join(results).lower()
    assert "dog" in combined, "Top chunks don't mention 'dog'"


def test_retriever_finds_cat_content():
    """A query about cats should return chunks that mention cats."""
    r = Retriever()
    results = r.retrieve("cat feeding nutrition water", top_k=3)
    assert results, "No chunks returned for cat query"
    combined = " ".join(results).lower()
    assert "cat" in combined, "Top chunks don't mention 'cat'"


def test_retriever_empty_query_returns_empty():
    """An empty or whitespace-only query should return an empty list."""
    r = Retriever()
    assert r.retrieve("") == []
    assert r.retrieve("   ") == []


def test_retriever_top_k_respected():
    """retrieve() should return at most top_k results."""
    r = Retriever()
    results = r.retrieve("pet care medication schedule", top_k=2)
    assert len(results) <= 2


def test_retriever_source_label_in_result():
    """Each returned chunk should include a source label in brackets."""
    r = Retriever()
    results = r.retrieve("grooming brushing nails", top_k=1)
    if results:
        assert results[0].startswith("["), "Result should start with a [Source] label"


# ── Guardrail tests ────────────────────────────────────────────────────────────

def test_validate_duration_valid():
    assert validate_duration(30) == 30
    assert validate_duration(1) == 1
    assert validate_duration(240) == 240


def test_validate_duration_zero_raises():
    with pytest.raises(ValidationError):
        validate_duration(0)


def test_validate_duration_negative_raises():
    with pytest.raises(ValidationError):
        validate_duration(-5)


def test_validate_duration_non_number_raises():
    with pytest.raises(ValidationError):
        validate_duration("thirty")


def test_validate_priority_valid():
    assert validate_priority(1) == 1
    assert validate_priority(5) == 5
    assert validate_priority(10) == 10


def test_validate_priority_too_high_raises():
    with pytest.raises(ValidationError):
        validate_priority(11)


def test_validate_priority_zero_raises():
    with pytest.raises(ValidationError):
        validate_priority(0)


def test_validate_time_format_valid():
    assert validate_time_format("08:00") == "08:00"
    assert validate_time_format("23:59") == "23:59"
    assert validate_time_format("00:00") == "00:00"


def test_validate_time_format_no_colon_raises():
    with pytest.raises(ValidationError):
        validate_time_format("0830")


def test_validate_time_format_single_digit_raises():
    with pytest.raises(ValidationError):
        validate_time_format("8:30")


def test_validate_time_format_out_of_range_raises():
    with pytest.raises(ValidationError):
        validate_time_format("25:00")
    with pytest.raises(ValidationError):
        validate_time_format("12:60")


def test_validate_time_available_positive():
    assert validate_time_available(60) == 60
    assert validate_time_available(1440) == 1440


def test_validate_time_available_zero_raises():
    with pytest.raises(ValidationError):
        validate_time_available(0)


def test_validate_time_available_over_day_raises():
    with pytest.raises(ValidationError):
        validate_time_available(1441)


def test_validate_pet_name_valid():
    assert validate_pet_name("Mochi") == "Mochi"
    assert validate_pet_name("  Fido  ") == "Fido"


def test_validate_pet_name_empty_raises():
    with pytest.raises(ValidationError):
        validate_pet_name("")
    with pytest.raises(ValidationError):
        validate_pet_name("   ")
