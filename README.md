# 🏦 YieldLens AI

**Evidence-Grounded Market Commentary Engine for US Rates & Fed Policy**

> Every sentence in a YieldLens brief carries a source. Every number is validated against structured data. Every causal claim is flagged unless the evidence establishes it.

---

## Overview

YieldLens AI turns Federal Reserve announcements and Treasury market movements into concise, verifiable daily briefs. It is designed around one core principle: **factual reliability over fluency**.

```
Market Data (FRED) ──┐
                      ├──► Structured Facts ──┐
Fed Documents ────────┤                       ├──► Brief Generator ──► Verifier ──► API
(FOMC Statements)     └──► Evidence Retrieval ┘                              │
                                                                              └──► Frontend
                                                                                 (clickable evidence)
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Three generation modes** | TEMPLATE (pure deterministic), LLM_RAG (evidence-only), HYBRID (primary) |
| **Sentence-level provenance** | Every sentence carries `fact_ids[]` + `chunk_ids[]` |
| **Automated verification** | 7 checks per claim: numbers, units, dates, citations, causation |
| **Causation discipline** | "yields rose after the announcement" ≠ "announcement caused yields to rise" |
| **Evaluation framework** | 15-date held-out set, MLflow comparison across all 3 modes |
| **Clickable evidence pane** | React UI: click any sentence to see its supporting facts and documents |

---

## Quick Start

### Prerequisites
- Docker Desktop
- Python 3.11+
- FRED API key (free at [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html))
- OpenAI API key

### 1. Clone & configure
```bash
git clone https://github.com/yash9025/YieldLens-AI.git
cd YieldLens-AI
cp .env.example .env
# Edit .env — add FRED_API_KEY and OPENAI_API_KEY
```

### 2. Start infrastructure
```bash
docker-compose up -d postgres mlflow
# PostgreSQL on :5432, MLflow on :5001
```

### 3. Install Python dependencies
```bash
pip install -e ".[dev]"
python -m spacy download en_core_web_sm
```

### 4. Run data ingestion
```bash
# Phase 1: Ingest FRED market data (2020–present for quick start)
python -m ingestion.pipeline market --start 2020-01-01

# Ingest FOMC documents
python -m ingestion.pipeline fed --start-year 2020

# Phase 2: Embed documents
python -c "from processing.doc_processor import DocumentProcessor; DocumentProcessor().process_all_unembedded()"

# Compute structured facts for a specific date
python -c "
from processing.fact_calculator import FactCalculator
from datetime import date
calc = FactCalculator()
facts = calc.compute_all_facts(date(2024, 1, 31))
calc.upsert_facts(facts)
print(f'Computed {len(facts)} facts')
"
```

### 5. Generate a brief
```bash
# Start the API
uvicorn api.main:app --reload

# Generate a HYBRID brief
curl -X POST http://localhost:8000/briefs/generate \
  -H "X-API-Key: change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{"date": "2024-01-31", "mode": "HYBRID"}'
```

### 6. Run evaluation
```bash
python -m evaluation.run_eval --modes TEMPLATE,LLM_RAG,HYBRID --max-dates 5
```

### 7. View MLflow results
Open [http://localhost:5001](http://localhost:5001) for the experiment dashboard.

---

## Project Structure

```
YieldLens-AI/
├── ingestion/              # Phase 1: FRED + Fed document collection
│   ├── market_collector.py   # FRED API → MarketObservationRecord
│   ├── fomc_scraper.py       # Fed.gov scraper → FedDocumentRecord
│   └── pipeline.py           # Orchestrator with MLflow logging
│
├── processing/             # Phase 2: Facts + embeddings
│   ├── fact_calculator.py    # Deterministic market fact computation
│   └── doc_processor.py      # Chunking, signal extraction, embedding
│
├── models/                 # Phase 2: Policy classifier
│   ├── orm_models.py         # SQLAlchemy ORM models
│   └── policy_classifier.py  # Baseline (TF-IDF) + DistilBERT classifier
│
├── retrieval/              # Phase 3: Two-stage retrieval
│   └── retriever.py          # BM25 + dense → cross-encoder reranker
│
├── generation/             # Phase 4: Brief generation
│   └── generator.py          # TEMPLATE, LLM_RAG, HYBRID modes
│
├── verification/           # Phase 5: Automated fact-checking
│   └── verifier.py           # 7-check verifier, verdict schema
│
├── evaluation/             # Phase 6: Held-out eval framework
│   ├── held_out_set.json     # 15 historical dates (never used for training)
│   └── run_eval.py           # MLflow comparison across modes
│
├── api/                    # Phase 7: FastAPI backend
│   └── main.py               # REST endpoints with API key auth
│
├── frontend/               # Phase 7: React UI
│   └── src/components/
│
├── migrations/
│   └── init.sql            # PostgreSQL schema + pgvector setup
├── tests/
│   └── unit/               # Unit tests (mocked DB, no network required)
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── config.py               # Pydantic settings (all from .env)
```

---

## Evaluation Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| `supported_rate` | % sentences with valid citations | > 85% (HYBRID) |
| `unsupported_rate` | % sentences with no citation | < 10% (HYBRID) |
| `causation_flag_rate` | % sentences using ungrounded causal language | < 5% |
| `avg_fact_coverage` | % key facts mentioned in brief | > 80% |
| `latency_p50_ms` | Median brief generation time | < 5000 ms |
| `avg_tokens` | Avg LLM tokens per brief | Logged (cost tracking) |

---

## Evaluation Design Notes

> **Chronological split**: Training documents end at 2021-12-31. Evaluation dates are 2022-01-01 and later.
>
> **LLM contamination caveat**: A pretrained LLM may have memorised events from evaluation dates. We evaluate **grounding against the supplied evidence corpus**, not against the model's parametric knowledge.
>
> **Template mode** provides the gold standard for numerical accuracy — it cannot hallucinate numbers.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11+ |
| Database | PostgreSQL 16 + pgvector |
| ML / NLP | PyTorch, HuggingFace Transformers, sentence-transformers |
| Tracking | MLflow |
| Orchestration | LangChain (retrieval chains) |
| API | FastAPI + asyncpg |
| Frontend | React + TailwindCSS |
| Infrastructure | Docker Compose |
| Data | FRED API, Federal Reserve website, Yahoo Finance |

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Run tests: `pytest tests/unit/ -v`
4. Submit a PR with a clear description of what changed and why

---

## License

MIT License — see [LICENSE](LICENSE).

---

*YieldLens AI is a research project. It does not constitute financial advice.*

