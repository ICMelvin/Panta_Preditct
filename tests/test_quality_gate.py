from backend.quality_gate import run_quality_gate, check_deadline, check_source, check_binary


def test_good_question_passes_all_checks():
    q = "Will Team X win the match by Friday? per official results at example.com"
    result = run_quality_gate(q)
    assert result.passed
    assert result.deadline.passed
    assert result.source.passed
    assert result.binary.passed


def test_missing_deadline_fails():
    q = "Will Team X win the match? per official results at example.com"
    result = run_quality_gate(q)
    assert not result.deadline.passed
    assert not result.passed


def test_missing_source_fails_without_source_field():
    q = "Will Team X win the match by Friday?"
    result = run_quality_gate(q)
    assert not result.source.passed


def test_source_field_satisfies_source_check():
    q = "Will Team X win the match by Friday?"
    result = run_quality_gate(q, source_field="https://example.com/results")
    assert result.source.passed


def test_hedging_language_fails_binary_check():
    q = "Will Team X probably win by Friday? per example.com"
    result = run_quality_gate(q)
    assert not result.binary.passed


def test_deadline_with_date_formats():
    """Test various date format patterns."""
    # ISO date
    assert check_deadline("Will X happen by 2026-12-31?").passed
    # US date format
    assert check_deadline("Will X happen by 12/31/2026?").passed
    # European date format
    assert check_deadline("Will X happen by 31-12-2026?").passed
    # Day names
    assert check_deadline("Will X happen by Monday?").passed
    assert check_deadline("Will X happen before Friday?").passed
    # Month names
    assert check_deadline("Will X happen by December 31st?").passed
    # Abbreviations
    assert check_deadline("Will X happen by end of day?").passed
    assert check_deadline("Will X happen by EOD?").passed
    assert check_deadline("Will X happen by end of week?").passed


def test_deadline_rejection():
    """Test that questions without clear deadlines fail."""
    assert not check_deadline("Will X happen?").passed
    assert not check_deadline("Will X happen soon?").passed
    assert not check_deadline("Will X happen in the future?").passed


def test_source_detection_various_patterns():
    """Test different ways sources can be specified."""
    # HTTP URLs
    assert check_source("Will X happen? https://example.com").passed
    assert check_source("Will X happen? http://news.site/article").passed
    # Named source hints
    assert check_source("Will X happen according to official results?").passed
    assert check_source("Will X happen per the data?").passed
    assert check_source("Will X happen source: official stats?").passed
    assert check_source("Will X happen via the API?").passed


def test_source_field_with_non_url():
    """Test that non-URL source fields still pass if they have content."""
    assert check_source("Will X happen?", source_field="Official government statistics").passed
    assert check_source("Will X happen?", source_field="Bloomberg terminal data").passed


def test_source_field_empty_string_fails():
    """Test that empty source field should fail."""
    assert not check_source("Will X happen?", source_field="").passed
    assert not check_source("Will X happen?", source_field="   ").passed


def test_binary_check_various_hedging_words():
    """Test various hedging/ambiguous words."""
    ambiguous_words = ["maybe", "kind of", "sort of", "probably", "roughly", "around", "approximately"]
    for word in ambiguous_words:
        q = f"Will X {word} happen by Friday?"
        assert not check_binary(q).passed, f"Should fail for hedging word: {word}"


def test_binary_check_valid_questions():
    """Test valid yes/no question patterns."""
    valid_questions = [
        "Will X happen by Friday?",
        "Will the price reach $100 by end of year?",
        "Will the team win the championship?",
        "Will the election result be certified by January?",
    ]
    for q in valid_questions:
        assert check_binary(q).passed, f"Should pass for: {q}"


def test_binary_check_non_question_format_fails():
    """Test that non-question formats fail."""
    assert not check_binary("X will happen by Friday").passed
    assert not check_binary("I think X will happen").passed
    assert not check_binary("X happening by Friday?").passed  # Missing "Will"


def test_to_dict_serialization():
    """Test that QualityGateResult can be serialized to dict."""
    result = run_quality_gate("Will X happen by Friday? https://example.com")
    d = result.to_dict()
    assert "passed" in d
    assert "checks" in d
    assert "deadline" in d["checks"]
    assert "source" in d["checks"]
    assert "binary" in d["checks"]
    assert "passed" in d["checks"]["deadline"]
    assert "message" in d["checks"]["deadline"]


def test_multiple_failures():
    """Test question that fails multiple checks."""
    q = "X might happen"  # No deadline, no source, not a yes/no question
    result = run_quality_gate(q)
    assert not result.deadline.passed
    assert not result.source.passed
    assert not result.binary.passed
    assert not result.passed


def test_case_insensitivity():
    """Test that checks are case-insensitive."""
    # Deadline
    assert check_deadline("Will X happen BY FRIDAY?").passed
    assert check_deadline("Will X happen By Monday?").passed
    # Source
    assert check_source("Will X happen ACCORDING TO data?").passed
    assert check_source("Will X happen PER the stats?").passed
    # Binary
    assert check_binary("WILL X happen by Friday?").passed


def test_edge_case_whitespace():
    """Test handling of whitespace in questions."""
    # Leading/trailing whitespace
    assert check_binary("   Will X happen by Friday?   ").passed
    # Multiple spaces
    assert check_binary("Will  X  happen  by  Friday?").passed
