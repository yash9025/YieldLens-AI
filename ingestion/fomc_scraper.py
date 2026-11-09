"""
YieldLens AI — FOMC Document Scraper
Downloads FOMC statements, minutes, press conference transcripts, and SEPs
from the Federal Reserve website. Stores full text with source URLs and
publication datetimes for complete provenance.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings

DocType = Literal["STATEMENT", "MINUTES", "PRESSER", "SEP"]


@dataclass
class FedDocumentRecord:
    """A downloaded Federal Reserve document with provenance metadata."""

    meeting_date: date
    doc_type: DocType
    source_url: str
    pub_datetime: datetime | None
    raw_text: str
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "meeting_date": self.meeting_date,
            "doc_type": self.doc_type,
            "source_url": self.source_url,
            "pub_datetime": self.pub_datetime,
            "raw_text": self.raw_text,
            "fetched_at": self.fetched_at,
        }


class FOMCScraper:
    """
    Scrapes Federal Reserve FOMC documents.

    Politeness:
      - Respects settings.fed_scraper_delay_seconds between requests
      - Uses retry with exponential backoff
      - Identifies itself in the User-Agent header

    Coverage:
      - FOMC calendar page (all years)
      - Statements (press releases)
      - Minutes
      - Press conference transcripts
      - Summary of Economic Projections (SEP)
    """

    _HEADERS = {
        "User-Agent": (
            "YieldLens-AI-Research-Bot/1.0 "
            "(academic research; github.com/yash9025/YieldLens-AI)"
        )
    }

    # ── URL patterns for different document types ─────────────────────────────
    _STATEMENT_PATTERNS = [
        r"/newsevents/pressreleases/monetary\d{8}[a-z]?.htm",
        r"/monetarypolicy/files/monetary\d{8}[a-z]?.pdf",
    ]
    _MINUTES_PATTERNS = [
        r"/monetarypolicy/fomcminutes\d{8}.htm",
    ]
    _PRESSER_PATTERNS = [
        r"/monetarypolicy/fomcpresconf\d{8}.htm",
    ]

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(self._HEADERS)
        self._delay = settings.fed_scraper_delay_seconds
        logger.info(
            f"FOMCScraper initialised (delay={self._delay}s, "
            f"base={settings.fed_base_url})"
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _sleep(self) -> None:
        time.sleep(self._delay)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get(self, url: str) -> requests.Response:
        """HTTP GET with retry and polite delay."""
        self._sleep()
        resp = self._session.get(url, timeout=30)
        resp.raise_for_status()
        return resp

    def _extract_text(self, html: str, url: str) -> str:
        """Strip HTML tags and normalise whitespace from a Fed webpage."""
        soup = BeautifulSoup(html, "lxml")
        # Remove nav / header / footer noise
        for tag in soup.select("nav, header, footer, script, style, .skip-to-main"):
            tag.decompose()
        # Fed pages typically put content in .col-xs-12.col-sm-8 or #content
        content = (
            soup.select_one("#content")
            or soup.select_one(".col-xs-12.col-sm-8")
            or soup.body
        )
        text = content.get_text(separator="\n") if content else soup.get_text(separator="\n")
        # Normalise whitespace
        lines = [ln.strip() for ln in text.splitlines()]
        return "\n".join(ln for ln in lines if ln)

    def _parse_pub_date(self, soup: BeautifulSoup) -> datetime | None:
        """
        Try to extract the publication datetime from a Fed page's metadata.
        Returns UTC datetime or None.
        """
        # <meta property="article:published_time" content="...">
        meta = soup.find("meta", property="article:published_time")
        if meta and meta.get("content"):
            try:
                return datetime.fromisoformat(meta["content"]).astimezone(timezone.utc)
            except ValueError:
                pass
        # Fallback: look for "Release Date: Month DD, YYYY" text
        date_pattern = re.compile(
            r"(?:release|publication)\s+date[:\s]+(\w+ \d{1,2},?\s+\d{4})", re.IGNORECASE
        )
        text = soup.get_text()
        m = date_pattern.search(text)
        if m:
            try:
                return datetime.strptime(m.group(1).strip(","), "%B %d %Y").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                pass
        return None

    # ── FOMC Calendar ─────────────────────────────────────────────────────────

    def fetch_calendar_links(self) -> list[dict]:
        """
        Parse the FOMC calendar page and return a list of meeting entries.

        Each entry:
          {
            "meeting_date": date,
            "statement_url": str | None,
            "minutes_url": str | None,
            "presser_url": str | None,
            "sep_url": str | None,
          }
        """
        logger.info(f"Fetching FOMC calendar: {settings.fomc_calendar_url}")
        resp = self._get(settings.fomc_calendar_url)
        soup = BeautifulSoup(resp.text, "lxml")

        entries: list[dict] = []

        # The Fed calendar page uses a consistent pattern:
        # each meeting block has a date header and links to documents.
        # We parse all anchor tags and classify by URL pattern.
        all_links = {
            a["href"]: a.get_text(strip=True)
            for a in soup.find_all("a", href=True)
        }

        # Group links by meeting date extracted from URL
        meeting_map: dict[str, dict] = {}

        for href, text in all_links.items():
            href_lower = href.lower()
            abs_url = urljoin(settings.fed_base_url, href)

            # Extract 8-digit date from URL
            date_match = re.search(r"(\d{8})", href)
            if not date_match:
                continue
            raw_date = date_match.group(1)

            try:
                meeting_date = datetime.strptime(raw_date, "%Y%m%d").date()
            except ValueError:
                continue

            key = raw_date
            if key not in meeting_map:
                meeting_map[key] = {
                    "meeting_date": meeting_date,
                    "statement_url": None,
                    "minutes_url": None,
                    "presser_url": None,
                    "sep_url": None,
                }

            # Classify
            if "monetary" in href_lower and "pressrelease" in href_lower:
                meeting_map[key]["statement_url"] = abs_url
            elif "fomcminutes" in href_lower:
                meeting_map[key]["minutes_url"] = abs_url
            elif "fomcpresconf" in href_lower:
                meeting_map[key]["presser_url"] = abs_url
            elif "sep" in href_lower or "mpr" in href_lower:
                meeting_map[key]["sep_url"] = abs_url
            elif "monetary" in href_lower and "a.htm" in href_lower:
                # Statement pattern: monetary20240131a.htm
                meeting_map[key]["statement_url"] = abs_url

        entries = list(meeting_map.values())
        entries.sort(key=lambda e: e["meeting_date"])
        logger.info(f"Found {len(entries)} FOMC meeting entries in calendar")
        return entries

    # ── Individual document downloaders ───────────────────────────────────────

    def _download_doc(
        self,
        url: str,
        meeting_date: date,
        doc_type: DocType,
    ) -> FedDocumentRecord | None:
        """Download a single Fed document and return a record."""
        try:
            resp = self._get(url)
        except Exception as exc:
            logger.warning(f"  ✗ Failed to download {doc_type} {url}: {exc}")
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        pub_datetime = self._parse_pub_date(soup)
        raw_text = self._extract_text(resp.text, url)

        if len(raw_text.strip()) < 100:
            logger.warning(f"  ✗ Too little text extracted from {url} ({len(raw_text)} chars)")
            return None

        logger.info(
            f"  ✓ {doc_type} {meeting_date} — {len(raw_text):,} chars from {url}"
        )
        return FedDocumentRecord(
            meeting_date=meeting_date,
            doc_type=doc_type,
            source_url=url,
            pub_datetime=pub_datetime,
            raw_text=raw_text,
        )

    def download_statement(self, url: str, meeting_date: date) -> FedDocumentRecord | None:
        return self._download_doc(url, meeting_date, "STATEMENT")

    def download_minutes(self, url: str, meeting_date: date) -> FedDocumentRecord | None:
        return self._download_doc(url, meeting_date, "MINUTES")

    def download_presser(self, url: str, meeting_date: date) -> FedDocumentRecord | None:
        return self._download_doc(url, meeting_date, "PRESSER")

    # ── Full pipeline ─────────────────────────────────────────────────────────

    def scrape_all(
        self,
        doc_types: list[DocType] | None = None,
        start_year: int = 2000,
        end_year: int | None = None,
    ) -> list[FedDocumentRecord]:
        """
        Download all FOMC documents within the date range.

        Args:
            doc_types: Which types to download. Defaults to ["STATEMENT", "MINUTES"].
            start_year: Inclusive start year.
            end_year: Inclusive end year. Defaults to current year.

        Returns:
            List of FedDocumentRecord objects.
        """
        if doc_types is None:
            doc_types = ["STATEMENT", "MINUTES"]

        end = end_year or date.today().year
        calendar = self.fetch_calendar_links()

        # Filter by year range
        calendar = [
            e for e in calendar
            if start_year <= e["meeting_date"].year <= end
        ]
        logger.info(
            f"Scraping {len(calendar)} meetings ({start_year}–{end}), "
            f"doc_types={doc_types}"
        )

        records: list[FedDocumentRecord] = []

        for entry in calendar:
            meeting_date: date = entry["meeting_date"]

            if "STATEMENT" in doc_types and entry["statement_url"]:
                rec = self.download_statement(entry["statement_url"], meeting_date)
                if rec:
                    records.append(rec)

            if "MINUTES" in doc_types and entry["minutes_url"]:
                rec = self.download_minutes(entry["minutes_url"], meeting_date)
                if rec:
                    records.append(rec)

            if "PRESSER" in doc_types and entry["presser_url"]:
                rec = self.download_presser(entry["presser_url"], meeting_date)
                if rec:
                    records.append(rec)

        logger.info(f"Scraping complete. Downloaded {len(records)} documents.")
        return records

