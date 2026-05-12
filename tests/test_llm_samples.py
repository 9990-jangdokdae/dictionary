import csv

from stock_dictionary.models import CleanedTerm, RawTerm
from stock_dictionary.llm_pipeline import DuplicateAliasJudgmentOutput, SourceConflictResolutionOutput
from scripts.run_llm_samples import (
    generate_source_conflict_groups,
    generate_duplicate_alias_candidate_groups,
    run_category_assignment_samples,
    run_definition_rewrite_samples,
    run_duplicate_alias_samples,
    run_source_conflict_samples,
    write_category_assignment_outputs,
)


def _term(term: str, category: str = "기타") -> CleanedTerm:
    return CleanedTerm(
        term=term,
        aliases=[],
        category=category,
        definition=f"{term} 설명",
        source_name="sample",
        source_url=f"https://example.com/{term}",
    )


def _raw(term: str, definition: str, source_name: str) -> RawTerm:
    return RawTerm(
        term=term,
        raw_definition=definition,
        source_name=source_name,
        source_url=f"https://example.com/{source_name}",
        collected_at="2026-05-12T12:00:00+09:00",
    )


def test_run_category_assignment_samples_preserves_input_order_with_parallelism():
    rows = [_term("KOSPI", "가격/차트"), _term("감자", "재무/회계"), _term("PER", "기타")]

    def fake_assigner(term: CleanedTerm):
        return term.model_copy(update={"category": f"분류-{term.term}"}), None

    results, reviews = run_category_assignment_samples(rows, limit=3, parallelism=2, assigner=fake_assigner)

    assert reviews == []
    assert [row.term for row in results] == ["KOSPI", "감자", "PER"]
    assert [row.category for row in results] == ["분류-KOSPI", "분류-감자", "분류-PER"]


def test_run_category_assignment_samples_without_limit_processes_all_rows():
    rows = [_term("KOSPI", "가격/차트"), _term("감자", "재무/회계"), _term("PER", "기타")]

    def fake_assigner(term: CleanedTerm):
        return term, None

    results, reviews = run_category_assignment_samples(rows, limit=None, parallelism=2, assigner=fake_assigner)

    assert reviews == []
    assert [row.term for row in results] == ["KOSPI", "감자", "PER"]


def test_run_definition_rewrite_samples_preserves_order_and_reviews():
    rows = [_term("PER", "투자지표/밸류에이션"), _term("애매한용어", "주식 기초")]

    def fake_rewriter(term: CleanedTerm):
        if term.term == "애매한용어":
            from stock_dictionary.models import ReviewRequiredTerm

            return None, ReviewRequiredTerm(
                term=term.term,
                aliases=term.aliases,
                category=term.category,
                reason="llm_definition_uncertain",
                source_name=term.source_name,
                source_url=term.source_url,
                notes="uncertain",
            )
        return term.model_copy(update={"definition": f"{term.term} 정제 설명"}), None

    results, reviews = run_definition_rewrite_samples(rows, parallelism=2, rewriter=fake_rewriter)

    assert [row.term for row in results] == ["PER"]
    assert results[0].definition == "PER 정제 설명"
    assert [review.term for review in reviews] == ["애매한용어"]
    assert reviews[0].reason == "llm_definition_uncertain"


def test_write_category_assignment_outputs_removes_misc_from_next_step_results(tmp_path):
    rows = [_term("PER", "투자지표/밸류에이션"), _term("IRP이체신청", "기타")]

    included, excluded = write_category_assignment_outputs(tmp_path, rows, [])

    with (tmp_path / "category_assignment_results.csv").open(encoding="utf-8", newline="") as f:
        result_rows = list(csv.DictReader(f))
    with (tmp_path / "category_assignment_all.csv").open(encoding="utf-8", newline="") as f:
        all_rows = list(csv.DictReader(f))
    with (tmp_path / "category_assignment_excluded.csv").open(encoding="utf-8", newline="") as f:
        excluded_rows = list(csv.DictReader(f))

    assert [row.term for row in included] == ["PER"]
    assert [row.term for row in excluded] == ["IRP이체신청"]
    assert [row["term"] for row in result_rows] == ["PER"]
    assert [row["term"] for row in all_rows] == ["PER", "IRP이체신청"]
    assert excluded_rows[0]["reason"] == "category_gate_excluded"


def test_generate_duplicate_alias_candidate_groups_uses_structural_similarity_only():
    rows = [
        _term("PSR", "투자지표/밸류에이션"),
        _term("PSR(price selling ratio)", "투자지표/밸류에이션"),
        _term("PER", "투자지표/밸류에이션"),
    ]

    groups = generate_duplicate_alias_candidate_groups(rows)

    assert [[term.term for term in group] for group in groups] == [["PSR", "PSR(price selling ratio)"]]


def test_run_duplicate_alias_samples_preserves_group_order_with_parallelism():
    groups = [
        [_term("PSR", "투자지표/밸류에이션"), _term("PSR(price selling ratio)", "투자지표/밸류에이션")],
        [_term("감자", "공시/기업행위"), _term("감자 (reduction of capital)", "공시/기업행위")],
    ]

    def fake_judger(candidates):
        return (
            DuplicateAliasJudgmentOutput(
                decision="alias",
                representative_term=candidates[0].term,
                aliases=[candidate.term for candidate in candidates[1:]],
            ),
            None,
        )

    results, reviews = run_duplicate_alias_samples(groups, parallelism=2, judger=fake_judger)

    assert reviews == []
    assert [row["candidate_terms"] for row in results] == [
        "PSR | PSR(price selling ratio)",
        "감자 | 감자 (reduction of capital)",
    ]
    assert [row["representative_term"] for row in results] == ["PSR", "감자"]


def test_generate_source_conflict_groups_matches_cleaned_terms_to_multiple_raw_sources():
    cleaned = [_term("PER", "투자지표/밸류에이션"), _term("KOSPI", "시장/상장")]
    raw_rows = [
        _raw("PER", "주가를 주당순이익으로 나눈 지표", "KB증권"),
        _raw("PER", "기업 이익 대비 주가 수준을 보는 지표", "미래에셋"),
        _raw("KOSPI", "유가증권시장", "KB증권"),
    ]

    groups = generate_source_conflict_groups(cleaned, raw_rows)

    assert len(groups) == 1
    term, category, sources = groups[0]
    assert term == "PER"
    assert category == "투자지표/밸류에이션"
    assert [source.source_name for source in sources] == ["KB증권", "미래에셋"]


def test_run_source_conflict_samples_preserves_group_order_with_parallelism():
    groups = [
        ("PER", "투자지표/밸류에이션", [_raw("PER", "정의1", "KB증권"), _raw("PER", "정의2", "미래에셋")]),
        ("KOSPI", "시장/상장", [_raw("KOSPI", "정의1", "KB증권"), _raw("KOSPI", "정의2", "iM증권")]),
    ]

    def fake_resolver(term, sources, category):
        return (
            SourceConflictResolutionOutput(
                decision="resolved",
                recommended_definition=f"{term} 대표 정의",
                representative_source_id="source_1",
            ),
            None,
        )

    results, reviews = run_source_conflict_samples(groups, parallelism=2, resolver=fake_resolver)

    assert reviews == []
    assert [row["term"] for row in results] == ["PER", "KOSPI"]
    assert [row["representative_source_name"] for row in results] == ["KB증권", "KB증권"]
    assert [row["representative_source_url"] for row in results] == ["https://example.com/KB증권", "https://example.com/KB증권"]
