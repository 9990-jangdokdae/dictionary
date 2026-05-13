from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Iterable

from stock_dictionary.models import CleanedTerm, RawTerm, ReviewRequiredTerm


ALLOWED_CATEGORIES = [
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
    "기타",
]

COMMON_ABBREVIATIONS = {"PER", "PBR", "ROE", "EPS", "BPS", "YOY", "QOQ", "MOM", "YTD", "TTM"}

ALIAS_GROUPS = [
    {"PER", "주가수익비율", "P/E Ratio"},
    {"PBR", "주가순자산비율"},
    {"ROE", "자기자본이익률"},
    {"EPS", "주당순이익"},
    {"BPS", "주당순자산"},
    {"YoY", "전년 동기 대비", "Year on Year"},
    {"QoQ", "전분기 대비", "Quarter on Quarter"},
    {"유상증자", "유상 증자"},
]

SOURCE_PRIORITY = [
    "금융위원회",
    "KB증권",
    "미래에셋",
    "iM증권",
    "한국투자",
    "KDI",
    "신한투자",
]


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_term(term: str) -> str:
    return re.sub(r"[\s/()·.,_-]+", "", term).casefold()


def clean_display_term(term: str) -> str:
    text = _clean_text(term)
    while True:
        matches = list(re.finditer(r"\(([^()]*)\)", text))
        if len(matches) < 2:
            return text
        last = matches[-1]
        previous = matches[-2]
        last_value = _clean_text(last.group(1)).casefold()
        previous_value = _clean_text(previous.group(1)).casefold()
        if last_value != previous_value:
            return text
        text = _clean_text(text[: last.start()] + text[last.end() :])


def normalize_term_aliases(term: str, aliases: Iterable[str]) -> tuple[str, list[str]]:
    base_term, extracted_aliases = _split_parenthetical_aliases(clean_display_term(term))
    normalized_aliases: list[str] = []
    for alias in aliases:
        alias_base, alias_extracted = _split_parenthetical_aliases(clean_display_term(alias))
        _append_alias(normalized_aliases, base_term, alias_base)
        for extracted_alias in alias_extracted:
            _append_alias(normalized_aliases, base_term, extracted_alias)
    for extracted_alias in extracted_aliases:
        _append_alias(normalized_aliases, base_term, extracted_alias)
    return base_term, normalized_aliases


def _append_alias(aliases: list[str], term: str, alias: str) -> None:
    cleaned_alias = _clean_text(alias)
    if not cleaned_alias:
        return
    if normalize_term(cleaned_alias) == normalize_term(term):
        return
    if cleaned_alias not in aliases:
        aliases.append(cleaned_alias)


def _split_parenthetical_aliases(term: str) -> tuple[str, list[str]]:
    aliases: list[str] = []
    base_term = term
    while True:
        matched = False

        def replace(match: re.Match[str]) -> str:
            nonlocal matched
            matched = True
            content = _clean_text(match.group(1))
            aliases.extend(_split_alias_content(content))
            return " "

        base_term = _clean_text(re.sub(r"\(([^()]*)\)", replace, base_term))
        if not matched:
            return base_term, aliases


def _split_alias_content(content: str) -> list[str]:
    return [_clean_text(part) for part in re.split(r"[,;]", content) if _clean_text(part)]


def _alias_key(term: str) -> str:
    normalized = normalize_term(normalize_term_aliases(term, [])[0])
    for group in ALIAS_GROUPS:
        if any(normalize_term(item) == normalized for item in group):
            return min(normalize_term(item) for item in group)
    return normalized


def choose_representative_term(candidates: Iterable[str]) -> str:
    terms = [clean_display_term(candidate) for candidate in candidates if candidate.strip()]
    for term in terms:
        if term.upper() in COMMON_ABBREVIATIONS:
            return term
    no_space = [term for term in terms if " " not in term]
    korean = [term for term in no_space if re.search(r"[가-힣]", term)]
    if korean:
        return sorted(korean, key=lambda item: (len(item), item))[0]
    if no_space:
        return sorted(no_space, key=lambda item: (len(item), item))[0]
    return sorted(terms, key=lambda item: (len(item), item))[0]


def assign_category(term: str, definition: str) -> str:
    text = f"{term} {definition}".casefold()
    if any(keyword.casefold() in text for keyword in ["PER", "PBR", "ROE", "EPS", "BPS", "수익비율", "투자지표", "밸류에이션"]):
        return "투자지표/밸류에이션"
    if any(keyword in text for keyword in ["매출", "영업이익", "당기순이익", "자산", "부채", "자본", "재무제표"]):
        return "재무/회계"
    if any(keyword in text for keyword in ["주문", "체결", "호가", "시장가", "지정가", "증거금", "미수"]):
        return "거래/주문/결제"
    if any(keyword in text for keyword in ["시가", "고가", "저가", "종가", "등락률", "가격", "주가"]):
        return "가격/차트"
    if any(keyword in text for keyword in ["코스피", "코스닥", "상장", "관리종목", "시가총액"]):
        return "시장/상장"
    if any(keyword in text for keyword in ["공시", "증자", "감자", "합병", "자기주식", "권리락"]):
        return "공시/기업행위"
    if any(keyword in text for keyword in ["배당", "주주환원"]):
        return "배당/주주환원"
    if any(keyword in text for keyword in ["개인", "기관", "외국인", "순매수", "순매도", "수급"]):
        return "수급/투자자"
    if any(keyword.casefold() in text for keyword in ["YoY", "QoQ", "컨센서스", "목표주가", "투자의견", "어닝"]):
        return "리포트/실적 표현"
    if any(keyword in text for keyword in ["금리", "환율", "물가", "경기"]):
        return "거시경제"
    if any(keyword in text for keyword in ["주식", "종목", "매수", "매도", "거래량"]):
        return "주식 기초"
    return "기타"


def apply_category_gate(rows: Iterable[CleanedTerm]) -> tuple[list[CleanedTerm], list[ReviewRequiredTerm]]:
    included: list[CleanedTerm] = []
    excluded: list[ReviewRequiredTerm] = []
    for row in rows:
        if row.category == "기타":
            excluded.append(
                ReviewRequiredTerm(
                    term=row.term,
                    aliases=row.aliases,
                    category=row.category,
                    reason="category_gate_excluded",
                    source_name=row.source_name,
                    source_url=row.source_url,
                    notes="category is 기타; excluded before downstream LLM stages",
                )
            )
        else:
            included.append(row)
    return included, excluded


def _source_rank(source_name: str) -> int:
    for index, marker in enumerate(SOURCE_PRIORITY):
        if marker in source_name:
            return index
    return len(SOURCE_PRIORITY)


def clean_raw_terms(rows: Iterable[RawTerm]) -> list[CleanedTerm]:
    grouped: dict[str, list[RawTerm]] = {}
    for row in rows:
        if _is_noise(row):
            continue
        grouped.setdefault(_alias_key(row.term), []).append(row.model_copy(update={"term": clean_display_term(row.term)}))

    cleaned: list[CleanedTerm] = []
    for group_rows in grouped.values():
        representative = choose_representative_term(row.term for row in group_rows)
        source = sorted(group_rows, key=lambda row: _source_rank(row.source_name))[0]
        aliases = [row.term for row in group_rows if row.term != representative]
        representative, aliases = normalize_term_aliases(representative, aliases)
        definition = source.raw_definition
        cleaned.append(
            CleanedTerm(
                term=representative,
                aliases=aliases,
                category=assign_category(representative, definition),
                definition=definition,
                source_name=source.source_name,
                source_url=source.source_url,
            )
        )
    return sorted(cleaned, key=lambda row: row.term)


def _is_noise(row: RawTerm) -> bool:
    term = row.term.strip()
    definition = row.raw_definition.strip()
    if not term or not definition:
        return True
    if "만족하셨나요" in term or definition in {"매우만족", "만족", "보통", "불만족", "매우불만족"}:
        return True
    if re.search(r"\d{2,4}-\d{3,4}", definition) and len(definition) < 80:
        return True
    if len(term) > 80 or len(definition) < 6:
        return True
    return False


def write_cleaned_terms(path: str | Path, rows: Iterable[CleanedTerm]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["term", "aliases", "category", "definition", "source_name", "source_url"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())
