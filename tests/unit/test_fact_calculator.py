"""
Unit tests for FactCalculator.
Tests the deterministic computation logic without requiring a live database.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from processing.fact_calculator import FactCalculator, StructuredFact, _direction


# ── _direction helper ─────────────────────────────────────────────────────────

def test_direction_up():
    assert _direction(5.0) == "up"

def test_direction_down():
    assert _direction(-3.0) == "down"

def test_direction_flat():
    assert _direction(0.05) == "flat"

def test_direction_exactly_at_threshold():
    assert _direction(0.1) == "flat"
    assert _direction(0.11) == "up"


# ── FactCalculator unit tests (mocked DB) ─────────────────────────────────────

@pytest.fixture
def mock_rows():
    """Mock DB rows: (id, obs_date, value)"""
    return [
        (1001, date(2024, 1, 29), 4.15),  # Monday (prev)
        (1002, date(2024, 1, 30), 4.17),  # Tuesday
        (1003, date(2024, 1, 31), 4.23),  # Wednesday (target)
    ]


class TestDailyChange:
    def test_computes_bps_correctly(self, mock_rows):
        calc = FactCalculator()
        with patch.object(calc, "_fetch_obs", return_value=mock_rows):
            fact = calc.daily_change("DGS10", date(2024, 1, 31))

        assert fact is not None
        assert fact.fact_type == "daily_change"
        # 4.23 - 4.17 = 0.06% = 6 bps
        assert abs(fact.value - 6.0) < 0.5
        assert fact.units == "bps"
        assert fact.direction == "up"
        assert fact.validated is True
        assert len(fact.source_obs_ids) == 2

    def test_returns_none_when_no_data(self):
        calc = FactCalculator()
        with patch.object(calc, "_fetch_obs", return_value=[]):
            fact = calc.daily_change("DGS10", date(2024, 1, 31))
        assert fact is None

    def test_id_format(self, mock_rows):
        calc = FactCalculator()
        with patch.object(calc, "_fetch_obs", return_value=mock_rows):
            fact = calc.daily_change("DGS10", date(2024, 1, 31))
        assert fact.id == "DGS10_daily_2024-01-31"

    def test_description_contains_key_info(self, mock_rows):
        calc = FactCalculator()
        with patch.object(calc, "_fetch_obs", return_value=mock_rows):
            fact = calc.daily_change("DGS10", date(2024, 1, 31))
        assert "DGS10" in fact.description
        assert "4.23" in fact.description

    def test_negative_change(self):
        rows = [
            (1001, date(2024, 1, 30), 4.23),
            (1002, date(2024, 1, 31), 4.17),
        ]
        calc = FactCalculator()
        with patch.object(calc, "_fetch_obs", return_value=rows):
            fact = calc.daily_change("DGS10", date(2024, 1, 31))
        assert fact.direction == "down"
        assert fact.value < 0


class TestYieldCurveSpread:
    def test_spread_computation(self):
        long_rows = [(2001, date(2024, 1, 31), 4.23)]
        short_rows = [(2002, date(2024, 1, 31), 4.68)]

        calc = FactCalculator()

        def mock_fetch(series_id, target_date, lookback_days=40):
            return long_rows if series_id == "DGS10" else short_rows

        with patch.object(calc, "_fetch_obs", side_effect=mock_fetch):
            fact = calc.yield_curve_spread(date(2024, 1, 31), "DGS10", "DGS2")

        assert fact is not None
        # 4.23 - 4.68 = -0.45% = -45 bps (inverted)
        assert abs(fact.value - (-45.0)) < 1.0
        assert "inverted" in fact.description

    def test_spread_id_format(self):
        long_rows = [(2001, date(2024, 1, 31), 4.23)]
        short_rows = [(2002, date(2024, 1, 31), 4.00)]

        calc = FactCalculator()

        def mock_fetch(series_id, target_date, lookback_days=40):
            return long_rows if series_id == "DGS10" else short_rows

        with patch.object(calc, "_fetch_obs", side_effect=mock_fetch):
            fact = calc.yield_curve_spread(date(2024, 1, 31), "DGS10", "DGS2")

        assert "DGS10" in fact.id
        assert "DGS2" in fact.id
        assert "2024-01-31" in fact.id


class TestStructuredFact:
    def test_to_dict_has_required_keys(self, mock_rows):
        calc = FactCalculator()
        with patch.object(calc, "_fetch_obs", return_value=mock_rows):
            fact = calc.daily_change("DGS10", date(2024, 1, 31))

        d = fact.to_dict()
        required_keys = [
            "id", "fact_date", "fact_type", "series_id", "value", "units",
            "direction", "magnitude", "description", "computation",
            "source_obs_ids", "validated", "computed_at",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"

