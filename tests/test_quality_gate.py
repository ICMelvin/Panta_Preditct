from backend.quality_gate import run_quality_gate


def test_good_question_passes_all_checks():
    q = "Will Bitcoin reach $100k by end of 2026? per CoinDesk"
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


def test_iso_date_deadline_passes():
    q = "Will Bitcoin reach $100k by 2026-12-31? per CoinDesk"
    result = run_quality_gate(q)
    assert result.deadline.passed
    assert result.passed


def test_slash_date_deadline_passes():
    q = "Will Bitcoin reach $100k by 12/31/2026? per CoinDesk"
    result = run_quality_gate(q)
    assert result.deadline.passed
    assert result.passed


def test_month_day_year_deadline_passes():
    q = "Will Bitcoin reach $100k by December 31, 2026? per CoinDesk"
    result = run_quality_gate(q)
    assert result.deadline.passed
    assert result.passed


def test_day_month_year_deadline_passes():
    q = "Will Bitcoin reach $100k before 31 December 2026? per CoinDesk"
    result = run_quality_gate(q)
    assert result.deadline.passed
    assert result.passed


def test_end_of_year_deadline_passes():
    q = "Will Bitcoin reach $100k by end of 2026? per CoinDesk"
    result = run_quality_gate(q)
    assert result.deadline.passed
    assert result.passed


def test_friday_deadline_passes():
    q = "Will Bitcoin reach $100k by Friday? per CoinDesk"
    result = run_quality_gate(q)
    assert result.deadline.passed
    assert result.passed


def test_relative_deadline_fails():
    q = "ethereum will reach $5k in the next month ? per example.com"
    result = run_quality_gate(q)
    assert not result.deadline.passed
    assert not result.passed


def test_special_characters_in_question_passes():
    # Test that special characters are handled correctly
    q = "Will A & B reach 100% by 2026-12-31? per CoinDesk"
    result = run_quality_gate(q)
    assert result.deadline.passed
    assert result.source.passed  # "per CoinDesk" provides source
    assert result.binary.passed
    assert result.passed


def test_html_tags_in_question_passes():
    # Test that HTML tags are handled as literal text (not rendered)
    q = "Will A & B reach 100% by 2026-12-31? per <b>CoinDesk</b> #test"
    result = run_quality_gate(q)
    assert result.deadline.passed
    assert result.source.passed  # "per <b>CoinDesk</b>" provides source
    assert result.binary.passed
    assert result.passed
