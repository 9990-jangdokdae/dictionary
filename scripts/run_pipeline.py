from __future__ import annotations

import argparse
import csv
import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from stock_dictionary.exporters import build_sqlite, export_postgres_artifacts
from stock_dictionary.llm_pipeline import rewrite_definition_with_llm
from stock_dictionary.models import CleanedTerm, RawTerm, ScrapeFailure
from stock_dictionary.preprocess import apply_category_gate, clean_raw_terms, write_cleaned_terms
from stock_dictionary.scrapers import scrape_reference


REFERENCES = [
    ("KB증권 금융용어사전", "https://www.kbsec.com/go.able?linkcd=m04110000"),
    ("미래에셋증권 증권용어사전", "https://securities.miraeasset.com/hki/hki3028/r01.do"),
    ("iM증권 금융용어사전", "https://www.imfnsec.com/research/financial_guide/fg000000.jsp"),
]


def run_pipeline(
    mode: str = "fixture",
    data_dir: str | Path = "data",
    output_dir: str | Path = "output",
    definition_rewriter: Callable[[CleanedTerm], CleanedTerm] | None = None,
    use_llm: bool = False,
    limit: int | None = None,
) -> None:
    load_dotenv()
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    if mode == "fixture":
        raw_terms, failures = _load_fixture_rows()
    elif mode == "existing":
        raw_terms, failures = _load_existing_rows(data_dir / "raw_terms.csv"), []
    else:
        raw_terms, failures = _scrape_live_rows()
    _write_csv(data_dir / "raw_terms.csv", ["term", "raw_definition", "source_name", "source_url", "collected_at"], raw_terms)
    _write_csv(
        data_dir / "scrape_failures.csv",
        ["source_name", "source_url", "failure_stage", "error_message", "attempted_at"],
        failures,
    )
    cleaned = clean_raw_terms(raw_terms)
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be greater than 0")
        cleaned = cleaned[:limit]
    cleaned, category_excluded_rows = apply_category_gate(cleaned)
    _write_review_log(data_dir / "category_excluded_terms.csv", category_excluded_rows)
    review_rows = []
    if definition_rewriter:
        cleaned = [definition_rewriter(term) for term in cleaned]
    elif use_llm:
        rewritten_terms: list[CleanedTerm] = []
        total = len(cleaned)
        for index, term in enumerate(cleaned, start=1):
            print(f"LLM definition rewrite {index}/{total}: {term.term}", flush=True)
            rewritten, review = rewrite_definition_with_llm(term)
            if rewritten:
                rewritten_terms.append(rewritten)
            if review:
                review_rows.append(review)
        cleaned = rewritten_terms
    _write_review_log(data_dir / "review_required_terms.csv", review_rows)
    write_cleaned_terms(data_dir / "cleaned_terms.csv", cleaned)
    build_sqlite(output_dir / "stock_dictionary.sqlite", cleaned)
    export_postgres_artifacts(output_dir, cleaned)


def _scrape_live_rows() -> tuple[list[RawTerm], list[ScrapeFailure]]:
    rows: list[RawTerm] = []
    failures: list[ScrapeFailure] = []
    for source_name, source_url in REFERENCES:
        scraped_rows, scraped_failures = scrape_reference(source_name, source_url)
        rows.extend(scraped_rows)
        failures.extend(scraped_failures)
    return rows, failures


def _load_fixture_rows() -> tuple[list[RawTerm], list[ScrapeFailure]]:
    collected_at = "2026-05-12T12:00:00+09:00"
    rows = [
        RawTerm(
            term="PER",
            raw_definition="주가를 주당순이익으로 나눈 투자지표입니다.",
            source_name="KB증권 금융용어사전",
            source_url="https://www.kbsec.com/go.able?linkcd=m04110000",
            collected_at=collected_at,
        ),
        RawTerm(
            term="주가수익비율",
            raw_definition="PER와 같은 의미의 투자지표입니다.",
            source_name="한국투자증권 경제용어사전",
            source_url="https://www.truefriend.com/main/research/dic/Dic.jsp",
            collected_at=collected_at,
        ),
        RawTerm(
            term="주가",
            raw_definition="주식이 시장에서 거래되는 가격입니다.",
            source_name="금융위원회 금융용어설명",
            source_url="https://www.fsc.go.kr/in090301",
            collected_at=collected_at,
        ),
        RawTerm(
            term="유상증자",
            raw_definition="회사가 신주를 발행해 자금을 조달하는 기업 이벤트입니다.",
            source_name="KB증권 금융용어사전",
            source_url="https://www.kbsec.com/go.able?linkcd=m04110000",
            collected_at=collected_at,
        ),
    ]
    return rows, []


def _load_existing_rows(path: Path) -> list[RawTerm]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [RawTerm(**row) for row in csv.DictReader(f)]


def _write_csv(path: Path, fieldnames: list[str], rows: list[object]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def _write_review_log(path: Path, rows: list[object]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["term", "aliases", "category", "reason", "source_name", "source_url", "notes"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["fixture", "live", "existing"], default="fixture")
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--use-llm", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run_pipeline(args.mode, args.data_dir, args.output_dir, use_llm=args.use_llm, limit=args.limit)


if __name__ == "__main__":
    main()
