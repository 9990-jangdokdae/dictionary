import csv
import json

from stock_dictionary.models import RawTerm
from stock_dictionary.preprocess import (
    ALLOWED_CATEGORIES,
    apply_category_gate,
    assign_category,
    clean_display_term,
    clean_raw_terms,
    choose_representative_term,
    normalize_term,
    normalize_term_aliases,
    write_cleaned_terms,
)


def test_normalize_term_removes_spaces_and_ignores_case_for_latin_terms():
    assert normalize_term("P/E Ratio") == "peratio"
    assert normalize_term("유상 증자") == "유상증자"


def test_clean_display_term_removes_duplicate_parenthetical_suffixes():
    assert clean_display_term("MMF(Money Market Fund) (Money Market Fund )") == "MMF(Money Market Fund)"
    assert clean_display_term("감자 (reduction of capital) (reduction of capital)") == "감자 (reduction of capital)"


def test_choose_representative_term_prefers_common_abbreviation():
    assert choose_representative_term(["주가수익비율", "PER", "P/E Ratio"]) == "PER"
    assert choose_representative_term(["유상 증자", "유상증자"]) == "유상증자"


def test_normalize_term_aliases_splits_parenthetical_aliases():
    term, aliases = normalize_term_aliases("감자 (reduction of capital)", [])

    assert term == "감자"
    assert aliases == ["reduction of capital"]


def test_normalize_term_aliases_keeps_abbreviation_as_representative():
    term, aliases = normalize_term_aliases("ELS(주가연계증권)", [])

    assert term == "ELS"
    assert aliases == ["주가연계증권"]


def test_normalize_term_aliases_handles_middle_parenthetical_expression():
    term, aliases = normalize_term_aliases("국제결제은행(BIS) 비율", [])

    assert term == "국제결제은행 비율"
    assert aliases == ["BIS"]


def test_normalize_term_aliases_handles_nested_parenthetical_expression():
    term, aliases = normalize_term_aliases("장외전자거래시장 (ECN (Electronic Communi-cation Network))", [])

    assert term == "장외전자거래시장"
    assert aliases == ["Electronic Communi-cation Network", "ECN"]


def test_normalize_term_aliases_drops_spacing_only_aliases():
    term, aliases = normalize_term_aliases("기본적분석", ["기본적 분석", "Fundamental Analysis"])

    assert term == "기본적분석"
    assert aliases == ["Fundamental Analysis"]


def test_normalize_term_aliases_splits_parenthetical_alias_values():
    term, aliases = normalize_term_aliases("감자", ["감자 (reduction of capital)"])

    assert term == "감자"
    assert aliases == ["reduction of capital"]


def test_assign_category_uses_prd_category_rules():
    assert assign_category("PER", "주가수익비율") == "투자지표/밸류에이션"
    assert assign_category("유상증자", "신주를 발행해 자금을 조달") == "공시/기업행위"
    assert assign_category("정체불명", "분류하기 어려운 설명") == "기타"
    assert "기타" in ALLOWED_CATEGORIES


def test_apply_category_gate_excludes_misc_terms_before_downstream_steps():
    terms = [
        RawTerm(
            term="PER",
            raw_definition="주가를 주당순이익으로 나눈 투자지표",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/per",
            collected_at="2026-05-12T12:00:00+09:00",
        ),
        RawTerm(
            term="IRP이체신청",
            raw_definition="개인형 퇴직연금 계좌의 적립금을 다른 금융회사로 옮기는 신청",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/irp",
            collected_at="2026-05-12T12:00:00+09:00",
        ),
    ]
    cleaned = [
        clean_raw_terms([terms[0]])[0],
        clean_raw_terms([terms[1]])[0].model_copy(update={"category": "기타"}),
    ]

    included, excluded = apply_category_gate(cleaned)

    assert [term.term for term in included] == ["PER"]
    assert [term.term for term in excluded] == ["IRP이체신청"]
    assert excluded[0].reason == "category_gate_excluded"
    assert excluded[0].category == "기타"


def test_clean_raw_terms_groups_aliases_and_keeps_representative_source():
    rows = [
        RawTerm(
            term="PER",
            raw_definition="주가를 주당순이익으로 나눈 투자지표",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/per",
            collected_at="2026-05-12T12:00:00+09:00",
        ),
        RawTerm(
            term="주가수익비율",
            raw_definition="PER와 같은 의미",
            source_name="한국투자증권 경제용어사전",
            source_url="https://example.com/per-ko",
            collected_at="2026-05-12T12:00:01+09:00",
        ),
    ]

    cleaned = clean_raw_terms(rows)

    assert len(cleaned) == 1
    assert cleaned[0].term == "PER"
    assert cleaned[0].aliases == ["주가수익비율"]
    assert cleaned[0].category == "투자지표/밸류에이션"
    assert cleaned[0].source_name == "KB증권 금융용어사전"


def test_clean_raw_terms_filters_obvious_navigation_and_contact_noise():
    rows = [
        RawTerm(
            term="CFD전용",
            raw_definition="1566-7053 (영업일 08:30 - 16:00)",
            source_name="iM증권 금융용어사전",
            source_url="https://example.com/noise",
            collected_at="2026-05-12T12:00:00+09:00",
        ),
        RawTerm(
            term="콘텐츠 내용에 만족하셨나요?",
            raw_definition="매우만족",
            source_name="금융위원회 금융용어설명",
            source_url="https://example.com/noise2",
            collected_at="2026-05-12T12:00:01+09:00",
        ),
        RawTerm(
            term="배당",
            raw_definition="기업이 이익 일부를 주주에게 나누는 것입니다.",
            source_name="금융위원회 금융용어설명",
            source_url="https://example.com/dividend",
            collected_at="2026-05-12T12:00:02+09:00",
        ),
    ]

    cleaned = clean_raw_terms(rows)

    assert [row.term for row in cleaned] == ["배당"]


def test_write_cleaned_terms_writes_aliases_as_json_array(tmp_path):
    cleaned = clean_raw_terms(
        [
            RawTerm(
                term="주가",
                raw_definition="주식의 가격",
                source_name="KB증권 금융용어사전",
                source_url="https://example.com/price",
                collected_at="2026-05-12T12:00:00+09:00",
            )
        ]
    )
    output = tmp_path / "cleaned_terms.csv"

    write_cleaned_terms(output, cleaned)

    with output.open(encoding="utf-8", newline="") as f:
        row = next(csv.DictReader(f))
    assert row["aliases"] == "[]"
    assert json.loads(row["aliases"]) == []
