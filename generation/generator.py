"""
YieldLens AI — Brief Generator
Generates evidence-grounded daily market briefs in three modes:
  TEMPLATE : Pure deterministic template, zero LLM.
  LLM_RAG  : LLM with retrieved evidence only (no structured facts injected).
  HYBRID   : Structured facts + retrieved evidence → LLM. (Primary mode)

Every sentence in HYBRID/LLM_RAG output carries:
  - fact_ids[]  : structured_facts.id references
  - chunk_ids[] : document_chunks.id references
  - uncertainty : explicit flag if the evidence doesn't establish causation
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Literal

import psycopg2
import psycopg2.extras
from loguru import logger
from openai import OpenAI

from config import settings
from processing.fact_calculator import StructuredFact
from retrieval.retriever import RetrievedChunk

BriefMode = Literal["TEMPLATE", "LLM_RAG", "HYBRID"]

# ── Prompt templates ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a rigorous financial analyst producing evidence-grounded market briefs.

STRICT RULES — follow every rule or the brief is invalid:
1. Every NUMERICAL CLAIM must be sourced from a STRUCTURED_FACT (cite its fact_id).
2. Every CONTEXTUAL CLAIM (policy language, announcements) must cite a DOCUMENT_CHUNK (cite chunk_id).
3. Use TEMPORAL language (e.g., "yields rose after the announcement"), NOT CAUSAL language
   (do NOT write "the announcement caused yields to rise") UNLESS the cited document itself
   uses causal language.
4. If evidence is insufficient to support a claim, mark it:
   [UNCERTAIN: <brief reason>]
5. Never invent numbers. Never round numbers differently from the structured facts.
6. Output ONLY valid JSON — no prose before or after the JSON block.

OUTPUT FORMAT (JSON):
{
  "date": "YYYY-MM-DD",
  "summary": "One sentence overview of the day",
  "sentences": [
    {
      "id": "s1",
      "text": "Full sentence text.",
      "section": "market_moves|fed_context|uncertainty_flags",
      "fact_ids": ["fact_id_1"],
      "chunk_ids": [123, 456],
      "uncertainty": null
    }
  ]
}
"""

HYBRID_USER_TEMPLATE = """
Generate a market brief for {date}.

=== STRUCTURED FACTS (use these for ALL numbers) ===
{facts_block}

=== RETRIEVED EVIDENCE (use these for context and policy language) ===
{chunks_block}

Generate a brief with:
- 3-5 sentences in market_moves (use exact numbers from structured facts)
- 2-4 sentences in fed_context (cite document chunks)
- 1-2 sentences in uncertainty_flags (where causation cannot be established)
"""

LLM_RAG_USER_TEMPLATE = """
Generate a market brief for {date}.

=== RETRIEVED EVIDENCE ===
{chunks_block}

Generate a brief with market_moves, fed_context, and uncertainty_flags sections.
Only use numbers that appear verbatim in the retrieved evidence above.
"""


@dataclass
class BriefSentence:
    id: str
    text: str
    section: str
    fact_ids: list[str] = field(default_factory=list)
    chunk_ids: list[int] = field(default_factory=list)
    uncertainty: str | None = None


@dataclass
class Brief:
    brief_date: date
    mode: BriefMode
    summary: str
    sentences: list[BriefSentence]
    model_version: str | None = None
    tokens_used: int | None = None
    latency_ms: int | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "date": self.brief_date.isoformat(),
            "mode": self.mode,
            "summary": self.summary,
            "sentences": [
                {
                    "id": s.id,
                    "text": s.text,
                    "section": s.section,
                    "fact_ids": s.fact_ids,
                    "chunk_ids": s.chunk_ids,
                    "uncertainty": s.uncertainty,
                }
                for s in self.sentences
            ],
        }


class BriefGenerator:
    """
    Generates grounded market briefs in TEMPLATE, LLM_RAG, or HYBRID mode.
    """

    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._conn_str = settings.database_url_sync

    def _get_conn(self):
        return psycopg2.connect(self._conn_str)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _facts_block(self, facts: list[StructuredFact]) -> str:
        """Format structured facts for injection into the prompt."""
        lines = []
        for f in facts:
            lines.append(
                f"[FACT:{f.id}] {f.description} "
                f"(value={f.value}, units={f.units}, validated={f.validated})"
            )
        return "\n".join(lines) if lines else "No structured facts available."

    def _chunks_block(self, chunks: list[RetrievedChunk]) -> str:
        """Format retrieved chunks for injection into the prompt."""
        lines = []
        for c in chunks:
            pub = c.pub_datetime.strftime("%Y-%m-%d") if c.pub_datetime else "unknown"
            lines.append(
                f"[CHUNK:{c.chunk_id}] ({c.doc_type}, meeting={c.meeting_date}, pub={pub})\n"
                f"{c.chunk_text[:600]}"
            )
        return "\n\n".join(lines) if lines else "No retrieved evidence available."

    def _call_llm(self, system: str, user: str) -> tuple[str, int]:
        """Call OpenAI and return (content, tokens_used)."""
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,  # low temp for factual reliability
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or "{}"
        tokens = resp.usage.total_tokens if resp.usage else 0
        return content, tokens

    def _parse_llm_output(self, raw: str, mode: BriefMode, brief_date: date) -> Brief:
        """Parse LLM JSON output into a Brief object."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON: {e}. Using fallback.")
            data = {"date": brief_date.isoformat(), "summary": "Parse error", "sentences": []}

        sentences = [
            BriefSentence(
                id=s.get("id", f"s{i}"),
                text=s.get("text", ""),
                section=s.get("section", "market_moves"),
                fact_ids=s.get("fact_ids", []),
                chunk_ids=[int(x) for x in s.get("chunk_ids", []) if str(x).isdigit()],
                uncertainty=s.get("uncertainty"),
            )
            for i, s in enumerate(data.get("sentences", []))
        ]

        return Brief(
            brief_date=brief_date,
            mode=mode,
            summary=data.get("summary", ""),
            sentences=sentences,
            model_version=self._model,
        )

    # ── Generation modes ──────────────────────────────────────────────────────

    def generate_template(self, brief_date: date, facts: list[StructuredFact]) -> Brief:
        """
        TEMPLATE mode: Pure deterministic — no LLM.
        Fills structured facts into a fixed template.
        """
        sentences: list[BriefSentence] = []
        s_idx = 0

        # Sort: daily changes first, then spreads
        daily = [f for f in facts if f.fact_type == "daily_change"]
        spreads = [f for f in facts if f.fact_type == "spread"]
        levels = [f for f in facts if f.fact_type == "level"]

        for fact in daily[:5]:
            s_idx += 1
            sentences.append(
                BriefSentence(
                    id=f"s{s_idx}",
                    text=fact.description,
                    section="market_moves",
                    fact_ids=[fact.id],
                    chunk_ids=[],
                    uncertainty=None,
                )
            )

        for fact in spreads[:2]:
            s_idx += 1
            sentences.append(
                BriefSentence(
                    id=f"s{s_idx}",
                    text=fact.description,
                    section="market_moves",
                    fact_ids=[fact.id],
                    chunk_ids=[],
                    uncertainty=None,
                )
            )

        s_idx += 1
        sentences.append(
            BriefSentence(
                id=f"s{s_idx}",
                text=(
                    "Causal attribution between market movements and specific announcements "
                    "has not been established by this template-based brief."
                ),
                section="uncertainty_flags",
                fact_ids=[],
                chunk_ids=[],
                uncertainty="Template mode: no document retrieval performed.",
            )
        )

        summary_parts = [f.description for f in daily[:2]]
        summary = "; ".join(summary_parts) if summary_parts else f"Market brief for {brief_date}"

        return Brief(
            brief_date=brief_date,
            mode="TEMPLATE",
            summary=summary,
            sentences=sentences,
            model_version="template-v1",
        )

    def generate_llm_rag(
        self,
        brief_date: date,
        chunks: list[RetrievedChunk],
    ) -> Brief:
        """
        LLM_RAG mode: LLM with retrieved evidence only. No structured facts injected.
        """
        t0 = time.perf_counter()
        user = LLM_RAG_USER_TEMPLATE.format(
            date=brief_date.isoformat(),
            chunks_block=self._chunks_block(chunks),
        )
        raw, tokens = self._call_llm(SYSTEM_PROMPT, user)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        brief = self._parse_llm_output(raw, "LLM_RAG", brief_date)
        brief.tokens_used = tokens
        brief.latency_ms = latency_ms
        return brief

    def generate_hybrid(
        self,
        brief_date: date,
        facts: list[StructuredFact],
        chunks: list[RetrievedChunk],
    ) -> Brief:
        """
        HYBRID mode (Primary): Structured facts + retrieved evidence → LLM.
        This is the main production mode.
        """
        t0 = time.perf_counter()
        user = HYBRID_USER_TEMPLATE.format(
            date=brief_date.isoformat(),
            facts_block=self._facts_block(facts),
            chunks_block=self._chunks_block(chunks),
        )
        raw, tokens = self._call_llm(SYSTEM_PROMPT, user)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        brief = self._parse_llm_output(raw, "HYBRID", brief_date)
        brief.tokens_used = tokens
        brief.latency_ms = latency_ms
        return brief

    # ── Persistence ───────────────────────────────────────────────────────────

    def save_brief(self, brief: Brief) -> int:
        """Upsert a brief to the briefs table. Returns the brief's DB id."""
        conn = self._get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO briefs
                            (brief_date, mode, content_json, model_version,
                             tokens_used, latency_ms, generated_at)
                        VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)
                        ON CONFLICT (brief_date, mode) DO UPDATE SET
                            content_json  = EXCLUDED.content_json,
                            model_version = EXCLUDED.model_version,
                            tokens_used   = EXCLUDED.tokens_used,
                            latency_ms    = EXCLUDED.latency_ms,
                            generated_at  = EXCLUDED.generated_at
                        RETURNING id
                        """,
                        (
                            brief.brief_date,
                            brief.mode,
                            json.dumps(brief.to_dict()),
                            brief.model_version,
                            brief.tokens_used,
                            brief.latency_ms,
                            brief.generated_at,
                        ),
                    )
                    row = cur.fetchone()
                    brief_id = row[0] if row else -1
        finally:
            conn.close()

        logger.info(f"Brief saved: id={brief_id}, date={brief.brief_date}, mode={brief.mode}")
        return brief_id

