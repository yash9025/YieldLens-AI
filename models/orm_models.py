"""
YieldLens AI — ORM Models
All SQLAlchemy models mapping to the PostgreSQL schema defined in migrations/init.sql
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from database import Base


class MarketObservation(Base):
    __tablename__ = "market_observations"
    __table_args__ = (UniqueConstraint("obs_date", "series_id", "provider", name="uq_obs"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    obs_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    series_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    units: Mapped[str] = mapped_column(String(32), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class FedDocument(Base):
    __tablename__ = "fed_documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    pub_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("doc_id", "chunk_index", name="uq_chunk"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doc_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("fed_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[Optional[int]] = mapped_column(Integer)
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(384))
    # Denormalised columns for fast filtering
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    doc_type: Mapped[str] = mapped_column(String(16), nullable=False)
    pub_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    document: Mapped[FedDocument] = relationship("FedDocument", back_populates="chunks")


class StructuredFact(Base):
    __tablename__ = "structured_facts"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    fact_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fact_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    series_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    units: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[Optional[str]] = mapped_column(String(8))
    magnitude: Mapped[Optional[float]] = mapped_column(Numeric(12, 6))
    description: Mapped[Optional[str]] = mapped_column(Text)
    computation: Mapped[Optional[str]] = mapped_column(Text)
    source_obs_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), nullable=False)
    validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Brief(Base):
    __tablename__ = "briefs"
    __table_args__ = (UniqueConstraint("brief_date", "mode", name="uq_brief"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    brief_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    model_version: Mapped[Optional[str]] = mapped_column(String(64))
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    verification_results: Mapped[list[VerificationResult]] = relationship(
        "VerificationResult", back_populates="brief", cascade="all, delete-orphan"
    )
    evidence_links: Mapped[list[EvidenceLink]] = relationship(
        "EvidenceLink", back_populates="brief", cascade="all, delete-orphan"
    )


class VerificationResult(Base):
    __tablename__ = "verification_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    brief_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("briefs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    claim_id: Mapped[str] = mapped_column(String(32), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    verdict: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    issues: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    evidence_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3))
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    brief: Mapped[Brief] = relationship("Brief", back_populates="verification_results")


class EvidenceLink(Base):
    __tablename__ = "evidence_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    brief_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("briefs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sentence_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    relevance_score: Mapped[Optional[float]] = mapped_column(Numeric(6, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    brief: Mapped[Brief] = relationship("Brief", back_populates="evidence_links")

