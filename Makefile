# =============================================================
# AyurKosha — Makefile
# =============================================================

.PHONY: install setup ingest serve eval eval-retrieval eval-generation test clean

# ── Setup ──────────────────────────────────────────────────
install:
	pip install -r requirements.txt
	python -c "import nltk; nltk.download('punkt')"

setup: install
	cp -n .env.example .env || true
	@echo "✅ Setup complete. Edit .env with your API keys."

# ── Data ───────────────────────────────────────────────────
synonyms:
	python scripts/build_synonyms.py

catalog:
	python scripts/catalog_data.py

ingest:
	python scripts/run_ingestion.py

seed:
	python scripts/seed_data.py

# ── Server ─────────────────────────────────────────────────
serve:
	uvicorn api.main:app --reload --port 8000

serve-prod:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

# ── Evaluation ─────────────────────────────────────────────
eval:
	python scripts/run_eval.py --dataset data/eval/eval_dataset.json \
	                           --output data/eval/eval_results/

eval-retrieval:
	python scripts/run_eval.py --retrieval-only

eval-generation:
	python scripts/run_eval.py --generation-only

# ── Testing ────────────────────────────────────────────────
test:
	pytest tests/ -v

test-tokenizer:
	pytest tests/test_tokenizer.py -v

# ── Cleanup ────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
