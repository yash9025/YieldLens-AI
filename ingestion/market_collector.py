"""
YieldLens AI — Market Data Collector
Fetches timestamped Treasury yield and rate observations from FRED and Yahoo Finance.
Stores each observation with a canonical source URL for full provenance.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Generator

import pandas as pd
from fredapi import Fred
from loguru import logger

from config import settings


# ── FRED series we care about ─────────────────────────────────────────────────
FRED_SERIES: dict[str, dict] = {
    "DFF":    {"name": "Federal Funds Rate (Effective)",      "units": "percent"},
    "DGS2":   {"name": "2-Year Treasury Constant Maturity",   "units": "percent"},
    "DGS5":   {"name": "5-Year Treasury Constant Maturity",   "units": "percent"},
    "DGS10":  {"name": "10-Year Treasury Constant Maturity",  "units": "percent"},
    "DGS30":  {"name": "30-Year Treasury Constant Maturity",  "units": "percent"},
    "T10Y2Y": {"name": "10Y-2Y Treasury Spread",              "units": "percent"},
    "T10Y3M": {"name": "10Y-3M Treasury Spread",              "units": "percent"},
    "DFII10": {"name": "10-Year TIPS (Real Yield)",           "units": "percent"},
    "BAMLH0A0HYM2": {"name": "HY Credit Spread (OAS)",       "units": "percent"},
}

FRED_BASE_URL = "https://fred.stlouisfed.org/series/{series_id}"


@dataclass
class MarketObservationRecord:
    """A single validated market data point with full provenance."""

    obs_date: date
    series_id: str
    value: float
    units: str
    source_url: str
    provider: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "obs_date": self.obs_date,
            "series_id": self.series_id,
            "value": self.value,
            "units": self.units,
            "source_url": self.source_url,
            "provider": self.provider,
            "fetched_at": self.fetched_at,
        }


class MarketCollector:
    """
    Collects market observations from FRED.

    Each record stores:
    - obs_date  : the date of the observation
    - series_id : e.g. "DGS10"
    - value     : numeric value
    - units     : "percent" etc.
    - source_url: canonical FRED URL for the series (provenance)
    - provider  : "FRED"
    """

    def __init__(self) -> None:
        if not settings.fred_api_key:
            raise ValueError(
                "FRED_API_KEY is not set. "
                "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self._fred = Fred(api_key=settings.fred_api_key)
        logger.info("MarketCollector initialised with FRED API")

    def fetch_series(
        self,
        series_id: str,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
    ) -> list[MarketObservationRecord]:
        """
        Fetch a single FRED series and return a list of observation records.

        Args:
            series_id: FRED series identifier (e.g. "DGS10")
            start_date: inclusive start (ISO string or date object); defaults to 2000-01-01
            end_date: inclusive end; defaults to today

        Returns:
            List of MarketObservationRecord, one per trading day.
        """
        if series_id not in FRED_SERIES:
            raise ValueError(
                f"Unknown series '{series_id}'. "
                f"Supported: {list(FRED_SERIES.keys())}"
            )

        meta = FRED_SERIES[series_id]
        source_url = FRED_BASE_URL.format(series_id=series_id)
        start = start_date or "2000-01-01"
        end = end_date or date.today().isoformat()

        logger.info(f"Fetching FRED series {series_id!r} from {start} to {end}")
        fetched_at = datetime.now(timezone.utc)

        try:
            series: pd.Series = self._fred.get_series(
                series_id, observation_start=str(start), observation_end=str(end)
            )
        except Exception as exc:
            logger.error(f"FRED fetch failed for {series_id}: {exc}")
            raise

        records: list[MarketObservationRecord] = []
        for ts, val in series.items():
            if pd.isna(val):
                continue  # skip missing observations (holidays, weekends)
            records.append(
                MarketObservationRecord(
                    obs_date=ts.date() if hasattr(ts, "date") else ts,
                    series_id=series_id,
                    value=float(val),
                    units=meta["units"],
                    source_url=source_url,
                    provider="FRED",
                    fetched_at=fetched_at,
                )
            )

        logger.info(f"  → {len(records)} observations for {series_id}")
        return records

    def fetch_all_series(
        self,
        start_date: str | date | None = None,
        end_date: str | date | None = None,
        delay: float | None = None,
    ) -> dict[str, list[MarketObservationRecord]]:
        """
        Fetch all configured FRED series with a polite delay between requests.

        Returns:
            Dict mapping series_id → list of records.
        """
        pause = delay if delay is not None else 0.5
        results: dict[str, list[MarketObservationRecord]] = {}

        for series_id in FRED_SERIES:
            results[series_id] = self.fetch_series(series_id, start_date, end_date)
            time.sleep(pause)

        total = sum(len(v) for v in results.values())
        logger.info(f"Fetched {total} total observations across {len(results)} series")
        return results

    def fetch_latest(self) -> dict[str, MarketObservationRecord | None]:
        """
        Fetch the most recent available observation for every series.

        Returns:
            Dict mapping series_id → most recent record (or None if unavailable).
        """
        results: dict[str, MarketObservationRecord | None] = {}
        for series_id in FRED_SERIES:
            try:
                records = self.fetch_series(series_id)
                results[series_id] = records[-1] if records else None
            except Exception as exc:
                logger.warning(f"Could not fetch latest for {series_id}: {exc}")
                results[series_id] = None
            time.sleep(0.3)
        return results

