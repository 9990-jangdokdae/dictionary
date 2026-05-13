from stock_dictionary.llm_pipeline import (
    CategoryAssignmentOutput,
    DefinitionRewriteOutput,
    DuplicateAliasJudgmentOutput,
    LLMJsonRunner,
    SourceConflictResolutionOutput,
    TermAugmentationOutput,
    augment_terms_with_llm,
    assign_category_with_llm,
    build_category_assignment_prompt,
    build_definition_prompt,
    build_duplicate_alias_prompt,
    build_source_conflict_prompt,
    build_term_augmentation_prompt,
    judge_duplicate_alias_with_llm,
    resolve_source_conflict_with_llm,
    ReviewRequiredTerm,
    get_task_thinking_level,
    init_dictionary_llm,
    rewrite_definition_with_llm,
)
from stock_dictionary.models import CleanedTerm, RawTerm


def test_llm_json_runner_parses_valid_json_response():
    runner = LLMJsonRunner(max_retries=2)

    result, review = runner.run(
        DefinitionRewriteOutput,
        lambda attempt: '{"decision": "rewritten", "definition": "PER는 주가를 주당순이익으로 나눈 투자지표입니다."}',
        review_context={
            "term": "PER",
            "aliases": ["주가수익비율"],
            "category": "투자지표/밸류에이션",
            "source_name": "KB증권 금융용어사전",
            "source_url": "https://example.com/per",
        },
    )

    assert result is not None
    assert result.definition.startswith("PER는")
    assert review is None


def test_llm_json_runner_retries_then_succeeds():
    responses = iter(
        [
            "not-json",
            '{"decision": "rewritten", "definition": "YoY는 전년 같은 기간과 비교한다는 뜻입니다."}',
        ]
    )
    runner = LLMJsonRunner(max_retries=2)

    result, review = runner.run(
        DefinitionRewriteOutput,
        lambda attempt: next(responses),
        review_context={
            "term": "YoY",
            "aliases": ["Year on Year"],
            "category": "리포트/실적 표현",
            "source_name": "KB증권 금융용어사전",
            "source_url": "https://example.com/yoy",
        },
    )

    assert result is not None
    assert "전년" in result.definition
    assert review is None


def test_llm_json_runner_writes_review_context_after_three_failures():
    runner = LLMJsonRunner(max_retries=2)

    result, review = runner.run(
        DefinitionRewriteOutput,
        lambda attempt: "not-json",
        review_context={
            "term": "권리락",
            "aliases": [],
            "category": "공시/기업행위",
            "source_name": "KB증권 금융용어사전",
            "source_url": "https://example.com/right",
        },
    )

    assert result is None
    assert isinstance(review, ReviewRequiredTerm)
    assert review.reason == "llm_json_validation_failed"
    assert "attempts=3" in review.notes


def test_llm_json_runner_rejects_legacy_reason_key():
    runner = LLMJsonRunner(max_retries=0)

    result, review = runner.run(
        DefinitionRewriteOutput,
        lambda attempt: '{"decision": "rewritten", "definition": "설명입니다.", "reason": "legacy"}',
        review_context={
            "term": "PER",
            "aliases": [],
            "category": "투자지표/밸류에이션",
            "source_name": "KB증권 금융용어사전",
            "source_url": "https://example.com/per",
        },
    )

    assert result is None
    assert review is not None
    assert review.reason == "llm_json_validation_failed"


def test_init_dictionary_llm_uses_google_genai_prefix(monkeypatch):
    captured = {}

    def fake_init_chat_model(model, **kwargs):
        captured["model"] = model
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("MAIN_MODEL", "gemini-3-flash")
    monkeypatch.setattr("stock_dictionary.llm_pipeline.init_chat_model", fake_init_chat_model)

    llm = init_dictionary_llm()

    assert llm is not None
    assert captured["model"] == "google_genai:gemini-3-flash"
    assert captured["configurable_fields"] == ("model", "model_provider")
    assert captured["temperature"] == 0
    assert captured["thinking_level"] == "medium"


def test_init_dictionary_llm_uses_task_specific_thinking_level(monkeypatch):
    captured = {}

    def fake_init_chat_model(model, **kwargs):
        captured["model"] = model
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("MAIN_MODEL", "gemini-3-flash")
    monkeypatch.setattr("stock_dictionary.llm_pipeline.init_chat_model", fake_init_chat_model)

    init_dictionary_llm(task="source_conflict_resolution")

    assert captured["thinking_level"] == "high"


def test_init_dictionary_llm_uses_term_augmentation_thinking_level(monkeypatch):
    captured = {}

    def fake_init_chat_model(model, **kwargs):
        captured["model"] = model
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("MAIN_MODEL", "gemini-3-flash")
    monkeypatch.setattr("stock_dictionary.llm_pipeline.init_chat_model", fake_init_chat_model)

    init_dictionary_llm(task="term_augmentation")

    assert captured["thinking_level"] == "medium"


def test_init_dictionary_llm_uses_env_thinking_level_override(monkeypatch):
    captured = {}

    def fake_init_chat_model(model, **kwargs):
        captured["model"] = model
        captured.update(kwargs)
        return object()

    monkeypatch.setenv("MAIN_MODEL", "gemini-3-flash")
    monkeypatch.setenv("DEFINITION_REWRITE_THINKING_LEVEL", "low")
    monkeypatch.setattr("stock_dictionary.llm_pipeline.init_chat_model", fake_init_chat_model)

    init_dictionary_llm(task="definition_rewrite")

    assert captured["thinking_level"] == "low"


def test_get_task_thinking_level_rejects_invalid_env_value(monkeypatch):
    monkeypatch.setenv("CATEGORY_ASSIGNMENT_THINKING_LEVEL", "fast")

    try:
        get_task_thinking_level("category_assignment")
    except ValueError as exc:
        assert "CATEGORY_ASSIGNMENT_THINKING_LEVEL" in str(exc)
    else:
        raise AssertionError("expected invalid thinking level to raise")


def test_rewrite_definition_with_llm_updates_definition_with_fake_llm():
    class FakeLLM:
        def invoke(self, prompt):
            return '{"decision": "rewritten", "definition": "LLM으로 정제된 설명입니다."}'

    term = CleanedTerm(
        term="PER",
        aliases=["주가수익비율"],
        category="투자지표/밸류에이션",
        definition="원본 설명",
        source_name="KB증권 금융용어사전",
        source_url="https://example.com/per",
    )

    rewritten, review = rewrite_definition_with_llm(term, llm=FakeLLM())

    assert review is None
    assert rewritten is not None
    assert rewritten.definition == "LLM으로 정제된 설명입니다."


def test_rewrite_definition_with_llm_routes_uncertain_to_review():
    class FakeLLM:
        def invoke(self, prompt):
            return '{"decision": "uncertain", "definition": ""}'

    term = CleanedTerm(
        term="애매한 용어",
        aliases=[],
        category="기타",
        definition="원본 설명",
        source_name="KB증권 금융용어사전",
        source_url="https://example.com/uncertain",
    )

    rewritten, review = rewrite_definition_with_llm(term, llm=FakeLLM())

    assert rewritten is None
    assert review is not None
    assert review.reason == "llm_definition_uncertain"
    assert review.notes == "definition_rewrite returned uncertain decision"


def test_build_definition_prompt_uses_term_aliases_category_and_current_definition(tmp_path):
    prompt_file = tmp_path / "definition_rewrite.md"
    prompt_file.write_text("Base prompt", encoding="utf-8")
    term = CleanedTerm(
        term="PER",
        aliases=["주가수익비율"],
        category="투자지표/밸류에이션",
        definition="주가를 주당순이익으로 나눈 투자지표",
        source_name="KB증권 금융용어사전",
        source_url="https://example.com/per",
    )

    prompt = build_definition_prompt(term, prompt_file)

    assert "term: PER" in prompt
    assert "aliases: ['주가수익비율']" in prompt
    assert "category: 투자지표/밸류에이션" in prompt
    assert "current_definition: 주가를 주당순이익으로 나눈 투자지표" in prompt
    assert '"decision" and "definition"' in prompt
    assert "KB증권" not in prompt
    assert "https://example.com/per" not in prompt


def test_build_category_assignment_prompt_uses_only_term_and_definition(tmp_path):
    prompt_file = tmp_path / "category_assignment.md"
    prompt_file.write_text("Category prompt", encoding="utf-8")
    term = CleanedTerm(
        term="KOSPI",
        aliases=[],
        category="가격/차트",
        definition="유가증권시장 상장 기업들의 주가 흐름을 나타내는 대표 지수",
        source_name="KB증권 금융용어사전",
        source_url="https://example.com/kospi",
    )

    prompt = build_category_assignment_prompt(term, prompt_file)

    assert "term: KOSPI" in prompt
    assert "definition: 유가증권시장" in prompt
    assert "category: 가격/차트" not in prompt
    assert "KB증권" not in prompt
    assert "https://example.com/kospi" not in prompt
    assert '"category"' in prompt


def test_build_duplicate_alias_prompt_uses_candidate_term_definition_category_only(tmp_path):
    prompt_file = tmp_path / "duplicate_alias_judgment.md"
    prompt_file.write_text("Duplicate prompt", encoding="utf-8")
    candidates = [
        CleanedTerm(
            term="PSR",
            aliases=[],
            category="투자지표/밸류에이션",
            definition="주가를 주당매출액으로 나눈 지표",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/psr",
        ),
        CleanedTerm(
            term="PSR(price selling ratio)",
            aliases=[],
            category="투자지표/밸류에이션",
            definition="price selling ratio",
            source_name="미래에셋증권 증권용어사전",
            source_url="https://example.com/psr-en",
        ),
    ]

    prompt = build_duplicate_alias_prompt(candidates, prompt_file)

    assert "term: PSR" in prompt
    assert "definition: 주가를 주당매출액" in prompt
    assert "category: 투자지표/밸류에이션" in prompt
    assert "KB증권" not in prompt
    assert "https://example.com/psr" not in prompt
    assert '"decision", "representative_term", and "aliases"' in prompt


def test_judge_duplicate_alias_with_llm_returns_alias_decision_with_fake_llm():
    class FakeLLM:
        def invoke(self, prompt):
            return '{"decision":"alias","representative_term":"PSR","aliases":["PSR(price selling ratio)"]}'

    candidates = [
        CleanedTerm(
            term="PSR",
            aliases=[],
            category="투자지표/밸류에이션",
            definition="주가를 주당매출액으로 나눈 지표",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/psr",
        ),
        CleanedTerm(
            term="PSR(price selling ratio)",
            aliases=[],
            category="투자지표/밸류에이션",
            definition="price selling ratio",
            source_name="미래에셋증권 증권용어사전",
            source_url="https://example.com/psr-en",
        ),
    ]

    result, review = judge_duplicate_alias_with_llm(candidates, llm=FakeLLM())

    assert review is None
    assert result is not None
    assert result.decision == "alias"
    assert result.representative_term == "PSR"
    assert result.aliases == ["PSR(price selling ratio)"]


def test_build_source_conflict_prompt_uses_source_name_and_definition_without_url(tmp_path):
    prompt_file = tmp_path / "source_conflict_resolution.md"
    prompt_file.write_text("Conflict prompt", encoding="utf-8")
    sources = [
        RawTerm(
            term="PER",
            raw_definition="주가를 주당순이익으로 나눈 지표",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/kb",
            collected_at="2026-05-12T12:00:00+09:00",
        ),
        RawTerm(
            term="PER",
            raw_definition="기업 이익 대비 주가 수준을 보는 투자지표",
            source_name="미래에셋증권 증권용어사전",
            source_url="https://example.com/mirae",
            collected_at="2026-05-12T12:00:00+09:00",
        ),
    ]

    prompt = build_source_conflict_prompt("PER", sources, prompt_file)

    assert "term: PER" in prompt
    assert "source_id: source_1" in prompt
    assert "source_name: KB증권 금융용어사전" in prompt
    assert "definition: 주가를 주당순이익으로 나눈 지표" in prompt
    assert "https://example.com/kb" not in prompt
    assert '"decision", "recommended_definition", and "representative_source_id"' in prompt


def test_build_term_augmentation_prompt_uses_seed_samples_and_limits(tmp_path):
    prompt_file = tmp_path / "term_augmentation.md"
    prompt_file.write_text("Augment prompt", encoding="utf-8")
    seed_terms = [
        CleanedTerm(
            term="YoY",
            aliases=["Year on Year"],
            category="리포트/실적 표현",
            definition="전년 같은 기간과 비교한 증감률",
            source_name="장독대 주식 용어 사전",
            source_url="https://example.com/prd",
        )
    ]
    existing_samples = [
        CleanedTerm(
            term="PER",
            aliases=["주가수익비율"],
            category="투자지표/밸류에이션",
            definition="주가를 주당순이익으로 나눈 지표",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/per",
        )
    ]

    prompt = build_term_augmentation_prompt(
        seed_terms,
        existing_samples,
        target_categories=["주식 기초", "리포트/실적 표현"],
        max_extra_terms_per_category=5,
        prompt_path=prompt_file,
    )

    assert "seed_terms:" in prompt
    assert "term: YoY" in prompt
    assert "existing_samples:" in prompt
    assert "term: PER" in prompt
    assert "target_categories: ['주식 기초', '리포트/실적 표현']" in prompt
    assert "max_extra_terms_per_category: 5" in prompt
    assert '"terms"' in prompt
    assert "https://example.com/per" not in prompt


def test_augment_terms_with_llm_returns_cleaned_terms_with_project_source():
    class FakeLLM:
        def invoke(self, prompt):
            return (
                '{"terms":[{"term":"YoY","aliases":["Year on Year","전년 동기 대비"],'
                '"category":"리포트/실적 표현","definition":"YoY는 전년 같은 기간과 비교한 증감률입니다."}]}'
            )

    seed_terms = [
        CleanedTerm(
            term="YoY",
            aliases=[],
            category="리포트/실적 표현",
            definition="전년 같은 기간과 비교",
            source_name="장독대 주식 용어 사전",
            source_url="https://example.com/prd",
        )
    ]

    terms, review = augment_terms_with_llm(
        seed_terms=seed_terms,
        existing_samples=[],
        target_categories=["리포트/실적 표현"],
        llm=FakeLLM(),
    )

    assert review is None
    assert terms is not None
    assert terms[0].term == "YoY"
    assert terms[0].aliases == ["Year on Year", "전년 동기 대비"]
    assert terms[0].source_name == "장독대 주식 용어 사전"


def test_term_augmentation_output_rejects_unknown_category():
    result, review = LLMJsonRunner(max_retries=0).run(
        TermAugmentationOutput,
        lambda attempt: '{"terms":[{"term":"테스트","aliases":[],"category":"뉴스 표현","definition":"설명"}]}',
        review_context={
            "term": "term_augmentation",
            "aliases": [],
            "category": "주식 기초",
            "source_name": "장독대 주식 용어 사전",
            "source_url": "https://example.com/prd",
        },
    )

    assert result is None
    assert review is not None
    assert review.reason == "llm_json_validation_failed"


def test_resolve_source_conflict_with_llm_returns_resolution_with_fake_llm():
    class FakeLLM:
        def invoke(self, prompt):
            return (
                '{"decision":"resolved","recommended_definition":"PER는 주가를 주당순이익으로 나눈 지표입니다.",'
                '"representative_source_id":"source_1"}'
            )

    sources = [
        RawTerm(
            term="PER",
            raw_definition="주가를 주당순이익으로 나눈 지표",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/kb",
            collected_at="2026-05-12T12:00:00+09:00",
        ),
        RawTerm(
            term="PER",
            raw_definition="기업 이익 대비 주가 수준을 보는 투자지표",
            source_name="미래에셋증권 증권용어사전",
            source_url="https://example.com/mirae",
            collected_at="2026-05-12T12:00:00+09:00",
        ),
    ]

    result, review = resolve_source_conflict_with_llm("PER", sources, category="투자지표/밸류에이션", llm=FakeLLM())

    assert review is None
    assert result is not None
    assert result.decision == "resolved"
    assert result.representative_source_id == "source_1"


def test_category_assignment_prompt_has_no_legacy_reason_field():
    prompt = build_category_assignment_prompt(
        CleanedTerm(
            term="KOSPI",
            aliases=[],
            category="가격/차트",
            definition="유가증권시장 상장 기업들의 주가 흐름을 나타내는 대표 지수",
            source_name="KB증권 금융용어사전",
            source_url="https://example.com/kospi",
        )
    )

    assert "reason" not in prompt


def test_assign_category_with_llm_updates_category_with_fake_llm():
    class FakeLLM:
        def invoke(self, prompt):
            return '{"category": "시장/상장"}'

    term = CleanedTerm(
        term="KOSPI",
        aliases=[],
        category="가격/차트",
        definition="유가증권시장 상장 기업들의 주가 흐름을 나타내는 대표 지수",
        source_name="KB증권 금융용어사전",
        source_url="https://example.com/kospi",
    )

    assigned, review = assign_category_with_llm(term, llm=FakeLLM())

    assert review is None
    assert assigned is not None
    assert assigned.category == "시장/상장"


def test_category_assignment_output_accepts_expanded_categories():
    result, review = LLMJsonRunner(max_retries=0).run(
        CategoryAssignmentOutput,
        lambda attempt: '{"category": "파생/구조화상품"}',
        review_context={
            "term": "DLS",
            "aliases": [],
            "category": "기타",
            "source_name": "KB증권 금융용어사전",
            "source_url": "https://example.com/dls",
        },
    )

    assert review is None
    assert result is not None
    assert result.category == "파생/구조화상품"


def test_category_assignment_output_rejects_unknown_category():
    result, review = LLMJsonRunner(max_retries=0).run(
        CategoryAssignmentOutput,
        lambda attempt: '{"category": "금융상품"}',
        review_context={
            "term": "DLS",
            "aliases": [],
            "category": "기타",
            "source_name": "KB증권 금융용어사전",
            "source_url": "https://example.com/dls",
        },
    )

    assert result is None
    assert review is not None
    assert review.reason == "llm_json_validation_failed"


def test_duplicate_alias_output_rejects_legacy_reason_key():
    result, review = LLMJsonRunner(max_retries=0).run(
        DuplicateAliasJudgmentOutput,
        lambda attempt: '{"decision":"separate","representative_term":"","aliases":[],"reason":"legacy"}',
        review_context={
            "term": "PSR | PER",
            "aliases": [],
            "category": "투자지표/밸류에이션",
            "source_name": "multiple",
            "source_url": "multiple",
        },
    )

    assert result is None
    assert review is not None
    assert review.reason == "llm_json_validation_failed"


def test_source_conflict_output_requires_resolved_fields():
    result, review = LLMJsonRunner(max_retries=0).run(
        SourceConflictResolutionOutput,
        lambda attempt: '{"decision":"resolved","recommended_definition":"","representative_source_id":""}',
        review_context={
            "term": "PER",
            "aliases": [],
            "category": "투자지표/밸류에이션",
            "source_name": "multiple",
            "source_url": "multiple",
        },
    )

    assert result is None
    assert review is not None
    assert review.reason == "llm_json_validation_failed"
