from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from scripts.build_final_artifacts import build_final_artifacts
from scripts.run_llm_samples import (
    generate_duplicate_alias_candidate_groups,
    generate_source_conflict_groups,
    load_cleaned_terms,
    load_raw_terms,
    load_terms_from_raw_terms,
    run_category_assignment_samples,
    run_definition_rewrite_samples,
    run_duplicate_alias_samples,
    run_source_conflict_samples,
    run_term_augmentation_samples,
    write_category_assignment_outputs,
    write_duplicate_alias_results,
    write_review_terms,
    write_source_conflict_results,
)
from stock_dictionary.augmentation import load_term_augmentation_seed, normalize_augmented_terms
from stock_dictionary.preprocess import write_cleaned_terms


PipelineMode = Literal[
    "full",
    "term_augmentation_only",
    "augmented_definition_rewrite_only",
    "build_only",
]


class DictionaryPipelineState(TypedDict, total=False):
    mode: PipelineMode
    data_dir: str
    output_dir: str
    samples_dir: str
    raw_csv: str
    seed_csv: str
    parallelism: int
    limit: int | None
    max_extra_terms_per_category: int
    existing_sample_per_category: int
    logs: Annotated[list[str], operator.add]
    final_terms: int


def build_dictionary_pipeline_graph():
    graph = StateGraph(DictionaryPipelineState)
    graph.add_node("category_assignment", category_assignment_node)
    graph.add_node("duplicate_alias_judgment", duplicate_alias_judgment_node)
    graph.add_node("definition_rewrite", definition_rewrite_node)
    graph.add_node("source_conflict_resolution", source_conflict_resolution_node)
    graph.add_node("term_augmentation", term_augmentation_node)
    graph.add_node("augmented_definition_rewrite", augmented_definition_rewrite_node)
    graph.add_node("build_final_artifacts", build_final_artifacts_node)

    graph.add_conditional_edges(
        START,
        route_start,
        {
            "category_assignment": "category_assignment",
            "term_augmentation": "term_augmentation",
            "augmented_definition_rewrite": "augmented_definition_rewrite",
            "build_final_artifacts": "build_final_artifacts",
        },
    )
    graph.add_edge("category_assignment", "duplicate_alias_judgment")
    graph.add_edge("duplicate_alias_judgment", "definition_rewrite")
    graph.add_edge("definition_rewrite", "source_conflict_resolution")
    graph.add_edge("source_conflict_resolution", "term_augmentation")
    graph.add_edge("term_augmentation", "augmented_definition_rewrite")
    graph.add_edge("augmented_definition_rewrite", "build_final_artifacts")
    graph.add_edge("build_final_artifacts", END)
    return graph.compile()


def route_start(state: DictionaryPipelineState) -> str:
    mode = state.get("mode", "full")
    if mode == "full":
        return "category_assignment"
    if mode == "term_augmentation_only":
        return "term_augmentation"
    if mode == "augmented_definition_rewrite_only":
        return "augmented_definition_rewrite"
    if mode == "build_only":
        return "build_final_artifacts"
    raise ValueError(f"unsupported pipeline mode: {mode}")


def category_assignment_node(state: DictionaryPipelineState) -> dict:
    data_dir = _data_dir(state)
    samples_dir = _samples_dir(state)
    rows = load_terms_from_raw_terms(data_dir / "raw_terms.csv")
    results, reviews = run_category_assignment_samples(
        rows,
        limit=state.get("limit"),
        parallelism=_parallelism(state),
    )
    included, excluded = write_category_assignment_outputs(samples_dir, results, reviews)
    return {
        "logs": [
            f"category_assignment results={len(included)} excluded={len(excluded)} reviews={len(reviews)}"
        ]
    }


def duplicate_alias_judgment_node(state: DictionaryPipelineState) -> dict:
    samples_dir = _samples_dir(state)
    rows = load_cleaned_terms(samples_dir / "category_assignment_results.csv")
    groups = generate_duplicate_alias_candidate_groups(rows)
    results, reviews = run_duplicate_alias_samples(groups, parallelism=_parallelism(state))
    write_duplicate_alias_results(samples_dir / "duplicate_alias_judgment_results.csv", results)
    write_review_terms(samples_dir / "duplicate_alias_judgment_review.csv", reviews)
    return {"logs": [f"duplicate_alias_judgment groups={len(groups)} results={len(results)} reviews={len(reviews)}"]}


def definition_rewrite_node(state: DictionaryPipelineState) -> dict:
    samples_dir = _samples_dir(state)
    rows = load_cleaned_terms(samples_dir / "category_assignment_results.csv")
    results, reviews = run_definition_rewrite_samples(rows, parallelism=_parallelism(state))
    write_cleaned_terms(samples_dir / "definition_rewrite_results.csv", results)
    write_review_terms(samples_dir / "definition_rewrite_review.csv", reviews)
    return {"logs": [f"definition_rewrite results={len(results)} reviews={len(reviews)}"]}


def source_conflict_resolution_node(state: DictionaryPipelineState) -> dict:
    data_dir = _data_dir(state)
    samples_dir = _samples_dir(state)
    raw_csv = Path(state.get("raw_csv") or data_dir / "raw_terms.csv")
    rows = load_cleaned_terms(samples_dir / "definition_rewrite_results.csv")
    groups = generate_source_conflict_groups(rows, load_raw_terms(raw_csv))
    results, reviews = run_source_conflict_samples(groups, parallelism=_parallelism(state))
    write_source_conflict_results(samples_dir / "source_conflict_resolution_results.csv", results)
    write_review_terms(samples_dir / "source_conflict_resolution_review.csv", reviews)
    return {"logs": [f"source_conflict_resolution groups={len(groups)} results={len(results)} reviews={len(reviews)}"]}


def term_augmentation_node(state: DictionaryPipelineState) -> dict:
    data_dir = _data_dir(state)
    samples_dir = _samples_dir(state)
    seed_csv = Path(state.get("seed_csv") or data_dir / "term_augmentation_seed.csv")
    existing_rows = load_cleaned_terms(samples_dir / "definition_rewrite_results.csv")
    seed_terms = load_term_augmentation_seed(seed_csv)
    raw_results, results, reviews = run_term_augmentation_samples(
        existing_rows,
        seed_terms,
        max_extra_terms_per_category=state.get("max_extra_terms_per_category", 5),
        existing_sample_per_category=state.get("existing_sample_per_category", 10),
    )
    write_cleaned_terms(samples_dir / "term_augmentation_raw.csv", normalize_augmented_terms(raw_results))
    write_cleaned_terms(samples_dir / "term_augmentation_results.csv", normalize_augmented_terms(results))
    write_review_terms(samples_dir / "term_augmentation_review.csv", reviews)
    return {"logs": [f"term_augmentation raw={len(raw_results)} results={len(results)} reviews={len(reviews)}"]}


def augmented_definition_rewrite_node(state: DictionaryPipelineState) -> dict:
    samples_dir = _samples_dir(state)
    rows = load_cleaned_terms(samples_dir / "term_augmentation_results.csv")
    result_path = samples_dir / "term_augmentation_definition_rewrite_results.csv"
    existing_results = load_cleaned_terms(result_path) if result_path.exists() else []
    existing_by_term = {term.term: term for term in normalize_augmented_terms(existing_results)}
    missing_rows = [row for row in rows if row.term not in existing_by_term]
    results, reviews = run_definition_rewrite_samples(missing_rows, parallelism=_parallelism(state)) if missing_rows else ([], [])
    for term in normalize_augmented_terms(results):
        existing_by_term[term.term] = term
    ordered_results = [existing_by_term[row.term] for row in rows if row.term in existing_by_term]
    write_cleaned_terms(result_path, ordered_results)
    write_review_terms(samples_dir / "term_augmentation_definition_rewrite_review.csv", reviews)
    return {
        "logs": [
            f"term_augmentation_definition_rewrite input={len(rows)} reused={len(existing_results)} "
            f"rewritten={len(results)} results={len(ordered_results)} reviews={len(reviews)}"
        ]
    }


def build_final_artifacts_node(state: DictionaryPipelineState) -> dict:
    terms = build_final_artifacts(
        data_dir=_data_dir(state),
        output_dir=_output_dir(state),
        samples_dir=_samples_dir(state),
        limit=state.get("limit"),
    )
    return {"final_terms": len(terms), "logs": [f"build_final_artifacts final_terms={len(terms)}"]}


def _data_dir(state: DictionaryPipelineState) -> Path:
    return Path(state.get("data_dir", "data"))


def _output_dir(state: DictionaryPipelineState) -> Path:
    return Path(state.get("output_dir", "output"))


def _samples_dir(state: DictionaryPipelineState) -> Path:
    return Path(state.get("samples_dir", "data/llm_full"))


def _parallelism(state: DictionaryPipelineState) -> int:
    parallelism = state.get("parallelism", 10)
    if parallelism < 1:
        raise ValueError("parallelism must be greater than 0")
    return parallelism
