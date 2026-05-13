from __future__ import annotations

import csv
import sqlite3
from pathlib import Path
from typing import Iterable

from stock_dictionary.models import CleanedTerm


SQLITE_SCHEMA = """CREATE TABLE IF NOT EXISTS stock_terms (
  id INTEGER PRIMARY KEY,
  term TEXT NOT NULL,
  aliases TEXT NOT NULL DEFAULT '[]' CHECK (json_valid(aliases)),
  category TEXT NOT NULL,
  definition TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

POSTGRES_SCHEMA = """CREATE TABLE stock_terms (
  id BIGSERIAL PRIMARY KEY,
  term TEXT NOT NULL,
  aliases JSONB NOT NULL DEFAULT '[]'::jsonb,
  category TEXT NOT NULL,
  definition TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

SEED_FIELDS = ["term", "aliases", "category", "definition", "source_name", "source_url"]


def build_sqlite(db_path: str | Path, terms: Iterable[CleanedTerm]) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    with sqlite3.connect(db_path) as conn:
        conn.execute(SQLITE_SCHEMA)
        conn.executemany(
            """
            INSERT INTO stock_terms (term, aliases, category, definition, source_name, source_url)
            VALUES (:term, :aliases, :category, :definition, :source_name, :source_url)
            """,
            [term.to_csv_row() for term in terms],
        )
        conn.commit()


def export_postgres_artifacts(output_dir: str | Path, terms: Iterable[CleanedTerm]) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [term.to_csv_row() for term in terms]

    (output_dir / "schema.postgres.sql").write_text(POSTGRES_SCHEMA, encoding="utf-8")
    _write_seed_csv(output_dir / "seed_terms.csv", rows)
    _write_seed_sql(output_dir / "seed_terms.sql", rows)


def _write_seed_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SEED_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _write_seed_sql(path: Path, rows: list[dict[str, str]]) -> None:
    lines = ["INSERT INTO stock_terms (term, aliases, category, definition, source_name, source_url) VALUES"]
    values = []
    for row in rows:
        values.append(
            "("
            + ", ".join(
                [
                    _sql_literal(row["term"]),
                    _sql_literal(row["aliases"]) + "::jsonb",
                    _sql_literal(row["category"]),
                    _sql_literal(row["definition"]),
                    _sql_literal(row["source_name"]),
                    _sql_literal(row["source_url"]),
                ]
            )
            + ")"
        )
    lines.append(",\n".join(values) + ";")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
