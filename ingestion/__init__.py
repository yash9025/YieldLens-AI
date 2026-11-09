"""ingestion package"""
from ingestion.market_collector import MarketCollector, MarketObservationRecord, FRED_SERIES
from ingestion.fomc_scraper import FOMCScraper, FedDocumentRecord
from ingestion.pipeline import ingest_market_data, ingest_fed_documents

__all__ = [
    "MarketCollector",
    "MarketObservationRecord",
    "FRED_SERIES",
    "FOMCScraper",
    "FedDocumentRecord",
    "ingest_market_data",
    "ingest_fed_documents",
]

