import csv
import json

from stock_dictionary.augmentation import (
    PROJECT_SOURCE_NAME,
    PROJECT_SOURCE_URL,
    load_term_augmentation_seed,
    merge_augmented_terms,
    validate_augmented_terms,
)
from stock_dictionary.models import CleanedTerm


def _term(term: str, category: str = "리포트/실적 표현", aliases=None, definition: str | None = None) -> CleanedTerm:
    return CleanedTerm(
        term=term,
        aliases=aliases or [],
        category=category,
        definition=definition or f"{term} 설명입니다.",
        source_name="source",
        source_url="https://example.com/source",
    )


def test_load_term_augmentation_seed_uses_project_source_and_json_aliases(tmp_path):
    seed_path = tmp_path / "term_augmentation_seed.csv"
    seed_path.write_text(
        "term,aliases,category,definition\n"
        'YoY,"[""Year on Year"",""전년 동기 대비""]",리포트/실적 표현,전년 같은 기간과 비교한 증감률\n',
        encoding="utf-8",
    )

    terms = load_term_augmentation_seed(seed_path)

    assert len(terms) == 1
    assert terms[0].term == "YoY"
    assert terms[0].aliases == ["Year on Year", "전년 동기 대비"]
    assert terms[0].source_name == PROJECT_SOURCE_NAME
    assert terms[0].source_url == PROJECT_SOURCE_URL


def test_validate_augmented_terms_rejects_existing_duplicates_and_forbidden_advice():
    existing = [_term("PER", "투자지표/밸류에이션", aliases=["주가수익비율"])]
    candidates = [
        _term("YoY", aliases=["Year on Year"]),
        _term("주가수익비율", "투자지표/밸류에이션"),
        _term("투자 추천 용어", definition="이 종목은 매수 추천 대상입니다."),
    ]

    results, reviews = validate_augmented_terms(candidates, existing)

    assert [term.term for term in results] == ["YoY"]
    assert [review.reason for review in reviews] == [
        "term_augmentation_duplicate",
        "term_augmentation_forbidden_advice",
    ]


def test_validate_augmented_terms_checks_normalized_existing_parenthetical_aliases():
    existing = [_term("주당순이익(EPS)", "투자지표/밸류에이션")]
    candidates = [_term("EPS", "투자지표/밸류에이션")]

    results, reviews = validate_augmented_terms(candidates, existing)

    assert results == []
    assert [review.reason for review in reviews] == ["term_augmentation_duplicate"]


def test_merge_augmented_terms_appends_only_valid_terms():
    base = [_term("PER", "투자지표/밸류에이션")]
    augmented = [_term("YoY"), _term("PER", "투자지표/밸류에이션")]

    merged, reviews = merge_augmented_terms(base, augmented)

    assert [term.term for term in merged] == ["PER", "YoY"]
    assert [review.reason for review in reviews] == ["term_augmentation_duplicate"]


def test_repository_term_augmentation_seed_is_valid():
    terms = load_term_augmentation_seed("data/term_augmentation_seed.csv")
    results, reviews = validate_augmented_terms(terms, [])

    assert len(terms) == 33
    assert len(results) == 33
    assert reviews == []
    assert all(json.loads(row["aliases"]) is not None for row in csv.DictReader(open("data/term_augmentation_seed.csv", encoding="utf-8")))
