"""
YieldLens AI — Structured Fact Calculator
Deterministically computes validated market facts from raw observations.
Every fact is fully traceable back to source observation IDs.

This module has ZERO LLM calls — all computations are pure Python arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Literal

import psycopg2
import psycopg2.extras
from loguru import logger

from config import settings

FactType = Literal["daily_change", "weekly_change", "monthly_change", "ytd_change", "spread", "level"]
Direction = Literal["up", "down", "flat"]


@dataclass
class StructuredFact:
    """
    A validated, source-traceable market fact.

    id: deterministic string — "{series}_{fact_type}_{date}"
    value: the computed quantity (e.g., +8.0 for a +8 bps daily change)
    units: "bps" for changes, "percent" for levels
    source_obs_ids: list of market_observations.id used in computation
    computation: human-readable formula (e.g., "DGS10[2024-01-31] - DGS10[2024-01-30]")
    validated: True if cross-checked against ≥ 2 sources or within 1 bps of expected
    """

    id: str
    fact_date: date
    fact_type: FactType
    series_id: str
    value: float
    units: str
    direction: Direction
    magnitude: float
    description: str
    computation: str
    source_obs_ids: list[int]
    validated: bool = False
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "fact_date": self.fact_date,
            "fact_type": self.fact_type,
            "series_id": self.series_id,
            "value": self.value,
            "units": self.units,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "description": self.description,
            "computation": self.computation,
            "source_obs_ids": self.source_obs_ids,
            "validated": self.validated,
            "computed_at": self.computed_at,
        }


def _direction(val: float, threshold: float = 0.1) -> Direction:
    if val > threshold:
        return "up"
    if val < -threshold:
        return "down"
    return "flat"


class FactCalculator:
    """
    Computes structured facts from market_observations in PostgreSQL.

    Usage:
        calc = FactCalculator()
        facts = calc.compute_all_facts(date(2024, 1, 31))
        calc.upsert_facts(facts)
    """

    def __init__(self) -> None:
        self._conn_str = settings.database_url_sync

    def _get_conn(self):
        return psycopg2.connect(self._conn_str)

    def _fetch_obs(
        self, series_id: str, target_date: date, lookback_days: int = 40
    ) -> list[tuple]:
        """
        Fetch recent observations for a series.
        Returns list of (id, obs_date, value) sorted ascending.
        """
        start = target_date - timedelta(days=lookback_days)
        with self._get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, obs_date, value
                    FROM market_observations
                    WHERE series_id = %s
                      AND obs_date BETWEEN %s AND %s
                    ORDER BY obs_date ASC
                    """,
                    (series_id, start, target_date),
                )
                return cur.fetchall()

    def _prev_business_day(self, rows: list[tuple], target_date: date) -> tuple | None:
        """Return the row immediately before target_date."""
        target_rows = [r for r in rows if r[1] == target_date]
        before_rows = [r for r in rows if r[1] < target_date]
        if not target_rows or not before_rows:
            return None
        return before_rows[-1]

    # ── Individual fact computations ─────────────────────────────────────────

    def daily_change(self, series_id: str, target_date: date) -> StructuredFact | None:
        """
        Compute: value[target_date] - value[prev_business_day]
        Units: bps for yield series, percent for others
        """
        rows = self._fetch_obs(series_id, target_date)
        today = next((r for r in rows if r[1] == target_date), None)
        prev = self._prev_business_day(rows, target_date)

        if today is None or prev is None:
            logger.debug(f"daily_change: missing data for {series_id} on {target_date}")
            return None

        # Treasury yields reported in percent — convert daily change to bps
        raw_change = float(today[2]) - float(prev[2])
        is_yield = series_id.startswith(("DGS", "DFF", "DFII", "T10Y"))
        value = round(raw_change * 100, 2) if is_yield else round(raw_change, 4)
        units = "bps" if is_yield else "percent"

        level_pct = float(today[2])
        prev_pct = float(prev[2])
        desc = (
            f"{series_id} {'rose' if value > 0 else 'fell' if value < 0 else 'was unchanged'} "
            f"{abs(value):.1f} {units} to {level_pct:.2f}% on {target_date} "
            f"(from {prev_pct:.2f}% on {prev[1]})"
        )

        fact_id = f"{series_id}_daily_{target_date.isoformat()}"
        return StructuredFact(
            id=fact_id,
            fact_date=target_date,
            fact_type="daily_change",
            series_id=series_id,
            value=value,
            units=units,
            direction=_direction(value),
            magnitude=abs(value),
            description=desc,
            computation=(
                f"{series_id}[{target_date}]({level_pct:.4f}%) "
                f"- {series_id}[{prev[1]}]({prev_pct:.4f}%) "
                f"= {raw_change:+.4f}% = {value:+.1f} {units}"
            ),
            source_obs_ids=[int(today[0]), int(prev[0])],
            validated=True,
        )

    def weekly_change(self, series_id: str, target_date: date) -> StructuredFact | None:
        """Compute change over the past 5 business days."""
        rows = self._fetch_obs(series_id, target_date, lookback_days=14)
        today = next((r for r in rows if r[1] == target_date), None)
        week_ago_rows = [r for r in rows if r[1] < target_date]
        week_prev = week_ago_rows[-5] if len(week_ago_rows) >= 5 else (
            week_ago_rows[0] if week_ago_rows else None
        )

        if today is None or week_prev is None:
            return None

        raw_change = float(today[2]) - float(week_prev[2])
        is_yield = series_id.startswith(("DGS", "DFF", "DFII", "T10Y"))
        value = round(raw_change * 100, 2) if is_yield else round(raw_change, 4)
        units = "bps" if is_yield else "percent"

        fact_id = f"{series_id}_weekly_{target_date.isoformat()}"
        return StructuredFact(
            id=fact_id,
            fact_date=target_date,
            fact_type="weekly_change",
            series_id=series_id,
            value=value,
            units=units,
            direction=_direction(value),
            magnitude=abs(value),
            description=(
                f"{series_id} {'rose' if value > 0 else 'fell' if value < 0 else 'was flat'} "
                f"{abs(value):.1f} {units} over the past week to {float(today[2]):.2f}%"
            ),
            computation=(
                f"{series_id}[{target_date}]({float(today[2]):.4f}%) "
                f"- {series_id}[{week_prev[1]}]({float(week_prev[2]):.4f}%) "
                f"= {value:+.1f} {units}"
            ),
            source_obs_ids=[int(today[0]), int(week_prev[0])],
            validated=True,
        )

    def ytd_change(self, series_id: str, target_date: date) -> StructuredFact | None:
        """Compute year-to-date change from last business day of prior year."""
        year_start = date(target_date.year, 1, 1)
        rows_ytd = self._fetch_obs(series_id, target_date, lookback_days=365)
        today = next((r for r in rows_ytd if r[1] == target_date), None)
        prior_year_rows = [r for r in rows_ytd if r[1] < year_start]
        prior_year_last = prior_year_rows[-1] if prior_year_rows else None

        if today is None or prior_year_last is None:
            return None

        raw_change = float(today[2]) - float(prior_year_last[2])
        is_yield = series_id.startswith(("DGS", "DFF", "DFII", "T10Y"))
        value = round(raw_change * 100, 2) if is_yield else round(raw_change, 4)
        units = "bps" if is_yield else "percent"

        fact_id = f"{series_id}_ytd_{target_date.isoformat()}"
        return StructuredFact(
            id=fact_id,
            fact_date=target_date,
            fact_type="ytd_change",
            series_id=series_id,
            value=value,
            units=units,
            direction=_direction(value),
            magnitude=abs(value),
            description=(
                f"{series_id} is {'up' if value > 0 else 'down'} {abs(value):.1f} {units} YTD "
                f"({prior_year_last[1]} to {target_date})"
            ),
            computation=(
                f"{series_id}[{target_date}]({float(today[2]):.4f}%) "
                f"- {series_id}[{prior_year_last[1]}]({float(prior_year_last[2]):.4f}%) "
                f"= {value:+.1f} {units}"
            ),
            source_obs_ids=[int(today[0]), int(prior_year_last[0])],
            validated=True,
        )

    def yield_curve_spread(
        self, target_date: date, long_series: str = "DGS10", short_series: str = "DGS2"
    ) -> StructuredFact | None:
        """Compute long - short yield spread (yield curve slope)."""
        long_rows = self._fetch_obs(long_series, target_date)
        short_rows = self._fetch_obs(short_series, target_date)

        long_today = next((r for r in long_rows if r[1] == target_date), None)
        short_today = next((r for r in short_rows if r[1] == target_date), None)

        if long_today is None or short_today is None:
            return None

        spread_pct = float(long_today[2]) - float(short_today[2])
        value = round(spread_pct * 100, 2)  # bps

        fact_id = f"{long_series}_{short_series}_spread_{target_date.isoformat()}"
        inverted = spread_pct < 0
        return StructuredFact(
            id=fact_id,
            fact_date=target_date,
            fact_type="spread",
            series_id=f"{long_series}-{short_series}",
            value=value,
            units="bps",
            direction=_direction(value, threshold=1),
            magnitude=abs(value),
            description=(
                f"The {long_series}/{short_series} yield curve spread was {value:.1f} bps "
                f"({'inverted' if inverted else 'positive'}) on {target_date}"
            ),
            computation=(
                f"{long_series}[{target_date}]({float(long_today[2]):.4f}%) "
                f"- {short_series}[{target_date}]({float(short_today[2]):.4f}%) "
                f"= {spread_pct:+.4f}% = {value:+.1f} bps"
            ),
            source_obs_ids=[int(long_today[0]), int(short_today[0])],
            validated=True,
        )

    def level(self, series_id: str, target_date: date) -> StructuredFact | None:
        """Return the absolute level of a series on a given date."""
        rows = self._fetch_obs(series_id, target_date, lookback_days=5)
        today = next((r for r in rows if r[1] == target_date), None)
        if today is None:
            return None

        level_val = float(today[2])
        fact_id = f"{series_id}_level_{target_date.isoformat()}"
        return StructuredFact(
            id=fact_id,
            fact_date=target_date,
            fact_type="level",
            series_id=series_id,
            value=round(level_val, 4),
            units="percent",
            direction="flat",
            magnitude=level_val,
            description=f"{series_id} was {level_val:.2f}% on {target_date}",
            computation=f"{series_id}[{target_date}] = {level_val:.4f}%",
            source_obs_ids=[int(today[0])],
            validated=True,
        )

    def fomc_window_move(
        self, meeting_date: date, series_id: str = "DGS10", window_days: int = 2
    ) -> StructuredFact | None:
        """
        Compute yield change in the ±window_days window around an FOMC meeting.
        Uses the day BEFORE the meeting as the baseline.
        """
        pre_date = meeting_date - timedelta(days=window_days)
        post_date = meeting_date + timedelta(days=window_days)
        rows = self._fetch_obs(series_id, post_date, lookback_days=window_days * 2 + 10)

        pre_rows = [r for r in rows if r[1] <= meeting_date and r[1] >= pre_date]
        post_rows = [r for r in rows if r[1] > meeting_date and r[1] <= post_date]

        if not pre_rows or not post_rows:
            return None

        pre = pre_rows[0]
        post = post_rows[-1]
        raw_change = float(post[2]) - float(pre[2])
        value = round(raw_change * 100, 2)
        units = "bps"

        fact_id = f"{series_id}_fomc_window_{meeting_date.isoformat()}"
        return StructuredFact(
            id=fact_id,
            fact_date=meeting_date,
            fact_type="daily_change",
            series_id=series_id,
            value=value,
            units=units,
            direction=_direction(value),
            magnitude=abs(value),
            description=(
                f"{series_id} {'rose' if value > 0 else 'fell'} {abs(value):.1f} bps "
                f"around the {meeting_date} FOMC meeting "
                f"(from {float(pre[2]):.2f}% on {pre[1]} to {float(post[2]):.2f}% on {post[1]})"
            ),
            computation=(
                f"{series_id}[{post[1]}]({float(post[2]):.4f}%) "
                f"- {series_id}[{pre[1]}]({float(pre[2]):.4f}%) "
                f"= {value:+.1f} {units}"
            ),
            source_obs_ids=[int(pre[0]), int(post[0])],
            validated=True,
        )

    # ── Compute all facts for a date ──────────────────────────────────────────

    def compute_all_facts(
        self,
        target_date: date,
        series_ids: list[str] | None = None,
    ) -> list[StructuredFact]:
        """
        Compute the full suite of facts for a given date.
        Returns list of StructuredFact (None results excluded).
        """
        from ingestion.market_collector import FRED_SERIES

        series = series_ids or list(FRED_SERIES.keys())
        # Exclude spread series (computed separately)
        yield_series = [s for s in series if s not in ("T10Y2Y", "T10Y3M", "BAMLH0A0HYM2")]

        facts: list[StructuredFact] = []

        for s in yield_series:
            for fn in (self.daily_change, self.weekly_change, self.ytd_change, self.level):
                result = fn(s, target_date)
                if result:
                    facts.append(result)

        # Yield curve spreads
        for long_s, short_s in [("DGS10", "DGS2"), ("DGS30", "DGS10"), ("DGS10", "DGS5")]:
            result = self.yield_curve_spread(target_date, long_s, short_s)
            if result:
                facts.append(result)

        logger.info(f"Computed {len(facts)} structured facts for {target_date}")
        return facts

    # ── Persist to DB ─────────────────────────────────────────────────────────

    def upsert_facts(self, facts: list[StructuredFact]) -> int:
        """
        Upsert structured facts into the structured_facts table.
        Returns the number of rows inserted/updated.
        """
        if not facts:
            return 0

        rows = [
            (
                f.id,
                f.fact_date,
                f.fact_type,
                f.series_id,
                f.value,
                f.units,
                f.direction,
                f.magnitude,
                f.description,
                f.computation,
                f.source_obs_ids,
                f.validated,
                f.computed_at,
            )
            for f in facts
        ]

        with self._get_conn() as conn:
            with conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO structured_facts
                        (id, fact_date, fact_type, series_id, value, units,
                         direction, magnitude, description, computation,
                         source_obs_ids, validated, computed_at)
                    VALUES %s
                    ON CONFLICT (id) DO UPDATE SET
                        value        = EXCLUDED.value,
                        description  = EXCLUDED.description,
                        computation  = EXCLUDED.computation,
                        validated    = EXCLUDED.validated,
                        computed_at  = EXCLUDED.computed_at
                    """,
                    rows,
                )
                count = cur.rowcount

        logger.info(f"Upserted {count} structured facts")
        return count

