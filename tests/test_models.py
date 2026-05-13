import json

import pytest
from pydantic import ValidationError

from stock_dictionary.models import (
    CleanedTerm,
    RawTerm,
    ReviewRequiredTerm,
    ScrapeFailure,
)


def test_cleaned_term_serializes_empty_aliases_as_json_array_string():
    term = CleanedTerm(
        term="주가",
        aliases=[],
        category="주식 기초",
        definition="주가는 주식이 시장에서 거래되는 가격입니다.",
        source_name="KB증권 금융용어사전",
        source_url="https://example.com",
    )

    row = term.to_csv_row()

    assert row["aliases"] == "[]"
    assert json.loads(row["aliases"]) == []


def test_cleaned_term_accepts_alias_json_string_and_normalizes_it():
    term = CleanedTerm(
        term="PER",
        aliases='["주가수익비율", "P/E Ratio"]',
        category="투자지표/밸류에이션",
        definition="PER는 주가를 주당순이익으로 나눈 투자지표입니다.",
        source_name="KB증권 금융용어사전",
        source_url="https://example.com",
    )

    assert term.aliases == ["주가수익비율", "P/E Ratio"]
    assert term.to_csv_row()["aliases"] == '["주가수익비율", "P/E Ratio"]'


def test_cleaned_term_rejects_blank_required_fields():
    with pytest.raises(ValidationError):
        CleanedTerm(
            term="",
            aliases=[],
            category="투자지표/밸류에이션",
            definition="PER는 주가를 주당순이익으로 나눈 투자지표입니다.",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com",
        )


def test_cleaned_and_review_terms_allow_blank_source_url_for_project_managed_terms():
    term = CleanedTerm(
        term="YoY",
        aliases=["Year on Year"],
        category="리포트/실적 표현",
        definition="YoY는 전년 같은 기간과 비교한 증감률입니다.",
        source_name="장독대 주식 용어 사전",
        source_url="",
    )
    review = ReviewRequiredTerm(
        term="YoY",
        aliases=[],
        category="리포트/실적 표현",
        reason="review",
        source_name="장독대 주식 용어 사전",
        source_url="",
    )

    assert term.to_csv_row()["source_url"] == ""
    assert review.to_csv_row()["source_url"] == ""


def test_raw_review_and_failure_rows_are_csv_serializable():
    raw = RawTerm(
        term="매출",
        raw_definition="상품이나 서비스를 팔아 벌어들인 금액",
        source_name="금융위원회 금융용어설명",
        source_url="https://example.com/raw",
        collected_at="2026-05-12T12:00:00+09:00",
    )
    review = ReviewRequiredTerm(
        term="권리락",
        aliases=[],
        category="공시/기업행위",
        reason="uncertain",
        source_name="KB증권 금융용어사전",
        source_url="https://example.com/review",
        notes="출처 간 정의 충돌",
    )
    failure = ScrapeFailure(
        source_name="KB증권 금융용어사전",
        source_url="https://example.com/fail",
        failure_stage="fetch",
        error_message="timeout",
        attempted_at="2026-05-12T12:00:00+09:00",
    )

    assert raw.to_csv_row()["raw_definition"] == "상품이나 서비스를 팔아 벌어들인 금액"
    assert review.to_csv_row()["aliases"] == "[]"
    assert failure.to_csv_row()["failure_stage"] == "fetch"
