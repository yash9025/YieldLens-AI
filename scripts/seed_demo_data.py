"""
YieldLens AI — Demo Data Seeder
Populates PostgreSQL database with realistic sample market observations,
FOMC documents, structured facts, and verified briefs for immediate offline evaluation.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
import psycopg2
import psycopg2.extras
from loguru import logger

from config import settings

SAMPLE_OBSERVATIONS = [
    # 2022-03-15 (baseline day before liftoff)
    (date(2022, 3, 15), "DFF", 0.08, "percent", "https://fred.stlouisfed.org/series/DFF", "FRED"),
    (date(2022, 3, 15), "DGS2", 1.85, "percent", "https://fred.stlouisfed.org/series/DGS2", "FRED"),
    (date(2022, 3, 15), "DGS5", 2.10, "percent", "https://fred.stlouisfed.org/series/DGS5", "FRED"),
    (date(2022, 3, 15), "DGS10", 2.15, "percent", "https://fred.stlouisfed.org/series/DGS10", "FRED"),
    (date(2022, 3, 15), "DGS30", 2.49, "percent", "https://fred.stlouisfed.org/series/DGS30", "FRED"),
    (date(2022, 3, 15), "T10Y2Y", 0.30, "percent", "https://fred.stlouisfed.org/series/T10Y2Y", "FRED"),

    # 2022-03-16 (liftoff meeting day)
    (date(2022, 3, 16), "DFF", 0.33, "percent", "https://fred.stlouisfed.org/series/DFF", "FRED"),
    (date(2022, 3, 16), "DGS2", 1.94, "percent", "https://fred.stlouisfed.org/series/DGS2", "FRED"),
    (date(2022, 3, 16), "DGS5", 2.14, "percent", "https://fred.stlouisfed.org/series/DGS5", "FRED"),
    (date(2022, 3, 16), "DGS10", 2.19, "percent", "https://fred.stlouisfed.org/series/DGS10", "FRED"),
    (date(2022, 3, 16), "DGS30", 2.46, "percent", "https://fred.stlouisfed.org/series/DGS30", "FRED"),
    (date(2022, 3, 16), "T10Y2Y", 0.25, "percent", "https://fred.stlouisfed.org/series/T10Y2Y", "FRED"),
]

SAMPLE_DOCS = [
    (
        date(2022, 3, 16),
        "STATEMENT",
        "https://www.federalreserve.gov/newsevents/pressreleases/monetary20220316a.htm",
        datetime(2022, 3, 16, 18, 0, 0, tzinfo=timezone.utc),
        (
            "The Federal Open Market Committee decided to raise the target range for the federal funds rate "
            "to 1/4 to 1/2 percent and anticipates that ongoing increases in the target range will be appropriate. "
            "In addition, the Committee expects to begin reducing its holdings of Treasury securities and agency "
            "debt and agency mortgage-backed securities at a coming meeting. Inflation remains elevated, reflecting "
            "supply and demand imbalances related to the pandemic, higher energy prices, and broader price pressures. "
            "The invasion of Ukraine by Russia is causing tremendous human and economic hardship."
        ),
    )
]


def seed_database():
    """Insert demo observations and documents."""
    conn = psycopg2.connect(settings.database_url_sync)
    try:
        with conn:
            with conn.cursor() as cur:
                # 1. Observations
                logger.info(f"Seeding {len(SAMPLE_OBSERVATIONS)} sample market observations...")
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO market_observations (obs_date, series_id, value, units, source_url, provider)
                    VALUES %s
                    ON CONFLICT (obs_date, series_id, provider) DO NOTHING
                    """,
                    SAMPLE_OBSERVATIONS,
                )

                # 2. Documents
                logger.info(f"Seeding {len(SAMPLE_DOCS)} sample Fed documents...")
                psycopg2.extras.execute_values(
                    cur,
                    """
                    INSERT INTO fed_documents (meeting_date, doc_type, source_url, pub_datetime, raw_text)
                    VALUES %s
                    ON CONFLICT (source_url) DO NOTHING
                    """,
                    SAMPLE_DOCS,
                )

        logger.info("Database seeding successfully completed.")
    except Exception as e:
        logger.error(f"Seeding error: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    seed_database()
