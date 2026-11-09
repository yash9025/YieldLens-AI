-- ============================================================
-- YieldLens AI  –  PostgreSQL Init Script
-- Run automatically by docker-compose on first startup
-- ============================================================

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- BM25-style trigram search

-- MLflow database (separate from main app)
CREATE DATABASE mlflow;

-- ============================================================
-- 1. Market Observations
--    One row per (date, series_id).  Source URL kept for provenance.
-- ============================================================
CREATE TABLE IF NOT EXISTS market_observations (
    id              BIGSERIAL PRIMARY KEY,
    obs_date        DATE        NOT NULL,
    series_id       VARCHAR(32) NOT NULL,          -- e.g. "DGS10", "DFF"
    value           NUMERIC(12, 6) NOT NULL,
    units           VARCHAR(32) NOT NULL,          -- "percent", "bps"
    source_url      TEXT        NOT NULL,
    provider        VARCHAR(16) NOT NULL,          -- "FRED" | "YAHOO"
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_obs UNIQUE (obs_date, series_id, provider)
);

CREATE INDEX idx_obs_date        ON market_observations (obs_date);
CREATE INDEX idx_obs_series      ON market_observations (series_id);
CREATE INDEX idx_obs_date_series ON market_observations (obs_date, series_id);

-- ============================================================
-- 2. Fed Documents
--    FOMC statements, minutes, press conferences, SEPs
-- ============================================================
CREATE TABLE IF NOT EXISTS fed_documents (
    id              BIGSERIAL PRIMARY KEY,
    meeting_date    DATE        NOT NULL,
    doc_type        VARCHAR(16) NOT NULL,          -- STATEMENT|MINUTES|PRESSER|SEP
    source_url      TEXT        NOT NULL UNIQUE,
    pub_datetime    TIMESTAMPTZ,                   -- NULL if unknown
    raw_text        TEXT        NOT NULL,
    char_count      INT         GENERATED ALWAYS AS (LENGTH(raw_text)) STORED,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_fed_meeting ON fed_documents (meeting_date);
CREATE INDEX idx_fed_type    ON fed_documents (doc_type);
CREATE INDEX idx_fed_pub     ON fed_documents (pub_datetime);

-- ============================================================
-- 3. Document Chunks
--    Chunked text with embeddings for vector search
-- ============================================================
CREATE TABLE IF NOT EXISTS document_chunks (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          BIGINT      NOT NULL REFERENCES fed_documents(id) ON DELETE CASCADE,
    chunk_index     INT         NOT NULL,
    chunk_text      TEXT        NOT NULL,
    token_count     INT,
    embedding       vector(384),                   -- MiniLM-L6-v2 dim
    -- Denormalised for fast filtering
    meeting_date    DATE        NOT NULL,
    doc_type        VARCHAR(16) NOT NULL,
    pub_datetime    TIMESTAMPTZ,
    source_url      TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_chunk UNIQUE (doc_id, chunk_index)
);

CREATE INDEX idx_chunk_doc      ON document_chunks (doc_id);
CREATE INDEX idx_chunk_meeting  ON document_chunks (meeting_date);
CREATE INDEX idx_chunk_pub      ON document_chunks (pub_datetime);
-- Vector index (IVFFlat — rebuild after bulk insert)
CREATE INDEX idx_chunk_embedding ON document_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
-- Trigram index for BM25-style keyword search
CREATE INDEX idx_chunk_trgm ON document_chunks USING GIN (chunk_text gin_trgm_ops);

-- ============================================================
-- 4. Structured Facts
--    Deterministically computed, fully sourced market facts
-- ============================================================
CREATE TABLE IF NOT EXISTS structured_facts (
    id              VARCHAR(128) PRIMARY KEY,       -- deterministic: "DGS10_daily_2024-01-31"
    fact_date       DATE        NOT NULL,
    fact_type       VARCHAR(32) NOT NULL,           -- "daily_change"|"weekly_change"|"ytd"|"spread"
    series_id       VARCHAR(32) NOT NULL,
    value           NUMERIC(12, 6) NOT NULL,
    units           VARCHAR(32) NOT NULL,           -- "bps" | "percent"
    direction       VARCHAR(8),                    -- "up" | "down" | "flat"
    magnitude       NUMERIC(12, 6),
    description     TEXT,
    computation     TEXT,                          -- human-readable formula
    source_obs_ids  BIGINT[]    NOT NULL,
    validated       BOOLEAN     NOT NULL DEFAULT FALSE,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_facts_date   ON structured_facts (fact_date);
CREATE INDEX idx_facts_series ON structured_facts (series_id);
CREATE INDEX idx_facts_type   ON structured_facts (fact_type);

-- ============================================================
-- 5. Briefs
--    Generated market briefs (all 3 modes stored)
-- ============================================================
CREATE TABLE IF NOT EXISTS briefs (
    id              BIGSERIAL PRIMARY KEY,
    brief_date      DATE        NOT NULL,
    mode            VARCHAR(16) NOT NULL,           -- TEMPLATE|LLM_RAG|HYBRID
    content_json    JSONB       NOT NULL,
    model_version   VARCHAR(64),
    tokens_used     INT,
    latency_ms      INT,
    generated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_brief UNIQUE (brief_date, mode)
);

CREATE INDEX idx_brief_date ON briefs (brief_date);
CREATE INDEX idx_brief_mode ON briefs (mode);

-- ============================================================
-- 6. Verification Results
--    Per-claim verification results for each brief
-- ============================================================
CREATE TABLE IF NOT EXISTS verification_results (
    id              BIGSERIAL PRIMARY KEY,
    brief_id        BIGINT      NOT NULL REFERENCES briefs(id) ON DELETE CASCADE,
    claim_id        VARCHAR(32) NOT NULL,           -- e.g. "s1", "s2"
    claim_text      TEXT        NOT NULL,
    verdict         VARCHAR(16) NOT NULL,           -- SUPPORTED|PARTIAL|UNSUPPORTED|UNCERTAIN
    issues          TEXT[]      DEFAULT '{}',
    evidence_ids    TEXT[]      DEFAULT '{}',
    confidence      NUMERIC(4,3),
    verified_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ver_brief   ON verification_results (brief_id);
CREATE INDEX idx_ver_verdict ON verification_results (verdict);

-- ============================================================
-- 7. Evidence Links
--    Links structured_facts / chunks to sentences in briefs
-- ============================================================
CREATE TABLE IF NOT EXISTS evidence_links (
    id              BIGSERIAL PRIMARY KEY,
    brief_id        BIGINT      NOT NULL REFERENCES briefs(id) ON DELETE CASCADE,
    sentence_id     VARCHAR(32) NOT NULL,
    link_type       VARCHAR(16) NOT NULL,           -- "fact" | "chunk"
    target_id       TEXT        NOT NULL,           -- fact.id or chunk.id
    relevance_score NUMERIC(6,4),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ev_brief    ON evidence_links (brief_id);
CREATE INDEX idx_ev_sentence ON evidence_links (sentence_id);

