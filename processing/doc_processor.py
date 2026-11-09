"""
YieldLens AI — Document Processor
Chunks Fed documents, extracts entities and policy events, generates embeddings.
Populates the document_chunks table with text + vector embeddings.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import psycopg2
import psycopg2.extras
from loguru import logger
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

from config import settings


# ── Policy-language patterns ──────────────────────────────────────────────────

HAWKISH_SIGNALS = [
    r"inflation\s+(?:remains\s+)?(?:risk|concern|elevated|persistent|high)",
    r"(?:raise|hike|increase)\s+(?:interest\s+)?rates?",
    r"above\s+(?:the\s+|our\s+)?(?:2[-\s]?percent|target)",
    r"tighten(?:ing)?\s+(?:monetary\s+)?policy",
    r"reducing\s+(?:the\s+)?balance\s+sheet",
    r"quantitative\s+tighten",
]

DOVISH_SIGNALS = [
    r"(?:support|support(?:ive)?)\s+(?:economic\s+)?(?:activity|growth|recovery)",
    r"(?:maximum\s+)?employment",
    r"below\s+(?:our\s+)?(?:2[-\s]?percent|target)",
    r"accommodative\s+(?:monetary\s+)?(?:policy|stance)",
    r"quantitative\s+eas(?:ing|e)",
    r"(?:asset\s+)?purchase\s+program",
    r"transitory",
]

FORWARD_GUIDANCE = [
    r"expect(?:s)?\s+to\s+(?:maintain|keep|hold)",
    r"data[\s-]dependent",
    r"patient",
    r"remain\s+(?:accommodative|restrictive)",
    r"until\s+(?:further|sufficient)",
    r"appropriate\s+to\s+(?:maintain|keep)",
]

RATE_CHANGE_PATTERN = re.compile(
    r"(?:raise|lower|reduce|increase|cut|maintain|hold)\s+(?:the\s+)?(?:target\s+)?(?:federal\s+funds\s+)?rate\s+(?:by\s+)?(\d+\.?\d*)\s*(?:percentage\s+point|basis\s+point|percent)",
    re.IGNORECASE,
)

NUMBER_PATTERN = re.compile(
    r"(\d+\.?\d*)\s*(percent|basis\s+point|trillion|billion|million|%|bps?)",
    re.IGNORECASE,
)


@dataclass
class ChunkRecord:
    """A single document chunk ready for DB insertion."""

    doc_id: int
    chunk_index: int
    chunk_text: str
    token_count: int
    embedding: list[float]
    meeting_date: date
    doc_type: str
    pub_datetime: datetime | None
    source_url: str
    # Extracted signals (stored separately for classifier training)
    hawkish_signals: list[str]
    dovish_signals: list[str]
    has_rate_change: bool
    has_forward_guidance: bool
    numbers_found: list[str]


class DocumentProcessor:
    """
    Processes Fed documents into searchable, embedded chunks.

    Pipeline per document:
    1. Sentence-aware chunking (400 tokens, 50-token overlap)
    2. Entity / signal extraction (regex-based, no LLM)
    3. Embedding generation (sentence-transformers)
    4. Upsert to document_chunks table
    """

    def __init__(self, model_name: str | None = None) -> None:
        model = model_name or settings.embedding_model
        logger.info(f"Loading embedding model: {model}")
        if SentenceTransformer is None:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Install with: pip install sentence-transformers"
            )
        self._embed_model = SentenceTransformer(model)
        logger.info("DocumentProcessor ready")

    # ── Chunking ──────────────────────────────────────────────────────────────

    def _split_sentences(self, text: str) -> list[str]:
        """Simple sentence splitter using punctuation (no spaCy dependency required)."""
        # Split on sentence-ending punctuation followed by whitespace + capital
        sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)
        return [s.strip() for s in sentences if s.strip()]

    def chunk_text(
        self,
        text: str,
        max_tokens: int = 400,
        overlap_tokens: int = 50,
        avg_chars_per_token: int = 4,
    ) -> list[str]:
        """
        Split text into overlapping chunks based on approximate token count.
        Uses sentence boundaries to avoid mid-sentence cuts.
        """
        max_chars = max_tokens * avg_chars_per_token
        overlap_chars = overlap_tokens * avg_chars_per_token

        sentences = self._split_sentences(text)
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for sent in sentences:
            sent_len = len(sent)
            if current_len + sent_len > max_chars and current:
                chunks.append(" ".join(current))
                # Keep overlap
                overlap_sents: list[str] = []
                overlap_len = 0
                for s in reversed(current):
                    if overlap_len + len(s) <= overlap_chars:
                        overlap_sents.insert(0, s)
                        overlap_len += len(s)
                    else:
                        break
                current = overlap_sents
                current_len = overlap_len

            current.append(sent)
            current_len += sent_len

        if current:
            chunks.append(" ".join(current))

        return chunks

    # ── Signal extraction ─────────────────────────────────────────────────────

    def _extract_signals(self, text: str) -> dict:
        """Extract policy signals and numbers from chunk text."""
        text_lower = text.lower()

        hawkish = [p for p in HAWKISH_SIGNALS if re.search(p, text_lower)]
        dovish = [p for p in DOVISH_SIGNALS if re.search(p, text_lower)]
        guidance = any(re.search(p, text_lower) for p in FORWARD_GUIDANCE)
        rate_change = bool(RATE_CHANGE_PATTERN.search(text))
        numbers = [m.group(0) for m in NUMBER_PATTERN.finditer(text)]

        return {
            "hawkish_signals": hawkish,
            "dovish_signals": dovish,
            "has_forward_guidance": guidance,
            "has_rate_change": rate_change,
            "numbers_found": numbers[:20],  # cap at 20
        }

    # ── Embedding ─────────────────────────────────────────────────────────────

    def embed_chunks(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Generate embeddings for a list of texts."""
        embeddings = self._embed_model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=len(texts) > 50,
            normalize_embeddings=True,  # cosine similarity ready
        )
        return embeddings.tolist()

    # ── Full document processing ───────────────────────────────────────────────

    def process_document(
        self,
        doc_id: int,
        raw_text: str,
        meeting_date: date,
        doc_type: str,
        pub_datetime: datetime | None,
        source_url: str,
    ) -> list[ChunkRecord]:
        """
        Process a single Fed document into chunk records with embeddings.
        """
        chunks_text = self.chunk_text(raw_text)
        if not chunks_text:
            logger.warning(f"No chunks produced for doc_id={doc_id}")
            return []

        logger.info(f"  doc_id={doc_id}: {len(chunks_text)} chunks → embedding…")
        embeddings = self.embed_chunks(chunks_text)

        records: list[ChunkRecord] = []
        for idx, (text, emb) in enumerate(zip(chunks_text, embeddings)):
            signals = self._extract_signals(text)
            token_count = len(text) // 4  # rough estimate
            records.append(
                ChunkRecord(
                    doc_id=doc_id,
                    chunk_index=idx,
                    chunk_text=text,
                    token_count=token_count,
                    embedding=emb,
                    meeting_date=meeting_date,
                    doc_type=doc_type,
                    pub_datetime=pub_datetime,
                    source_url=source_url,
                    **signals,
                )
            )

        return records

    # ── Persist to DB ─────────────────────────────────────────────────────────

    def upsert_chunks(self, chunks: list[ChunkRecord]) -> int:
        """Upsert chunk records into document_chunks table."""
        if not chunks:
            return 0

        rows = [
            (
                c.doc_id,
                c.chunk_index,
                c.chunk_text,
                c.token_count,
                c.embedding,
                c.meeting_date,
                c.doc_type,
                c.pub_datetime,
                c.source_url,
            )
            for c in chunks
        ]

        conn = psycopg2.connect(settings.database_url_sync)
        try:
            with conn:
                with conn.cursor() as cur:
                    psycopg2.extras.execute_values(
                        cur,
                        """
                        INSERT INTO document_chunks
                            (doc_id, chunk_index, chunk_text, token_count, embedding,
                             meeting_date, doc_type, pub_datetime, source_url)
                        VALUES %s
                        ON CONFLICT (doc_id, chunk_index) DO UPDATE SET
                            chunk_text  = EXCLUDED.chunk_text,
                            token_count = EXCLUDED.token_count,
                            embedding   = EXCLUDED.embedding
                        """,
                        rows,
                        template="(%s,%s,%s,%s,%s::vector,%s,%s,%s,%s)",
                    )
                    return cur.rowcount
        finally:
            conn.close()

    def process_all_unembedded(self, batch_size: int = 50) -> int:
        """
        Find all fed_documents without any chunks and process them.
        Returns total chunks created.
        """
        conn = psycopg2.connect(settings.database_url_sync)
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT fd.id, fd.raw_text, fd.meeting_date, fd.doc_type,
                           fd.pub_datetime, fd.source_url
                    FROM fed_documents fd
                    WHERE fd.id NOT IN (SELECT DISTINCT doc_id FROM document_chunks)
                    ORDER BY fd.meeting_date ASC
                    LIMIT %s
                    """,
                    (batch_size,),
                )
                docs = cur.fetchall()
        finally:
            conn.close()

        if not docs:
            logger.info("No unembedded documents found")
            return 0

        logger.info(f"Processing {len(docs)} unembedded documents…")
        total_chunks = 0

        for doc in docs:
            chunks = self.process_document(
                doc_id=doc["id"],
                raw_text=doc["raw_text"],
                meeting_date=doc["meeting_date"],
                doc_type=doc["doc_type"],
                pub_datetime=doc["pub_datetime"],
                source_url=doc["source_url"],
            )
            inserted = self.upsert_chunks(chunks)
            total_chunks += inserted
            logger.info(
                f"  doc_id={doc['id']} ({doc['doc_type']} {doc['meeting_date']}): "
                f"{inserted} chunks upserted"
            )

        return total_chunks

