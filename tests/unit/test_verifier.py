"""
Unit tests for the Verifier.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from verification.verifier import Verifier


BRIEF_DATE = date(2024, 1, 31)

SAMPLE_FACTS = [
    {
        "id": "DGS10_daily_2024-01-31",
        "fact_type": "daily_change",
        "series_id": "DGS10",
        "value": 8.0,
        "units": "bps",
        "magnitude": 8.0,
        "description": "DGS10 rose 8.0 bps to 4.23% on 2024-01-31",
    },
    {
        "id": "DGS10_level_2024-01-31",
        "fact_type": "level",
        "series_id": "DGS10",
        "value": 4.23,
        "units": "percent",
        "magnitude": 4.23,
        "description": "DGS10 was 4.23% on 2024-01-31",
    },
]

SAMPLE_CHUNKS = [
    {
        "id": 999,
        "chunk_text": "The Federal Reserve raised the federal funds rate by 25 basis points.",
        "source_url": "https://www.federalreserve.gov/...",
        "meeting_date": date(2024, 1, 31),
        "doc_type": "STATEMENT",
    }
]


class TestVerifier:
    @pytest.fixture
    def verifier(self):
        v = Verifier()
        return v

    def test_supported_sentence(self, verifier):
        with (
            patch.object(verifier, "_fetch_facts_for_date", return_value=SAMPLE_FACTS),
            patch.object(verifier, "_fetch_facts_by_ids", return_value=SAMPLE_FACTS),
            patch.object(verifier, "_fetch_chunks_by_ids", return_value=SAMPLE_CHUNKS),
        ):
            result = verifier.verify_sentence(
                sentence_id="s1",
                sentence_text="The 10-year yield rose 8 basis points to 4.23% on January 31.",
                fact_ids=["DGS10_daily_2024-01-31"],
                chunk_ids=[999],
                brief_date=BRIEF_DATE,
                all_facts=SAMPLE_FACTS,
            )

        assert result.verdict in ("SUPPORTED", "PARTIAL")
        assert result.claim_id == "s1"

    def test_unsupported_sentence_no_citations(self, verifier):
        with (
            patch.object(verifier, "_fetch_facts_for_date", return_value=SAMPLE_FACTS),
            patch.object(verifier, "_fetch_facts_by_ids", return_value=[]),
            patch.object(verifier, "_fetch_chunks_by_ids", return_value=[]),
        ):
            result = verifier.verify_sentence(
                sentence_id="s2",
                sentence_text="The Fed will likely cut rates next quarter.",
                fact_ids=[],
                chunk_ids=[],
                brief_date=BRIEF_DATE,
                all_facts=SAMPLE_FACTS,
            )

        assert result.verdict == "UNSUPPORTED"
        assert any("No fact_ids" in issue or "no citations" in issue.lower() for issue in result.issues)

    def test_causal_language_flagged(self, verifier):
        with (
            patch.object(verifier, "_fetch_facts_for_date", return_value=SAMPLE_FACTS),
            patch.object(verifier, "_fetch_facts_by_ids", return_value=SAMPLE_FACTS),
            patch.object(verifier, "_fetch_chunks_by_ids", return_value=[
                {**SAMPLE_CHUNKS[0], "chunk_text": "The Fed raised rates unexpectedly."}
            ]),
        ):
            result = verifier.verify_sentence(
                sentence_id="s3",
                sentence_text="The announcement caused yields to rise sharply.",
                fact_ids=["DGS10_daily_2024-01-31"],
                chunk_ids=[999],
                brief_date=BRIEF_DATE,
                all_facts=SAMPLE_FACTS,
            )

        assert any("Causal" in issue for issue in result.issues)

    def test_metrics_calculation(self, verifier):
        from verification.verifier import ClaimVerification
        results = [
            ClaimVerification("s1", "text", "SUPPORTED", [], [], 1.0),
            ClaimVerification("s2", "text", "UNSUPPORTED", ["No citation"], [], 0.1),
            ClaimVerification("s3", "text", "PARTIAL", [], [], 0.6),
        ]
        metrics = verifier.compute_metrics(results)

        assert metrics["total_claims"] == 3
        assert abs(metrics["supported_rate"] - 1 / 3) < 0.01
        assert abs(metrics["unsupported_rate"] - 1 / 3) < 0.01


class TestChecks:
    def test_number_not_in_facts_flagged(self):
        v = Verifier()
        issues = v._check_numbers(
            text="Yields rose 999 basis points.",
            cited_facts=[],
            brief_date=BRIEF_DATE,
            all_facts=SAMPLE_FACTS,
        )
        assert any("999" in i for i in issues)

    def test_number_matching_fact_ok(self):
        v = Verifier()
        issues = v._check_numbers(
            text="Yields rose 8 basis points.",
            cited_facts=SAMPLE_FACTS,
            brief_date=BRIEF_DATE,
            all_facts=SAMPLE_FACTS,
        )
        # Should have no or few issues
        assert len(issues) == 0

