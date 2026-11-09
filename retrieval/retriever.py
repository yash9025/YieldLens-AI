"""
YieldLens AI — Retrieval Engine
Two-stage retrieval: candidate fetch (BM25 + dense) → cross-encoder rerank.
Enforces temporal constraints: only documents published BEFORE the brief date.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import psycopg2
import psycopg2.extras
from loguru import logger
try:
    from sentence_transformers import CrossEncoder, SentenceTransformer
except ImportError:
    CrossEncoder = None
    SentenceTransformer = None

from config import settings


@dataclass
class RetrievedChunk:
    """A document chunk returned by the retriever with provenance."""

    chunk_id: int
    doc_id: int
    chunk_index: int
    chunk_text: str
    meeting_date: date
    doc_type: str
    pub_datetime: datetime | None
    source_url: str
    # Scores
    bm25_score: float = 0.0
    dense_score: float = 0.0
    rerank_score: float = 0.0
    final_rank: int = 0


class Retriever:
    """
    Evidence retriever for YieldLens briefs.

    Stage 1 — Candidate fetch (k=50):
      - Keyword search using PostgreSQL trigram similarity (pg_trgm)
      - Dense embedding search using pgvector cosine similarity
      - Union and deduplicate candidates

    Stage 2 — Reranking (top-k=10):
      - cross-encoder/ms-marco-MiniLM-L-6-v2
      - Returns ranked chunks with scores

    Temporal constraint:
      - Only chunks from documents with pub_datetime < brief_date are returned.
      - This prevents look-ahead contamination in evaluation.
    """

    def __init__(
        self,
        embed_model: str | None = None,
        rerank_model: str | None = None,
    ) -> None:
        embed = embed_model or settings.embedding_model
        rerank = rerank_model or settings.reranker_model

        logger.info(f"Loading embedding model: {embed}")
        self._embed_model = SentenceTransformer(embed)

        logger.info(f"Loading cross-encoder: {rerank}")
        self._reranker = CrossEncoder(rerank, max_length=512)

        logger.info("Retriever ready")

    def _get_conn(self):
        return psycopg2.connect(settings.database_url_sync)

    # ── Stage 1a: Keyword search (BM25 / trigram) ─────────────────────────────

    def _keyword_search(
        self,
        query: str,
        brief_date: date,
        k: int,
    ) -> list[RetrievedChunk]:
        """
        Trigram-based keyword search with temporal constraint.
        Uses pg_trgm similarity score.
        """
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        dc.id AS chunk_id,
                        dc.doc_id,
                        dc.chunk_index,
                        dc.chunk_text,
                        dc.meeting_date,
                        dc.doc_type,
                        dc.pub_datetime,
                        dc.source_url,
                        similarity(dc.chunk_text, %s) AS bm25_score
                    FROM document_chunks dc
                    WHERE (dc.pub_datetime IS NULL OR dc.pub_datetime::date < %s)
                      AND dc.meeting_date < %s
                      AND similarity(dc.chunk_text, %s) > 0.05
                    ORDER BY bm25_score DESC
                    LIMIT %s
                    """,
                    (query, brief_date, brief_date, query, k),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        return [
            RetrievedChunk(
                chunk_id=r["chunk_id"],
                doc_id=r["doc_id"],
                chunk_index=r["chunk_index"],
                chunk_text=r["chunk_text"],
                meeting_date=r["meeting_date"],
                doc_type=r["doc_type"],
                pub_datetime=r["pub_datetime"],
                source_url=r["source_url"],
                bm25_score=float(r["bm25_score"]),
            )
            for r in rows
        ]

    # ── Stage 1b: Dense embedding search ─────────────────────────────────────

    def _dense_search(
        self,
        query: str,
        brief_date: date,
        k: int,
    ) -> list[RetrievedChunk]:
        """
        pgvector cosine similarity search with temporal constraint.
        """
        query_emb = self._embed_model.encode(
            [query], normalize_embeddings=True
        )[0].tolist()

        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        dc.id AS chunk_id,
                        dc.doc_id,
                        dc.chunk_index,
                        dc.chunk_text,
                        dc.meeting_date,
                        dc.doc_type,
                        dc.pub_datetime,
                        dc.source_url,
                        1 - (dc.embedding <=> %s::vector) AS dense_score
                    FROM document_chunks dc
                    WHERE (dc.pub_datetime IS NULL OR dc.pub_datetime::date < %s)
                      AND dc.meeting_date < %s
                      AND dc.embedding IS NOT NULL
                    ORDER BY dc.embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_emb, brief_date, brief_date, query_emb, k),
                )
                rows = cur.fetchall()
        finally:
            conn.close()

        return [
            RetrievedChunk(
                chunk_id=r["chunk_id"],
                doc_id=r["doc_id"],
                chunk_index=r["chunk_index"],
                chunk_text=r["chunk_text"],
                meeting_date=r["meeting_date"],
                doc_type=r["doc_type"],
                pub_datetime=r["pub_datetime"],
                source_url=r["source_url"],
                dense_score=float(r["dense_score"]),
            )
            for r in rows
        ]

    # ── Stage 2: Reranking ────────────────────────────────────────────────────

    def _rerank(
        self,
        query: str,
        candidates: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        """
        Score candidates with a cross-encoder and return top_k sorted by score.
        """
        if not candidates:
            return []

        pairs = [[query, c.chunk_text] for c in candidates]
        scores = self._reranker.predict(pairs, show_progress_bar=False)

        for chunk, score in zip(candidates, scores):
            chunk.rerank_score = float(score)

        ranked = sorted(candidates, key=lambda c: c.rerank_score, reverse=True)[:top_k]
        for i, chunk in enumerate(ranked):
            chunk.final_rank = i + 1

        return ranked

    # ── Public interface ──────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        brief_date: date,
        candidate_k: int | None = None,
        final_k: int | None = None,
    ) -> list[RetrievedChunk]:
        """
        Full two-stage retrieval for a single query.

        Args:
            query: Natural language query (fact description or free-form question).
            brief_date: The date of the brief. Only docs published BEFORE this date
                        are returned (temporal integrity constraint).
            candidate_k: Number of candidates to fetch in stage 1.
            final_k: Number of results to return after reranking.

        Returns:
            List of RetrievedChunk sorted by rerank_score descending.
        """
        ck = candidate_k or settings.retrieval_candidate_k
        fk = final_k or settings.retrieval_final_k

        logger.debug(f"Retrieval: q='{query[:60]}…', date={brief_date}, k={ck}→{fk}")

        # Stage 1: get candidates from both sources
        kw_results = self._keyword_search(query, brief_date, k=ck // 2)
        dense_results = self._dense_search(query, brief_date, k=ck // 2)

        # Merge and deduplicate by chunk_id
        seen: set[int] = set()
        candidates: list[RetrievedChunk] = []
        for chunk in kw_results + dense_results:
            if chunk.chunk_id not in seen:
                seen.add(chunk.chunk_id)
                candidates.append(chunk)

        logger.debug(
            f"  Stage 1: {len(kw_results)} keyword + {len(dense_results)} dense "
            f"→ {len(candidates)} unique candidates"
        )

        if not candidates:
            logger.warning(f"No candidates found for query: '{query[:60]}'")
            return []

        # Stage 2: rerank
        ranked = self._rerank(query, candidates, top_k=fk)
        logger.debug(f"  Stage 2: top-{len(ranked)} after reranking")

        return ranked

    def retrieve_for_facts(
        self,
        facts: list[dict],
        brief_date: date,
        final_k_per_fact: int = 5,
    ) -> dict[str, list[RetrievedChunk]]:
        """
        Retrieve evidence for each structured fact.

        Args:
            facts: List of structured fact dicts (must have 'id' and 'description').
            brief_date: Date of the brief.
            final_k_per_fact: Chunks to return per fact.

        Returns:
            Dict mapping fact_id → list of ranked chunks.
        """
        evidence_map: dict[str, list[RetrievedChunk]] = {}
        for fact in facts:
            fact_id = fact["id"]
            query = fact.get("description", fact_id)
            chunks = self.retrieve(query, brief_date, final_k=final_k_per_fact)
            evidence_map[fact_id] = chunks
            logger.debug(f"  {fact_id}: {len(chunks)} evidence chunks")
        return evidence_map

