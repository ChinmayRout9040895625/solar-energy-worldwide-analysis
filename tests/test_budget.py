import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".claude" / "hooks"))

from lib.budget import TRUNCATION_MARKER, estimate_tokens, truncate_to_budget


def test_estimate_tokens_uses_four_chars_per_token():
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_text_under_budget_is_unchanged():
    text = "short line"
    assert truncate_to_budget(text, 100) == text


def test_text_over_budget_is_truncated_and_marked():
    text = "x" * 1000
    result = truncate_to_budget(text, 10)
    assert result.endswith(TRUNCATION_MARKER)
    assert len(result) <= 40 + len(TRUNCATION_MARKER)


def test_zero_or_negative_budget_yields_empty_string():
    assert truncate_to_budget("anything", 0) == ""
    assert truncate_to_budget("anything", -5) == ""
