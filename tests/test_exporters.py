import csv
import sqlite3

from stock_dictionary.exporters import (
    POSTGRES_SCHEMA,
    build_sqlite,
    export_postgres_artifacts,
)
from stock_dictionary.models import CleanedTerm


def sample_terms():
    return [
        CleanedTerm(
            term="PER",
            aliases=["주가수익비율", "P/E Ratio"],
            category="투자지표/밸류에이션",
            definition="PER는 주가를 주당순이익으로 나눈 투자지표입니다.",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/per",
        ),
        CleanedTerm(
            term="주가",
            aliases=[],
            category="가격/차트",
            definition="주가는 주식이 시장에서 거래되는 가격입니다.",
            source_name="금융위원회 금융용어설명",
            source_url="https://example.com/price",
        ),
    ]


def test_build_sqlite_creates_stock_terms_with_valid_json_aliases(tmp_path):
    db_path = tmp_path / "stock_dictionary.sqlite"

    build_sqlite(db_path, sample_terms())

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM stock_terms").fetchone()[0]
        invalid = conn.execute("SELECT COUNT(*) FROM stock_terms WHERE NOT json_valid(aliases)").fetchone()[0]
        aliases = conn.execute("SELECT aliases FROM stock_terms WHERE term = 'PER'").fetchone()[0]
    assert count == 2
    assert invalid == 0
    assert aliases == '["주가수익비율", "P/E Ratio"]'


def test_postgres_schema_uses_jsonb_and_required_columns():
    assert "CREATE TABLE stock_terms" in POSTGRES_SCHEMA
    assert "aliases JSONB NOT NULL DEFAULT '[]'::jsonb" in POSTGRES_SCHEMA
    assert "source_url TEXT NOT NULL" in POSTGRES_SCHEMA


def test_export_postgres_artifacts_writes_schema_and_seed_files(tmp_path):
    export_postgres_artifacts(tmp_path, sample_terms())

    assert (tmp_path / "schema.postgres.sql").read_text(encoding="utf-8") == POSTGRES_SCHEMA
    assert "INSERT INTO stock_terms" in (tmp_path / "seed_terms.sql").read_text(encoding="utf-8")
    assert not (tmp_path / "upload_to_neon.md").exists()
    assert not (tmp_path / "migration_to_neon.md").exists()

    with (tmp_path / "seed_terms.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["term"] == "PER"
    assert rows[1]["aliases"] == "[]"
