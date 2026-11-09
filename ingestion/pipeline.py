"""
YieldLens AI — Ingestion Orchestrator
Runs the full ingestion pipeline: market data + Fed documents → PostgreSQL.
Logs ingestion statistics to MLflow.
"""
from __future__ import annotations

import mlflow
import psycopg2
import psycopg2.extras
from datetime import date
from loguru import logger

from config import settings
from ingestion.market_collector import MarketCollector, FRED_SERIES
from ingestion.fomc_scraper import FOMCScraper, FedDocumentRecord


def _get_conn():
    """Return a psycopg2 connection (sync, used for bulk inserts)."""
    return psycopg2.connect(settings.database_url_sync)


def ingest_market_data(
    start_date: str = "2000-01-01",
    end_date: str | None = None,
    run_name: str = "market-ingestion",
) -> None:
    """
    Collect all configured FRED series and upsert into market_observations table.
    Logs ingestion counts to MLflow.
    """
    end = end_date or date.today().isoformat()

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({"start_date": start_date, "end_date": end, "source": "FRED"})

        collector = MarketCollector()
        all_records = collector.fetch_all_series(start_date=start_date, end_date=end)

        total_inserted = 0
        total_skipped = 0

        conn = _get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    for series_id, records in all_records.items():
                        insert_count = 0
                        skip_count = 0
                        for rec in records:
                            try:
                                cur.execute(
                                    """
                                    INSERT INTO market_observations
                                        (obs_date, series_id, value, units, source_url, provider, fetched_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                    ON CONFLICT (obs_date, series_id, provider) DO NOTHING
                                    """,
                                    (
                                        rec.obs_date,
                                        rec.series_id,
                                        rec.value,
                                        rec.units,
                                        rec.source_url,
                                        rec.provider,
                                        rec.fetched_at,
                                    ),
                                )
                                if cur.rowcount:
                                    insert_count += 1
                                else:
                                    skip_count += 1
                            except Exception as e:
                                logger.warning(f"Skip {series_id} {rec.obs_date}: {e}")
                                skip_count += 1

                        total_inserted += insert_count
                        total_skipped += skip_count
                        mlflow.log_metric(f"{series_id}_inserted", insert_count)
                        logger.info(
                            f"{series_id}: +{insert_count} new, {skip_count} already exist"
                        )
        finally:
            conn.close()

        mlflow.log_metrics(
            {"total_inserted": total_inserted, "total_skipped": total_skipped}
        )
        logger.info(
            f"Market ingestion complete: {total_inserted} new rows, {total_skipped} skipped"
        )


def ingest_fed_documents(
    start_year: int = 2000,
    end_year: int | None = None,
    doc_types: list[str] | None = None,
    run_name: str = "fed-doc-ingestion",
) -> None:
    """
    Scrape FOMC documents and upsert into fed_documents table.
    Logs ingestion counts to MLflow.
    """
    if doc_types is None:
        doc_types = ["STATEMENT", "MINUTES"]

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params(
            {
                "start_year": start_year,
                "end_year": end_year or date.today().year,
                "doc_types": ",".join(doc_types),
            }
        )

        scraper = FOMCScraper()
        records: list[FedDocumentRecord] = scraper.scrape_all(
            doc_types=doc_types,
            start_year=start_year,
            end_year=end_year,
        )

        inserted = 0
        skipped = 0

        conn = _get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    for rec in records:
                        try:
                            cur.execute(
                                """
                                INSERT INTO fed_documents
                                    (meeting_date, doc_type, source_url, pub_datetime, raw_text, fetched_at)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                ON CONFLICT (source_url) DO NOTHING
                                """,
                                (
                                    rec.meeting_date,
                                    rec.doc_type,
                                    rec.source_url,
                                    rec.pub_datetime,
                                    rec.raw_text,
                                    rec.fetched_at,
                                ),
                            )
                            if cur.rowcount:
                                inserted += 1
                            else:
                                skipped += 1
                        except Exception as e:
                            logger.warning(
                                f"Skip {rec.doc_type} {rec.meeting_date}: {e}"
                            )
                            skipped += 1
        finally:
            conn.close()

        mlflow.log_metrics({"docs_inserted": inserted, "docs_skipped": skipped})
        logger.info(
            f"Fed document ingestion complete: {inserted} new, {skipped} already exist"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="YieldLens AI Ingestion Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Market parser
    market_p = subparsers.add_parser("market", help="Ingest FRED market data")
    market_p.add_argument("--start", default="2000-01-01", help="Start date YYYY-MM-DD")
    market_p.add_argument("--end", default=None, help="End date YYYY-MM-DD")

    # Fed parser
    fed_p = subparsers.add_parser("fed", help="Ingest FOMC documents")
    fed_p.add_argument("--start-year", type=int, default=2000, help="Start year")
    fed_p.add_argument("--end-year", type=int, default=None, help="End year")
    fed_p.add_argument("--types", default="STATEMENT,MINUTES", help="Comma-sep doc types")

    args = parser.parse_args()

    if args.command == "market":
        ingest_market_data(start_date=args.start, end_date=args.end)
    elif args.command == "fed":
        ingest_fed_documents(
            start_year=args.start_year,
            end_year=args.end_year,
            doc_types=args.types.split(","),
        )

