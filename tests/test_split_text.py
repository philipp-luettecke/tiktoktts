"""Tests for the _split_text chunking helper in tts.py.

Direct mode must split long messages on natural boundaries (sentence, then
word, then a hard cut) without ever exceeding the per-request character
limit or producing empty chunks.
"""

from __future__ import annotations

import pytest

from custom_components.tiktoktts.tts import _split_text


def test_short_text_returned_unchanged() -> None:
    assert _split_text("hello", 200) == ["hello"]


def test_text_exactly_chunk_size_not_split() -> None:
    text = "a" * 10
    assert _split_text(text, 10) == [text]


def test_empty_string() -> None:
    assert _split_text("", 200) == [""]


def test_splits_on_sentence_boundary() -> None:
    """Sentence-ending punctuation + space is the preferred split point."""
    text = "Hello there. How are you doing today?"
    assert _split_text(text, 20) == ["Hello there.", "How are you doing", "today?"]


def test_splits_on_word_boundary_when_no_sentence() -> None:
    """With no sentence punctuation, split at the last space in the window."""
    text = "one two three four five six"
    chunks = _split_text(text, 10)
    assert chunks == ["one two", "three", "four five", "six"]
    assert all(len(c) <= 10 for c in chunks)


def test_window_ending_exactly_on_punctuation() -> None:
    """A '!' as the final window character is treated as a split point."""
    text = "Hello world!Goodbye now"
    assert _split_text(text, 12) == ["Hello world!", "Goodbye now"]


def test_hard_split_when_no_natural_boundary() -> None:
    """Text with no spaces or punctuation is cut at exactly chunk_size."""
    text = "a" * 50
    assert _split_text(text, 20) == ["a" * 20, "a" * 20, "a" * 10]


@pytest.mark.parametrize(
    "text",
    [
        "The quick brown fox. Jumps over the lazy dog! Really? Yes indeed.",
        "x" * 1000,
        "word " * 200,
        "Mixed. Content here! With? punctuation and-some-very-long-unbroken-token" * 5,
    ],
)
def test_chunks_never_exceed_size_and_are_non_empty(text: str) -> None:
    """Core invariant: no chunk exceeds the limit or is empty."""
    chunk_size = 50
    chunks = _split_text(text, chunk_size)
    assert chunks, "expected at least one chunk"
    for chunk in chunks:
        assert 0 < len(chunk) <= chunk_size


def test_all_visible_characters_preserved() -> None:
    """Splitting only drops boundary whitespace, never visible characters."""
    text = "Alpha beta gamma. Delta epsilon zeta! Eta theta iota kappa."
    chunks = _split_text(text, 25)
    joined = "".join(chunks).replace(" ", "")
    assert joined == text.replace(" ", "")
