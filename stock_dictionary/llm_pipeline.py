from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, TypeVar

from langchain.chat_models import init_chat_model
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from typing_extensions import Literal

from stock_dictionary.augmentation import PROJECT_SOURCE_NAME, PROJECT_SOURCE_URL
from stock_dictionary.models import ReviewRequiredTerm
from stock_dictionary.models import CleanedTerm, RawTerm


ThinkingLevel = Literal["minimal", "low", "medium", "high"]
LLMTaskName = Literal[
    "definition_rewrite",
    "duplicate_alias_judgment",
    "category_assignment",
    "source_conflict_resolution",
    "term_augmentation",
]

TASK_THINKING_LEVELS: dict[LLMTaskName, ThinkingLevel] = {
    "definition_rewrite": "medium",
    "duplicate_alias_judgment": "medium",
    "category_assignment": "minimal",
    "source_conflict_resolution": "high",
    "term_augmentation": "medium",
}

THINKING_LEVEL_ENV_VARS: dict[LLMTaskName, str] = {
    "definition_rewrite": "DEFINITION_REWRITE_THINKING_LEVEL",
    "duplicate_alias_judgment": "DUPLICATE_ALIAS_JUDGMENT_THINKING_LEVEL",
    "category_assignment": "CATEGORY_ASSIGNMENT_THINKING_LEVEL",
    "source_conflict_resolution": "SOURCE_CONFLICT_RESOLUTION_THINKING_LEVEL",
    "term_augmentation": "TERM_AUGMENTATION_THINKING_LEVEL",
}

VALID_THINKING_LEVELS = {"minimal", "low", "medium", "high"}


class StrictOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DefinitionRewriteOutput(StrictOutputModel):
    decision: Literal["rewritten", "uncertain"]
    definition: str = ""

    @model_validator(mode="after")
    def _definition_required_when_rewritten(self) -> "DefinitionRewriteOutput":
        if self.decision == "rewritten" and not self.definition.strip():
            raise ValueError("definition is required when decision is rewritten")
        return self


class DuplicateAliasJudgmentOutput(StrictOutputModel):
    decision: Literal["alias", "separate", "uncertain"]
    representative_term: str = ""
    aliases: list[str] = Field(default_factory=list)


CategoryName = Literal[
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


class CategoryAssignmentOutput(StrictOutputModel):
    category: CategoryName


class SourceConflictResolutionOutput(StrictOutputModel):
    decision: Literal["resolved", "uncertain"]
    recommended_definition: str = ""
    representative_source_id: str = ""

    @model_validator(mode="after")
    def _resolved_fields_required(self) -> "SourceConflictResolutionOutput":
        if self.decision == "resolved":
            if not self.recommended_definition.strip():
                raise ValueError("recommended_definition is required when decision is resolved")
            if not self.representative_source_id.strip():
                raise ValueError("representative_source_id is required when decision is resolved")
        return self


class TermAugmentationCandidateOutput(StrictOutputModel):
    term: str
    aliases: list[str] = Field(default_factory=list)
    category: CategoryName
    definition: str

    @model_validator(mode="after")
    def _required_text_fields(self) -> "TermAugmentationCandidateOutput":
        if not self.term.strip():
            raise ValueError("term is required")
        if not self.definition.strip():
            raise ValueError("definition is required")
        return self


class TermAugmentationOutput(StrictOutputModel):
    terms: list[TermAugmentationCandidateOutput] = Field(default_factory=list)


T = TypeVar("T", bound=BaseModel)


class LLMJsonRunner:
    def __init__(self, max_retries: int = 2):
        self.max_retries = max_retries

    def run(
        self,
        schema: type[T],
        invoke: Callable[[int], str],
        review_context: dict[str, object],
    ) -> tuple[T | None, ReviewRequiredTerm | None]:
        parser = JsonOutputParser()
        last_error = ""
        total_attempts = self.max_retries + 1
        for attempt in range(1, total_attempts + 1):
            try:
                parsed = parser.parse(invoke(attempt))
                return schema.model_validate(parsed), None
            except Exception as exc:
                last_error = str(exc)

        return None, ReviewRequiredTerm(
            term=str(review_context.get("term", "")),
            aliases=review_context.get("aliases", []),
            category=str(review_context.get("category", "기타")),
            reason="llm_json_validation_failed",
            source_name=str(review_context.get("source_name", "")),
            source_url=str(review_context.get("source_url", "")),
            notes=f"attempts={total_attempts}; error={last_error}",
        )


def _with_google_provider_prefix(model: str) -> str:
    if ":" not in model:
        return f"google_genai:{model}"
    return model


def get_task_thinking_level(task: LLMTaskName) -> ThinkingLevel:
    env_var = THINKING_LEVEL_ENV_VARS[task]
    level = os.getenv(env_var, TASK_THINKING_LEVELS[task]).strip()
    if level not in VALID_THINKING_LEVELS:
        allowed = ", ".join(sorted(VALID_THINKING_LEVELS))
        raise ValueError(f"{env_var} must be one of: {allowed}")
    return level  # type: ignore[return-value]


def init_dictionary_llm(
    task: LLMTaskName = "definition_rewrite",
    model: str | None = None,
):
    model = _with_google_provider_prefix(model or os.getenv("MAIN_MODEL", "gemini-3-flash"))
    return init_chat_model(
        model,
        configurable_fields=("model", "model_provider"),
        temperature=0,
        thinking_level=get_task_thinking_level(task),
        include_thoughts=False,
    )


def init_fallback_dictionary_llm(task: LLMTaskName = "definition_rewrite"):
    fallback_model = os.getenv("FALLBACK_MODEL", "").strip()
    primary_model = os.getenv("MAIN_MODEL", "gemini-3-flash").strip()
    if not fallback_model or fallback_model == primary_model:
        return None
    return init_dictionary_llm(task=task, model=fallback_model)


def _invoke_llm(llm, prompt: str) -> str:
    response = llm.invoke(prompt)
    content = getattr(response, "content", response)
    if isinstance(content, list):
        text_blocks: list[str] = []
        for block in content:
            if isinstance(block, str):
                text_blocks.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                text_blocks.append(block["text"])
        return "\n".join(text_blocks)
    return str(content)


def build_definition_prompt(term: CleanedTerm, prompt_path: str | Path = "prompts/definition_rewrite.md") -> str:
    prompt_template = Path(prompt_path).read_text(encoding="utf-8")
    return (
        f"{prompt_template}\n\n"
        "Input:\n"
        f'term: {term.term}\n'
        f"aliases: {term.aliases}\n"
        f"category: {term.category}\n\n"
        f"current_definition: {term.definition}\n\n"
        'Return JSON with keys "decision" and "definition".'
    )


def build_category_assignment_prompt(
    term: CleanedTerm,
    prompt_path: str | Path = "prompts/category_assignment.md",
) -> str:
    prompt_template = Path(prompt_path).read_text(encoding="utf-8")
    return (
        f"{prompt_template}\n\n"
        "Input:\n"
        f"term: {term.term}\n"
        f"definition: {term.definition}\n\n"
        'Return JSON with key "category".'
    )


def build_duplicate_alias_prompt(
    candidates: list[CleanedTerm],
    prompt_path: str | Path = "prompts/duplicate_alias_judgment.md",
) -> str:
    if len(candidates) < 2:
        raise ValueError("duplicate alias judgment requires at least 2 candidates")
    prompt_template = Path(prompt_path).read_text(encoding="utf-8")
    candidate_lines: list[str] = ["candidates:"]
    for candidate in candidates:
        candidate_lines.extend(
            [
                f"- term: {candidate.term}",
                f"  definition: {candidate.definition}",
                f"  category: {candidate.category}",
            ]
        )
    return (
        f"{prompt_template}\n\n"
        "Input:\n"
        f"{'\n'.join(candidate_lines)}\n\n"
        'Return JSON with keys "decision", "representative_term", and "aliases".'
    )


def build_source_conflict_prompt(
    term: str,
    sources: list[RawTerm],
    prompt_path: str | Path = "prompts/source_conflict_resolution.md",
) -> str:
    if len(sources) < 2:
        raise ValueError("source conflict resolution requires at least 2 sources")
    prompt_template = Path(prompt_path).read_text(encoding="utf-8")
    source_lines: list[str] = ["sources:"]
    for index, source in enumerate(sources, start=1):
        source_lines.extend(
            [
                f"- source_id: source_{index}",
                f"  source_name: {source.source_name}",
                f"  definition: {source.raw_definition}",
            ]
        )
    return (
        f"{prompt_template}\n\n"
        "Input:\n"
        f"term: {term}\n"
        f"{'\n'.join(source_lines)}\n\n"
        'Return JSON with keys "decision", "recommended_definition", and "representative_source_id".'
    )


def build_term_augmentation_prompt(
    seed_terms: list[CleanedTerm],
    existing_samples: list[CleanedTerm],
    target_categories: list[str],
    max_extra_terms_per_category: int = 5,
    prompt_path: str | Path = "prompts/term_augmentation.md",
) -> str:
    prompt_template = Path(prompt_path).read_text(encoding="utf-8")
    seed_lines = _term_input_lines("seed_terms", seed_terms)
    sample_lines = _term_input_lines("existing_samples", existing_samples)
    return (
        f"{prompt_template}\n\n"
        "Input:\n"
        f"target_categories: {target_categories}\n"
        f"max_extra_terms_per_category: {max_extra_terms_per_category}\n"
        f"{seed_lines}\n"
        f"{sample_lines}\n\n"
        'Return JSON with key "terms".'
    )


def _term_input_lines(label: str, terms: list[CleanedTerm]) -> str:
    lines = [f"{label}:"]
    for term in terms:
        lines.extend(
            [
                f"- term: {term.term}",
                f"  aliases: {term.aliases}",
                f"  category: {term.category}",
                f"  definition: {term.definition}",
            ]
        )
    return "\n".join(lines)


def rewrite_definition_with_llm(
    term: CleanedTerm,
    llm=None,
    runner: LLMJsonRunner | None = None,
) -> tuple[CleanedTerm | None, ReviewRequiredTerm | None]:
    fallback_llm = None
    if llm is None:
        llm = init_dictionary_llm(task="definition_rewrite")
        fallback_llm = init_fallback_dictionary_llm(task="definition_rewrite")
    runner = runner or LLMJsonRunner()
    prompt = build_definition_prompt(term)

    def invoke(_: int) -> str:
        try:
            return _invoke_llm(llm, prompt)
        except Exception:
            if fallback_llm is None:
                raise
            return _invoke_llm(fallback_llm, prompt)

    result, review = runner.run(
        DefinitionRewriteOutput,
        invoke,
        review_context={
            "term": term.term,
            "aliases": term.aliases,
            "category": term.category,
            "source_name": term.source_name,
            "source_url": term.source_url,
        },
    )
    if result is None:
        return None, review
    if result.decision == "uncertain":
        return None, ReviewRequiredTerm(
            term=term.term,
            aliases=term.aliases,
            category=term.category,
            reason="llm_definition_uncertain",
            source_name=term.source_name,
            source_url=term.source_url,
            notes="definition_rewrite returned uncertain decision",
        )
    return term.model_copy(update={"definition": result.definition}), None


def augment_terms_with_llm(
    seed_terms: list[CleanedTerm],
    existing_samples: list[CleanedTerm],
    target_categories: list[str],
    max_extra_terms_per_category: int = 5,
    llm=None,
    runner: LLMJsonRunner | None = None,
) -> tuple[list[CleanedTerm] | None, ReviewRequiredTerm | None]:
    fallback_llm = None
    if llm is None:
        llm = init_dictionary_llm(task="term_augmentation")
        fallback_llm = init_fallback_dictionary_llm(task="term_augmentation")
    runner = runner or LLMJsonRunner()
    prompt = build_term_augmentation_prompt(
        seed_terms=seed_terms,
        existing_samples=existing_samples,
        target_categories=target_categories,
        max_extra_terms_per_category=max_extra_terms_per_category,
    )

    def invoke(_: int) -> str:
        try:
            return _invoke_llm(llm, prompt)
        except Exception:
            if fallback_llm is None:
                raise
            return _invoke_llm(fallback_llm, prompt)

    result, review = runner.run(
        TermAugmentationOutput,
        invoke,
        review_context={
            "term": "term_augmentation",
            "aliases": [],
            "category": "주식 기초",
            "source_name": PROJECT_SOURCE_NAME,
            "source_url": PROJECT_SOURCE_URL,
        },
    )
    if result is None:
        return None, review
    return [
        CleanedTerm(
            term=term.term,
            aliases=term.aliases,
            category=term.category,
            definition=term.definition,
            source_name=PROJECT_SOURCE_NAME,
            source_url=PROJECT_SOURCE_URL,
        )
        for term in result.terms
    ], None


def judge_duplicate_alias_with_llm(
    candidates: list[CleanedTerm],
    llm=None,
    runner: LLMJsonRunner | None = None,
) -> tuple[DuplicateAliasJudgmentOutput | None, ReviewRequiredTerm | None]:
    fallback_llm = None
    if llm is None:
        llm = init_dictionary_llm(task="duplicate_alias_judgment")
        fallback_llm = init_fallback_dictionary_llm(task="duplicate_alias_judgment")
    runner = runner or LLMJsonRunner()
    prompt = build_duplicate_alias_prompt(candidates)

    def invoke(_: int) -> str:
        try:
            return _invoke_llm(llm, prompt)
        except Exception:
            if fallback_llm is None:
                raise
            return _invoke_llm(fallback_llm, prompt)

    review_context = {
        "term": " | ".join(candidate.term for candidate in candidates),
        "aliases": [],
        "category": candidates[0].category if candidates else "기타",
        "source_name": "multiple",
        "source_url": "multiple",
    }
    result, review = runner.run(DuplicateAliasJudgmentOutput, invoke, review_context=review_context)
    if result is None:
        return None, review
    if result.decision == "uncertain":
        return result, ReviewRequiredTerm(
            term=review_context["term"],
            aliases=[],
            category=review_context["category"],
            reason="llm_duplicate_alias_uncertain",
            source_name="multiple",
            source_url="multiple",
            notes="duplicate_alias_judgment returned uncertain decision",
        )
    return result, None


def resolve_source_conflict_with_llm(
    term: str,
    sources: list[RawTerm],
    category: str = "기타",
    llm=None,
    runner: LLMJsonRunner | None = None,
) -> tuple[SourceConflictResolutionOutput | None, ReviewRequiredTerm | None]:
    fallback_llm = None
    if llm is None:
        llm = init_dictionary_llm(task="source_conflict_resolution")
        fallback_llm = init_fallback_dictionary_llm(task="source_conflict_resolution")
    runner = runner or LLMJsonRunner()
    prompt = build_source_conflict_prompt(term, sources)

    def invoke(_: int) -> str:
        try:
            return _invoke_llm(llm, prompt)
        except Exception:
            if fallback_llm is None:
                raise
            return _invoke_llm(fallback_llm, prompt)

    review_context = {
        "term": term,
        "aliases": [],
        "category": category,
        "source_name": "multiple",
        "source_url": "multiple",
    }
    result, review = runner.run(SourceConflictResolutionOutput, invoke, review_context=review_context)
    if result is None:
        return None, review
    if result.decision == "uncertain":
        return result, ReviewRequiredTerm(
            term=term,
            aliases=[],
            category=category,
            reason="llm_source_conflict_uncertain",
            source_name="multiple",
            source_url="multiple",
            notes="source_conflict_resolution returned uncertain decision",
        )
    return result, None


def assign_category_with_llm(
    term: CleanedTerm,
    llm=None,
    runner: LLMJsonRunner | None = None,
) -> tuple[CleanedTerm | None, ReviewRequiredTerm | None]:
    fallback_llm = None
    if llm is None:
        llm = init_dictionary_llm(task="category_assignment")
        fallback_llm = init_fallback_dictionary_llm(task="category_assignment")
    runner = runner or LLMJsonRunner()
    prompt = build_category_assignment_prompt(term)

    def invoke(_: int) -> str:
        try:
            return _invoke_llm(llm, prompt)
        except Exception:
            if fallback_llm is None:
                raise
            return _invoke_llm(fallback_llm, prompt)

    result, review = runner.run(
        CategoryAssignmentOutput,
        invoke,
        review_context={
            "term": term.term,
            "aliases": term.aliases,
            "category": term.category,
            "source_name": term.source_name,
            "source_url": term.source_url,
        },
    )
    if result is None:
        return None, review
    return term.model_copy(update={"category": result.category}), None
