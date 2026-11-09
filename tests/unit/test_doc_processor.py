"""
Unit tests for DocumentProcessor (chunking and signal extraction).
No DB or model loading required for most tests.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from processing.doc_processor import DocumentProcessor, HAWKISH_SIGNALS


SAMPLE_FOMC_TEXT = """
The Federal Open Market Committee decided to raise the target range for the federal funds rate
by 75 basis points to 3 to 3-1/4 percent. This action reflects the ongoing commitment of the
Committee to restoring price stability to the economy. Inflation remains elevated, reflecting
supply and demand imbalances related to the pandemic, higher food and energy prices, and
broader price pressures. The Committee is highly attentive to inflation risks.

Recent indicators point to modest growth in spending and production. Job gains have been robust
in recent months, and the unemployment rate has remained low. Inflation remains elevated,
reflecting supply and demand imbalances related to the pandemic, higher food and energy prices,
and broader price pressures.

The Committee seeks to achieve maximum employment and inflation at the rate of 2 percent over
the longer run. In support of these goals, the Committee decided to raise the target range for
the federal funds rate to 3 to 3-1/4 percent and anticipates that ongoing increases in the
target range will be appropriate. The Committee will continue reducing its holdings of Treasury
securities and agency debt and agency mortgage-backed securities.
"""


@pytest.fixture
def processor():
    """Return a processor with a mocked embedding model."""
    with patch("processing.doc_processor.SentenceTransformer") as MockST:
        mock_model = MagicMock()
        mock_model.encode.return_value = [[0.1] * 384]
        MockST.return_value = mock_model
        return DocumentProcessor()


class TestChunking:
    def test_produces_chunks(self, processor):
        chunks = processor.chunk_text(SAMPLE_FOMC_TEXT)
        assert len(chunks) >= 1

    def test_chunks_are_non_empty(self, processor):
        chunks = processor.chunk_text(SAMPLE_FOMC_TEXT)
        for chunk in chunks:
            assert len(chunk.strip()) > 0

    def test_short_text_one_chunk(self, processor):
        short = "The Federal Reserve raised rates."
        chunks = processor.chunk_text(short)
        assert len(chunks) == 1
        assert "Federal Reserve" in chunks[0]

    def test_long_text_multiple_chunks(self, processor):
        # Repeat text to force multiple chunks
        long_text = SAMPLE_FOMC_TEXT * 5
        chunks = processor.chunk_text(long_text, max_tokens=400)
        assert len(chunks) > 1


class TestSignalExtraction:
    def test_detects_hawkish_signal(self, processor):
        text = "Inflation remains elevated and above the 2 percent target."
        signals = processor._extract_signals(text)
        assert len(signals["hawkish_signals"]) >= 1

    def test_detects_dovish_signal(self, processor):
        text = "The labor market remains well below maximum employment."
        signals = processor._extract_signals(text)
        assert len(signals["dovish_signals"]) >= 1

    def test_detects_rate_change(self, processor):
        text = "The Committee decided to raise the federal funds rate by 75 basis points."
        signals = processor._extract_signals(text)
        assert signals["has_rate_change"] is True

    def test_detects_forward_guidance(self, processor):
        text = "The Committee expects to maintain this target range until further notice."
        signals = processor._extract_signals(text)
        assert signals["has_forward_guidance"] is True

    def test_detects_numbers(self, processor):
        text = "The rate was raised by 75 basis points to 5.25 percent."
        signals = processor._extract_signals(text)
        assert len(signals["numbers_found"]) >= 2

    def test_neutral_text_no_signals(self, processor):
        text = "Economic activity expanded at a moderate pace during the second quarter."
        signals = processor._extract_signals(text)
        assert len(signals["hawkish_signals"]) == 0
        assert len(signals["dovish_signals"]) == 0
        assert signals["has_rate_change"] is False

