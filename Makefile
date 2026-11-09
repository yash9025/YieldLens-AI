.PHONY: help install test lint run-api run-ui docker-up docker-down seed eval train-baseline train-lora

help:
	@echo "YieldLens AI — Development Commands:"
	@echo "  make install        Install backend and dev dependencies"
	@echo "  make test           Run pytest unit tests"
	@echo "  make run-api        Start FastAPI server with auto-reload"
	@echo "  make run-ui         Start React/Vite development server"
	@echo "  make build-ui       Compile React frontend into dist/"
	@echo "  make docker-up      Start PostgreSQL (pgvector) and MLflow containers"
	@echo "  make docker-down    Stop all containers"
	@echo "  make seed           Populate database with sample demo data"
	@echo "  make train-baseline Train TF-IDF + Logistic Regression policy classifier"
	@echo "  make train-lora     Train LoRA fine-tuned DistilBERT classifier"
	@echo "  make eval           Run chronological held-out evaluation across 3 modes"

install:
	pip install -e ".[dev]"
	cd frontend && npm install

test:
	pytest tests/unit/ -v

run-api:
	python -m api.cli serve --reload

run-ui:
	cd frontend && npm run dev

build-ui:
	cd frontend && npm run build

docker-up:
	docker-compose up -d postgres mlflow

docker-down:
	docker-compose down

seed:
	python -m scripts.seed_demo_data

train-baseline:
	python -m models.train_classifier

train-lora:
	python -m models.lora_finetune

eval:
	python -m evaluation.run_eval --modes TEMPLATE,LLM_RAG,HYBRID
