import csv
import sqlite3

from scripts.run_pipeline import run_pipeline


def test_run_pipeline_fixture_mode_produces_data_and_database_artifacts(tmp_path):
    run_pipeline(mode="fixture", data_dir=tmp_path / "data", output_dir=tmp_path / "output")

    expected_data = [
        "raw_terms.csv",
        "cleaned_terms.csv",
        "category_excluded_terms.csv",
        "review_required_terms.csv",
        "scrape_failures.csv",
    ]
    expected_output = [
        "stock_dictionary.sqlite",
        "schema.postgres.sql",
        "seed_terms.csv",
        "seed_terms.sql",
    ]
    for filename in expected_data:
        assert (tmp_path / "data" / filename).exists()
    for filename in expected_output:
        assert (tmp_path / "output" / filename).exists()

    with (tmp_path / "data" / "cleaned_terms.csv").open(encoding="utf-8", newline="") as f:
        cleaned = list(csv.DictReader(f))
    assert cleaned
    assert set(cleaned[0]) == {"term", "aliases", "category", "definition", "source_name", "source_url"}

    with sqlite3.connect(tmp_path / "output" / "stock_dictionary.sqlite") as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM stock_terms").fetchone()[0]
        invalid_aliases = conn.execute("SELECT COUNT(*) FROM stock_terms WHERE NOT json_valid(aliases)").fetchone()[0]
    assert row_count == len(cleaned)
    assert invalid_aliases == 0


def test_run_pipeline_can_apply_llm_definition_rewriter(tmp_path):
    def fake_rewriter(term):
        if term.term == "PER":
            return term.model_copy(update={"definition": "LLM으로 정제된 PER 설명입니다."})
        return term

    run_pipeline(
        mode="fixture",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        definition_rewriter=fake_rewriter,
    )

    with (tmp_path / "data" / "cleaned_terms.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    per = next(row for row in rows if row["term"] == "PER")
    assert per["definition"] == "LLM으로 정제된 PER 설명입니다."


def test_run_pipeline_existing_mode_reuses_raw_terms_csv(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    (data_dir / "raw_terms.csv").write_text(
        "term,raw_definition,source_name,source_url,collected_at\n"
        "PER,주가를 주당순이익으로 나눈 투자지표입니다.,KB증권 금융용어사전,https://example.com/per,2026-05-12T12:00:00+09:00\n",
        encoding="utf-8",
    )

    run_pipeline(mode="existing", data_dir=data_dir, output_dir=output_dir)

    with (data_dir / "cleaned_terms.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [row["term"] for row in rows] == ["PER"]
    assert (output_dir / "seed_terms.sql").exists()


def test_run_pipeline_limit_applies_after_preprocessing(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    (data_dir / "raw_terms.csv").write_text(
        "term,raw_definition,source_name,source_url,collected_at\n"
        "PER,주가를 주당순이익으로 나눈 투자지표입니다.,KB증권 금융용어사전,https://example.com/per,2026-05-12T12:00:00+09:00\n"
        "PBR,주가를 주당순자산으로 나눈 투자지표입니다.,KB증권 금융용어사전,https://example.com/pbr,2026-05-12T12:00:00+09:00\n",
        encoding="utf-8",
    )

    run_pipeline(mode="existing", data_dir=data_dir, output_dir=output_dir, limit=1)

    with (data_dir / "cleaned_terms.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1


def test_run_pipeline_category_gate_excludes_misc_before_database_outputs(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    (data_dir / "raw_terms.csv").write_text(
        "term,raw_definition,source_name,source_url,collected_at\n"
        "PER,주가를 주당순이익으로 나눈 투자지표입니다.,KB증권 금융용어사전,https://example.com/per,2026-05-12T12:00:00+09:00\n"
        "정체불명,일반 사무 절차에 대한 설명입니다.,KB증권 금융용어사전,https://example.com/misc,2026-05-12T12:00:00+09:00\n",
        encoding="utf-8",
    )

    run_pipeline(mode="existing", data_dir=data_dir, output_dir=output_dir)

    with (data_dir / "cleaned_terms.csv").open(encoding="utf-8", newline="") as f:
        cleaned = list(csv.DictReader(f))
    with (data_dir / "category_excluded_terms.csv").open(encoding="utf-8", newline="") as f:
        excluded = list(csv.DictReader(f))

    assert [row["term"] for row in cleaned] == ["PER"]
    assert [row["term"] for row in excluded] == ["정체불명"]
    assert excluded[0]["reason"] == "category_gate_excluded"

    with sqlite3.connect(output_dir / "stock_dictionary.sqlite") as conn:
        row_count = conn.execute("SELECT COUNT(*) FROM stock_terms").fetchone()[0]
    assert row_count == 1
