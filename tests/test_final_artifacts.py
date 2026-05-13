import csv
import sqlite3

from scripts.build_final_artifacts import build_final_artifacts


def test_build_final_artifacts_applies_source_conflict_resolution_and_exports(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    samples_dir = data_dir / "llm_samples"
    samples_dir.mkdir(parents=True)

    (samples_dir / "definition_rewrite_results.csv").write_text(
        "term,aliases,category,definition,source_name,source_url\n"
        "거래량,[],가격/차트,기존 거래량 설명,KB증권 금융용어사전,https://example.com/kb-volume\n"
        "PER,[],투자지표/밸류에이션,PER 설명,KB증권 금융용어사전,https://example.com/per\n",
        encoding="utf-8",
    )
    (samples_dir / "source_conflict_resolution_results.csv").write_text(
        "term,decision,recommended_definition,representative_source_id,representative_source_name,representative_source_url,source_count\n"
        "거래량,resolved,충돌 해결 거래량 설명,source_2,미래에셋증권 증권용어사전,https://example.com/mirae-volume,2\n",
        encoding="utf-8",
    )

    build_final_artifacts(data_dir=data_dir, output_dir=output_dir, samples_dir=samples_dir)

    with (data_dir / "cleaned_terms.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    volume = next(row for row in rows if row["term"] == "거래량")
    assert volume["definition"] == "충돌 해결 거래량 설명"
    assert volume["source_name"] == "미래에셋증권 증권용어사전"
    assert volume["source_url"] == "https://example.com/mirae-volume"

    with sqlite3.connect(output_dir / "stock_dictionary.sqlite") as conn:
        count = conn.execute("SELECT COUNT(*) FROM stock_terms").fetchone()[0]
    assert count == 2
    assert (output_dir / "schema.postgres.sql").exists()
    assert (output_dir / "seed_terms.csv").exists()
    assert (output_dir / "seed_terms.sql").exists()
    assert not (output_dir / "upload_to_neon.md").exists()
    assert not (output_dir / "migration_to_neon.md").exists()


def test_build_final_artifacts_limits_exported_terms(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    samples_dir = data_dir / "llm_samples"
    samples_dir.mkdir(parents=True)

    (samples_dir / "definition_rewrite_results.csv").write_text(
        "term,aliases,category,definition,source_name,source_url\n"
        "거래량,[],가격/차트,거래량 설명,KB증권 금융용어사전,https://example.com/volume\n"
        "PER,[],투자지표/밸류에이션,PER 설명,KB증권 금융용어사전,https://example.com/per\n"
        "PBR,[],투자지표/밸류에이션,PBR 설명,KB증권 금융용어사전,https://example.com/pbr\n",
        encoding="utf-8",
    )
    (samples_dir / "source_conflict_resolution_results.csv").write_text(
        "term,decision,recommended_definition,representative_source_id,representative_source_name,representative_source_url,source_count\n",
        encoding="utf-8",
    )

    terms = build_final_artifacts(
        data_dir=data_dir,
        output_dir=output_dir,
        samples_dir=samples_dir,
        limit=2,
    )

    assert [term.term for term in terms] == ["거래량", "PER"]
    with (data_dir / "cleaned_terms.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert [row["term"] for row in rows] == ["거래량", "PER"]

    with sqlite3.connect(output_dir / "stock_dictionary.sqlite") as conn:
        count = conn.execute("SELECT COUNT(*) FROM stock_terms").fetchone()[0]
    assert count == 2


def test_build_final_artifacts_normalizes_aliases_and_merges_duplicate_terms(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    samples_dir = data_dir / "llm_samples"
    samples_dir.mkdir(parents=True)

    (samples_dir / "definition_rewrite_results.csv").write_text(
        "term,aliases,category,definition,source_name,source_url\n"
        "감자,[],공시/기업행위,감자 설명,KB증권 금융용어사전,https://example.com/reduction\n"
        "감자 (reduction of capital),[],공시/기업행위,감자 영문 설명,미래에셋증권 증권용어사전,https://example.com/reduction-en\n",
        encoding="utf-8",
    )
    (samples_dir / "source_conflict_resolution_results.csv").write_text(
        "term,decision,recommended_definition,representative_source_id,representative_source_name,representative_source_url,source_count\n",
        encoding="utf-8",
    )

    terms = build_final_artifacts(data_dir=data_dir, output_dir=output_dir, samples_dir=samples_dir)

    assert len(terms) == 1
    assert terms[0].term == "감자"
    assert terms[0].aliases == ["reduction of capital"]

    with sqlite3.connect(output_dir / "stock_dictionary.sqlite") as conn:
        count = conn.execute("SELECT COUNT(*) FROM stock_terms").fetchone()[0]
        aliases = conn.execute("SELECT aliases FROM stock_terms WHERE term = '감자'").fetchone()[0]
    assert count == 1
    assert aliases == '["reduction of capital"]'
