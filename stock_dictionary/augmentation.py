from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from stock_dictionary.models import CleanedTerm, ReviewRequiredTerm
from stock_dictionary.preprocess import normalize_term, normalize_term_aliases


PROJECT_SOURCE_NAME = "장독대 주식 용어 사전"
PROJECT_SOURCE_URL = ""

AUGMENTATION_TARGET_CATEGORIES = [
    "주식 기초",
    "리포트/실적 표현",
    "수급/투자자",
    "투자지표/밸류에이션",
]

ALLOWED_CATEGORIES = {
    "주식 기초",
    "시장/상장",
    "가격/차트",
    "거래/주문/결제",
    "공시/기업행위",
    "재무/회계",
    "투자지표/밸류에이션",
    "수급/투자자",
    "배당/주주환원",
    "리포트/실적 표현",
    "ETF/펀드",
    "파생/구조화상품",
    "채권/금리/환율",
    "거시경제",
}

FORBIDDEN_DEFINITION_PHRASES = [
    "매수 추천",
    "매도 추천",
    "투자 추천",
    "수익 보장",
    "반드시 상승",
    "반드시 하락",
    "무조건 상승",
    "무조건 하락",
]


def load_term_augmentation_seed(path: str | Path) -> list[CleanedTerm]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        rows = []
        for row in csv.DictReader(f):
            term, aliases = normalize_term_aliases(row["term"], json.loads(row["aliases"]))
            rows.append(
                CleanedTerm(
                    term=term,
                    aliases=aliases,
                    category=row["category"],
                    definition=row["definition"],
                    source_name=PROJECT_SOURCE_NAME,
                    source_url=PROJECT_SOURCE_URL,
                )
            )
    return rows


def validate_augmented_terms(
    candidates: Iterable[CleanedTerm],
    existing_terms: Iterable[CleanedTerm],
) -> tuple[list[CleanedTerm], list[ReviewRequiredTerm]]:
    existing_keys = _term_keys(existing_terms)
    accepted_keys: set[str] = set()
    accepted: list[CleanedTerm] = []
    reviews: list[ReviewRequiredTerm] = []

    for candidate in candidates:
        normalized = normalize_augmented_term(candidate)
        review_reason = _validation_error(normalized, existing_keys | accepted_keys)
        if review_reason:
            reviews.append(_review(normalized, review_reason))
            continue
        accepted.append(normalized)
        accepted_keys.update(_term_keys([normalized]))

    return accepted, reviews


def merge_augmented_terms(
    terms: Iterable[CleanedTerm],
    augmented_terms: Iterable[CleanedTerm],
) -> tuple[list[CleanedTerm], list[ReviewRequiredTerm]]:
    base_terms = list(terms)
    accepted, reviews = validate_augmented_terms(augmented_terms, base_terms)
    return [*base_terms, *accepted], reviews


def normalize_augmented_term(term: CleanedTerm) -> CleanedTerm:
    normalized_term, aliases = normalize_term_aliases(term.term, term.aliases)
    return term.model_copy(
        update={
            "term": normalized_term,
            "aliases": aliases,
            "source_name": PROJECT_SOURCE_NAME,
            "source_url": PROJECT_SOURCE_URL,
        }
    )


def normalize_augmented_terms(terms: Iterable[CleanedTerm]) -> list[CleanedTerm]:
    return [normalize_augmented_term(term) for term in terms]


def _term_keys(terms: Iterable[CleanedTerm]) -> set[str]:
    keys: set[str] = set()
    for term in terms:
        normalized_term, aliases = normalize_term_aliases(term.term, term.aliases)
        keys.add(normalize_term(normalized_term))
        keys.update(normalize_term(alias) for alias in aliases)
    return keys


def _validation_error(term: CleanedTerm, existing_keys: set[str]) -> str:
    if normalize_term(term.term) in existing_keys:
        return "term_augmentation_duplicate"
    if term.category not in ALLOWED_CATEGORIES:
        return "term_augmentation_invalid_category"
    if term.category == "기타":
        return "term_augmentation_misc_category"
    if not term.definition.strip():
        return "term_augmentation_empty_definition"
    if any(phrase in term.definition for phrase in FORBIDDEN_DEFINITION_PHRASES):
        return "term_augmentation_forbidden_advice"
    return ""


def _review(term: CleanedTerm, reason: str) -> ReviewRequiredTerm:
    return ReviewRequiredTerm(
        term=term.term,
        aliases=term.aliases,
        category=term.category,
        reason=reason,
        source_name=term.source_name,
        source_url=term.source_url,
    )
