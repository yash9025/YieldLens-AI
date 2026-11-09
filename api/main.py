"""
YieldLens AI — FastAPI Application
Main entry point for the API server.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from loguru import logger
from pydantic import BaseModel

from config import settings
from database import AsyncSessionLocal, engine
from models.orm_models import Base

# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("YieldLens API starting up…")
    # Create tables if they don't exist (alembic handles migrations in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables verified")
    yield
    logger.info("YieldLens API shutting down")
    await engine.dispose()


app = FastAPI(
    title="YieldLens AI API",
    description="Evidence-Grounded Market Commentary Engine for US Rates & Fed Policy",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Key auth ──────────────────────────────────────────────────────────────

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)):
    if api_key != settings.api_secret_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class BriefGenerateRequest(BaseModel):
    date: date
    mode: str = "HYBRID"  # TEMPLATE | LLM_RAG | HYBRID


class BriefResponse(BaseModel):
    id: int
    brief_date: date
    mode: str
    content_json: dict
    model_version: str | None
    tokens_used: int | None
    latency_ms: int | None


class FactsResponse(BaseModel):
    date: date
    facts: list[dict]


class EvidenceResponse(BaseModel):
    sentence_id: str
    sentence_text: str
    facts: list[dict]
    chunks: list[dict]
    verification: dict | None


class HealthResponse(BaseModel):
    status: str
    version: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health():
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/briefs/generate", tags=["Briefs"])
async def generate_brief(
    req: BriefGenerateRequest,
    _: str = Depends(verify_api_key),
):
    """
    Trigger brief generation for a specific date and mode.
    Returns the generated brief with full sentence-level provenance.
    """
    import asyncpg
    from generation.generator import BriefGenerator
    from processing.fact_calculator import FactCalculator
    from retrieval.retriever import Retriever
    from verification.verifier import Verifier

    brief_date = req.date
    mode = req.mode.upper()

    if mode not in ("TEMPLATE", "LLM_RAG", "HYBRID"):
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")

    logger.info(f"Generating {mode} brief for {brief_date}")

    calc = FactCalculator()
    facts = calc.compute_all_facts(brief_date)

    retriever = Retriever()
    query = f"Federal Reserve monetary policy Treasury yields {brief_date}"
    chunks = retriever.retrieve(query, brief_date)

    gen = BriefGenerator()
    if mode == "TEMPLATE":
        brief = gen.generate_template(brief_date, facts)
    elif mode == "LLM_RAG":
        brief = gen.generate_llm_rag(brief_date, chunks)
    else:
        brief = gen.generate_hybrid(brief_date, facts, chunks)

    brief_id = gen.save_brief(brief)

    # Verify
    verifier = Verifier()
    ver_results = verifier.verify_brief(brief.to_dict(), brief_date)
    verifier.save_verification_results(brief_id, ver_results)

    return {
        "brief_id": brief_id,
        "date": brief_date.isoformat(),
        "mode": mode,
        "summary": brief.summary,
        "sentences": brief.to_dict()["sentences"],
        "tokens_used": brief.tokens_used,
        "latency_ms": brief.latency_ms,
    }


@app.get("/briefs/{brief_date}", tags=["Briefs"])
async def get_brief(
    brief_date: date,
    mode: str = Query(default="HYBRID"),
):
    """Fetch a stored brief for a given date and mode."""
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(settings.database_url_sync)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM briefs WHERE brief_date = %s AND mode = %s",
                (brief_date, mode.upper()),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No {mode} brief found for {brief_date}. Use POST /briefs/generate to create one.",
        )

    return dict(row)


@app.get("/briefs/{brief_date}/sentence/{sentence_id}/evidence", tags=["Evidence"])
async def get_sentence_evidence(brief_date: date, sentence_id: str, mode: str = "HYBRID"):
    """
    Fetch the supporting evidence (facts + document chunks) for a single sentence.
    This powers the clickable evidence pane in the frontend.
    """
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(settings.database_url_sync)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Get brief
            cur.execute(
                "SELECT id, content_json FROM briefs WHERE brief_date = %s AND mode = %s",
                (brief_date, mode.upper()),
            )
            brief_row = cur.fetchone()
            if not brief_row:
                raise HTTPException(status_code=404, detail="Brief not found")

            brief_id = brief_row["id"]
            content = brief_row["content_json"]
            sentence = next(
                (s for s in content.get("sentences", []) if s["id"] == sentence_id),
                None,
            )
            if not sentence:
                raise HTTPException(status_code=404, detail=f"Sentence {sentence_id} not found")

            # Fetch facts
            fact_ids = sentence.get("fact_ids", [])
            facts = []
            if fact_ids:
                cur.execute(
                    "SELECT * FROM structured_facts WHERE id = ANY(%s)", (fact_ids,)
                )
                facts = [dict(r) for r in cur.fetchall()]

            # Fetch chunks
            chunk_ids = [int(x) for x in sentence.get("chunk_ids", []) if str(x).isdigit()]
            chunks = []
            if chunk_ids:
                cur.execute(
                    "SELECT id, chunk_text, source_url, meeting_date, doc_type, pub_datetime "
                    "FROM document_chunks WHERE id = ANY(%s)",
                    (chunk_ids,),
                )
                chunks = [dict(r) for r in cur.fetchall()]

            # Fetch verification
            cur.execute(
                "SELECT * FROM verification_results WHERE brief_id = %s AND claim_id = %s",
                (brief_id, sentence_id),
            )
            ver_row = cur.fetchone()
            verification = dict(ver_row) if ver_row else None

    finally:
        conn.close()

    return EvidenceResponse(
        sentence_id=sentence_id,
        sentence_text=sentence["text"],
        facts=[{k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                for k, v in f.items()} for f in facts],
        chunks=[{k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v
                 for k, v in c.items()} for c in chunks],
        verification={k: str(v) if not isinstance(v, (str, int, float, bool, type(None), list)) else v
                      for k, v in verification.items()} if verification else None,
    )


@app.get("/briefs/{brief_date}/sentence/{sentence_id}/verification", tags=["Verification"])
async def get_sentence_verification(brief_date: date, sentence_id: str, mode: str = "HYBRID"):
    """Fetch the verification result for a single sentence."""
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(settings.database_url_sync)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT vr.* FROM verification_results vr
                JOIN briefs b ON b.id = vr.brief_id
                WHERE b.brief_date = %s AND b.mode = %s AND vr.claim_id = %s
                """,
                (brief_date, mode.upper(), sentence_id),
            )
            row = cur.fetchone()
    finally:
        conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Verification result not found")
    return dict(row)


@app.get("/facts/{fact_date}", tags=["Facts"])
async def get_facts(fact_date: date):
    """Get all structured facts computed for a given date."""
    import psycopg2
    import psycopg2.extras

    conn = psycopg2.connect(settings.database_url_sync)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM structured_facts WHERE fact_date = %s ORDER BY fact_type, series_id",
                (fact_date,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    return FactsResponse(
        date=fact_date,
        facts=[{k: str(v) if not isinstance(v, (str, int, float, bool, type(None), list)) else v
                for k, v in dict(r).items()} for r in rows],
    )


# ── Static UI Mounting ────────────────────────────────────────────────────────
from pathlib import Path
from fastapi.staticfiles import StaticFiles

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

