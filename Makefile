.PHONY: test test-py test-ts eval ablations preference-alignment llm-eval llm-eval-live audit value-audit paper-tables clean clean-cache help

LLM_PROVIDER ?= deepseek
LLM_MODEL ?= deepseek-chat
LLM_BASE_URL ?= https://api.deepseek.com
LLM_API_KEY_ENV ?= DEEPSEEK_API_KEY

help:
	@echo "ASM Build & Experiment Targets"
	@echo ""
	@echo "  make test          Run all tests (Python + TypeScript)"
	@echo "  make test-py       Run Python scorer tests only"
	@echo "  make test-ts       Run TypeScript MCP server tests only"
	@echo "  make eval          Run A/B evaluation (Section 6.5)"
	@echo "  make ablations     Run ablation studies (Section 6.3a)"
	@echo "  make preference-alignment  Run natural-language preference evaluation (Section 6.6a)"
	@echo "  make llm-eval      LLM-as-selector dry-run (no API calls)"
	@echo "  make llm-eval-live LLM-as-selector with live LLM (override LLM_PROVIDER/LLM_MODEL/LLM_BASE_URL/LLM_API_KEY_ENV)"
	@echo "  make audit         Run MCP ecosystem audit (Section 2)"
	@echo "  make value-audit   Run expanded MCP registry/directory value metadata audit"
	@echo "  make paper-tables  Generate paper tables from experiment results"
	@echo "  make clean         Remove cache artifacts"
	@echo "  make clean-cache   Remove raw-doc cache (large)"
	@echo ""

# ---------------------------------------------------------------------------
# Test targets
# ---------------------------------------------------------------------------

test: test-py test-ts
	@echo "[OK] All tests passed."

test-py:
	python -m pytest scorer/test_scorer.py -v

test-ts:
	cd registry && npx tsx src/test_scorer.ts
	cd registry && npx tsx src/test_topsis.ts

# ---------------------------------------------------------------------------
# Experiment targets
# ---------------------------------------------------------------------------

eval:
	python experiments/ab_test.py
	python experiments/analyze.py

ablations:
	python experiments/ablation_experiments.py --seed 2024

preference-alignment:
	python experiments/preference_alignment.py --seed 2024

llm-eval:
	python experiments/expert_annotation/run_ranking_experiment.py \
	  --tasks-file experiments/expert_annotation/tasks_objective.yaml \
	  --dry-run

llm-eval-live:
	@if [ -z "$${$(LLM_API_KEY_ENV)}" ]; then \
		echo "Error: set $(LLM_API_KEY_ENV), or override LLM_API_KEY_ENV=<ENV_NAME>"; \
		exit 1; \
	fi
	python experiments/expert_annotation/run_ranking_experiment.py \
	  --tasks-file experiments/expert_annotation/tasks_objective.yaml \
	  --provider $(LLM_PROVIDER) \
	  --model $(LLM_MODEL) \
	  --base-url $(LLM_BASE_URL) \
	  --api-key-env $(LLM_API_KEY_ENV)

audit:
	python experiments/mcp_ecosystem_audit.py

value-audit:
	python experiments/mcp_value_metadata_audit.py --sample-size 600 --seed 2026

paper-tables:
	python experiments/ab_test.py
	python experiments/analyze.py
	python experiments/ablation_experiments.py --seed 2024
	python experiments/preference_alignment.py --seed 2024
	python experiments/mcp_value_metadata_audit.py --sample-size 600 --seed 2026
	python experiments/expert_annotation/run_ranking_experiment.py \
	  --tasks-file experiments/expert_annotation/tasks_objective.yaml \
	  --dry-run

# ---------------------------------------------------------------------------
# Clean targets
# ---------------------------------------------------------------------------

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name node_modules -path "*/registry/node_modules" -exec rm -rf {} + 2>/dev/null || true
	@echo "[OK] Cleaned build artifacts."

clean-cache:
	rm -rf experiments/expert_annotation/cache/raw_docs
	@echo "[OK] Removed raw-doc cache."
