# Stock Dictionary Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the PRD-defined stock dictionary pipeline that scrapes reference terms, produces intermediate CSVs, runs deterministic and LLM-assisted cleanup, builds SQLite, and exports Neon/PostgreSQL deliverables.

**Architecture:** Use small Python scripts over shared library modules. Keep final DB schema flat, keep review and scrape failures as CSV logs, and make each output reproducible from `data/cleaned_terms.csv`.

**Tech Stack:** Python 3.12 via `uv`, Scrapling 0.4.8, LangChain 1.2.18, LangGraph 1.2.0, LangChain-Core 1.4.0, langchain-google-genai 4.2.2, Pydantic 2.13.4, pytest, SQLite.

---

### Task 1: Project Skeleton And Contracts

**Files:**
- Create: `pyproject.toml`
- Create: `stock_dictionary/__init__.py`
- Create: `stock_dictionary/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for row contracts**

Create tests that prove aliases are always valid JSON arrays, cleaned rows require source fields, and review rows preserve reasons.

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL because `stock_dictionary.models` does not exist.

- [ ] **Step 3: Implement Pydantic models**

Implement `RawTerm`, `CleanedTerm`, `ReviewRequiredTerm`, `ScrapeFailure`, and helper methods for CSV serialization.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS.

### Task 2: Deterministic Preprocessing

**Files:**
- Create: `stock_dictionary/preprocess.py`
- Create: `tests/test_preprocess.py`
- Create: `scripts/preprocess_terms.py`

- [ ] **Step 1: Write failing tests for aliases, categories, and duplicate grouping**

Cover PER/주가수익비율 alias grouping, empty alias as `[]`, category fallback to `기타`, and representative term selection.

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run pytest tests/test_preprocess.py -v`
Expected: FAIL because preprocessing functions do not exist.

- [ ] **Step 3: Implement deterministic preprocessing**

Add normalization, representative-term selection, base category assignment, and CSV read/write helpers.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `uv run pytest tests/test_preprocess.py -v`
Expected: PASS.

### Task 3: SQLite And PostgreSQL Export

**Files:**
- Create: `stock_dictionary/exporters.py`
- Create: `tests/test_exporters.py`
- Create: `scripts/build_sqlite.py`
- Create: `scripts/export_postgres.py`

- [ ] **Step 1: Write failing tests for SQLite schema and export artifacts**

Verify SQLite has `stock_terms`, `aliases` passes `json_valid`, PostgreSQL schema uses `JSONB`, seed CSV has headers, and seed SQL quotes values safely.

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run pytest tests/test_exporters.py -v`
Expected: FAIL because exporters do not exist.

- [ ] **Step 3: Implement exporters**

Generate `output/stock_dictionary.sqlite`, `output/schema.postgres.sql`, `output/seed_terms.csv`, `output/seed_terms.sql`, `output/upload_to_neon.md`, and `output/migration_to_neon.md`.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `uv run pytest tests/test_exporters.py -v`
Expected: PASS.

### Task 4: LLM Prompt Files And Pipeline Shell

**Files:**
- Create: `prompts/definition_rewrite.md`
- Create: `prompts/duplicate_alias_judgment.md`
- Create: `prompts/category_assignment.md`
- Create: `prompts/source_conflict_resolution.md`
- Create: `stock_dictionary/llm_pipeline.py`
- Create: `tests/test_llm_pipeline.py`

- [ ] **Step 1: Write failing tests with a fake LLM client**

Verify JSON parsing, Pydantic validation, two retries, and `review_required_terms.csv` fallback behavior without calling Gemini.

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run pytest tests/test_llm_pipeline.py -v`
Expected: FAIL because LLM pipeline code does not exist.

- [ ] **Step 3: Implement LLM pipeline wrapper**

Use `init_chat_model`, `JsonOutputParser`, Pydantic schemas, env vars `GEMINI_API_KEY`, `MAIN_MODEL`, `FALLBACK_MODEL`, and LangSmith-compatible tracing envs.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `uv run pytest tests/test_llm_pipeline.py -v`
Expected: PASS without network model calls.

### Task 5: Scrapling Scraper

**Files:**
- Create: `stock_dictionary/scrapers.py`
- Create: `tests/test_scrapers.py`
- Create: `scripts/scrape_terms.py`

- [ ] **Step 1: Write failing tests for HTML extraction fixtures**

Use static HTML snippets to prove the scraper extracts term/definition pairs and records scrape failures.

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run pytest tests/test_scrapers.py -v`
Expected: FAIL because scraper helpers do not exist.

- [ ] **Step 3: Implement Scrapling-based fetch and generic extraction helpers**

Use Scrapling for fetching, preserve `raw_definition`, and write `data/raw_terms.csv` plus `data/scrape_failures.csv`.

- [ ] **Step 4: Run tests to verify GREEN**

Run: `uv run pytest tests/test_scrapers.py -v`
Expected: PASS.

### Task 6: End-To-End CLI And Verification

**Files:**
- Create: `scripts/run_pipeline.py`
- Create: `tests/test_pipeline_smoke.py`
- Generate: `data/raw_terms.csv`
- Generate: `data/cleaned_terms.csv`
- Generate: `data/review_required_terms.csv`
- Generate: `data/scrape_failures.csv`
- Generate: `output/stock_dictionary.sqlite`
- Generate: `output/schema.postgres.sql`
- Generate: `output/seed_terms.csv`
- Generate: `output/seed_terms.sql`
- Generate: `output/upload_to_neon.md`
- Generate: `output/migration_to_neon.md`

- [ ] **Step 1: Write failing smoke test**

Use a small fixture dataset to run the full local pipeline without network or Gemini calls and verify all files are produced.

- [ ] **Step 2: Run smoke test to verify RED**

Run: `uv run pytest tests/test_pipeline_smoke.py -v`
Expected: FAIL because `scripts/run_pipeline.py` does not exist.

- [ ] **Step 3: Implement CLI orchestration**

Wire scrape, preprocess, SQLite build, and PostgreSQL export into one command with fixture mode and live mode.

- [ ] **Step 4: Run all tests**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 5: Run live pipeline or fixture fallback**

Run: `uv run python scripts/run_pipeline.py --mode live`
Expected: produces PRD deliverables. If live sources fail, failures are logged and fixture smoke outputs still validate artifact generation.

### Self-Review

- Spec coverage: plan covers scripts, prompts, data CSVs, SQLite, PostgreSQL schema/seed, upload/migration docs, LLM JSON validation, LangSmith logging hooks, and scrape failure logs.
- No placeholders: each task has explicit files and commands.
- Type consistency: final DB rows use `term`, `aliases`, `category`, `definition`, `source_name`, `source_url`; raw rows use `term`, `raw_definition`, `source_name`, `source_url`, `collected_at`.
