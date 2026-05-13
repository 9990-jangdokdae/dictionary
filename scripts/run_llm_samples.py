from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from stock_dictionary.llm_pipeline import (
    DuplicateAliasJudgmentOutput,
    SourceConflictResolutionOutput,
    augment_terms_with_llm,
    assign_category_with_llm,
    judge_duplicate_alias_with_llm,
    resolve_source_conflict_with_llm,
    rewrite_definition_with_llm,
)
from stock_dictionary.models import CleanedTerm, RawTerm, ReviewRequiredTerm
from stock_dictionary.augmentation import (
    AUGMENTATION_TARGET_CATEGORIES,
    load_term_augmentation_seed,
    validate_augmented_terms,
)
from stock_dictionary.preprocess import apply_category_gate, clean_display_term, clean_raw_terms, normalize_term, write_cleaned_terms


CategoryAssigner = Callable[[CleanedTerm], tuple[CleanedTerm | None, ReviewRequiredTerm | None]]
DuplicateAliasJudger = Callable[[list[CleanedTerm]], tuple[DuplicateAliasJudgmentOutput | None, ReviewRequiredTerm | None]]
DefinitionRewriter = Callable[[CleanedTerm], tuple[CleanedTerm | None, ReviewRequiredTerm | None]]
TermAugmenter = Callable[
    [list[CleanedTerm], list[CleanedTerm], list[str], int],
    tuple[list[CleanedTerm] | None, ReviewRequiredTerm | None],
]
SourceConflictGroup = tuple[str, str, list[RawTerm]]
SourceConflictResolver = Callable[
    [str, list[RawTerm], str],
    tuple[SourceConflictResolutionOutput | None, ReviewRequiredTerm | None],
]


def run_category_assignment_samples(
    rows: list[CleanedTerm],
    limit: int | None = None,
    parallelism: int = 10,
    assigner: CategoryAssigner = assign_category_with_llm,
) -> tuple[list[CleanedTerm], list[ReviewRequiredTerm]]:
    selected = _limited_rows(rows, limit)
    if parallelism < 1:
        raise ValueError("parallelism must be greater than 0")

    results: list[CleanedTerm | None] = [None] * len(selected)
    reviews: list[tuple[int, ReviewRequiredTerm]] = []

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {executor.submit(assigner, row): (index, row) for index, row in enumerate(selected)}
        for future in as_completed(futures):
            index, row = futures[future]
            try:
                assigned, review = future.result()
            except Exception as exc:
                assigned = None
                review = ReviewRequiredTerm(
                    term=row.term,
                    aliases=row.aliases,
                    category=row.category,
                    reason="llm_sample_execution_failed",
                    source_name=row.source_name,
                    source_url=row.source_url,
                    notes=str(exc),
                )
            if assigned is not None:
                results[index] = assigned
            if review is not None:
                reviews.append((index, review))

    return [row for row in results if row is not None], [review for _, review in sorted(reviews, key=lambda item: item[0])]


def _limited_rows[T](rows: list[T], limit: int | None) -> list[T]:
    if limit is None:
        return rows
    if limit < 1:
        raise ValueError("limit must be greater than 0")
    return rows[:limit]


def _duplicate_candidate_key(term: str) -> str:
    without_parenthetical = re.sub(r"\([^()]*\)", "", term).strip()
    return normalize_term(without_parenthetical)


def generate_duplicate_alias_candidate_groups(rows: list[CleanedTerm]) -> list[list[CleanedTerm]]:
    grouped: dict[str, list[CleanedTerm]] = defaultdict(list)
    for row in rows:
        grouped[_duplicate_candidate_key(row.term)].append(row)
    return [group for _, group in sorted(grouped.items()) if len(group) > 1]


def run_duplicate_alias_samples(
    groups: list[list[CleanedTerm]],
    parallelism: int = 10,
    judger: DuplicateAliasJudger = judge_duplicate_alias_with_llm,
) -> tuple[list[dict[str, str]], list[ReviewRequiredTerm]]:
    if parallelism < 1:
        raise ValueError("parallelism must be greater than 0")

    results: list[dict[str, str] | None] = [None] * len(groups)
    reviews: list[tuple[int, ReviewRequiredTerm]] = []

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {executor.submit(judger, group): (index, group) for index, group in enumerate(groups)}
        for future in as_completed(futures):
            index, group = futures[future]
            try:
                result, review = future.result()
            except Exception as exc:
                result = None
                review = ReviewRequiredTerm(
                    term=" | ".join(row.term for row in group),
                    aliases=[],
                    category=group[0].category,
                    reason="llm_sample_execution_failed",
                    source_name="multiple",
                    source_url="multiple",
                    notes=str(exc),
                )
            if result is not None:
                results[index] = {
                    "candidate_terms": " | ".join(row.term for row in group),
                    "decision": result.decision,
                    "representative_term": result.representative_term,
                    "aliases": json.dumps(result.aliases, ensure_ascii=False),
                }
            if review is not None:
                reviews.append((index, review))

    return [row for row in results if row is not None], [review for _, review in sorted(reviews, key=lambda item: item[0])]


def run_definition_rewrite_samples(
    rows: list[CleanedTerm],
    parallelism: int = 10,
    rewriter: DefinitionRewriter = rewrite_definition_with_llm,
) -> tuple[list[CleanedTerm], list[ReviewRequiredTerm]]:
    if parallelism < 1:
        raise ValueError("parallelism must be greater than 0")

    results: list[CleanedTerm | None] = [None] * len(rows)
    reviews: list[tuple[int, ReviewRequiredTerm]] = []

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {executor.submit(rewriter, row): (index, row) for index, row in enumerate(rows)}
        for future in as_completed(futures):
            index, row = futures[future]
            try:
                rewritten, review = future.result()
            except Exception as exc:
                rewritten = None
                review = ReviewRequiredTerm(
                    term=row.term,
                    aliases=row.aliases,
                    category=row.category,
                    reason="llm_sample_execution_failed",
                    source_name=row.source_name,
                    source_url=row.source_url,
                    notes=str(exc),
                )
            if rewritten is not None:
                results[index] = rewritten
            if review is not None:
                reviews.append((index, review))

    return [row for row in results if row is not None], [review for _, review in sorted(reviews, key=lambda item: item[0])]


def select_existing_samples_by_category(
    rows: list[CleanedTerm],
    target_categories: list[str],
    per_category: int = 10,
) -> list[CleanedTerm]:
    selected: list[CleanedTerm] = []
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        if row.category not in target_categories:
            continue
        if counts[row.category] >= per_category:
            continue
        selected.append(row)
        counts[row.category] += 1
    return selected


def run_term_augmentation_samples(
    existing_rows: list[CleanedTerm],
    seed_terms: list[CleanedTerm],
    target_categories: list[str] = AUGMENTATION_TARGET_CATEGORIES,
    max_extra_terms_per_category: int = 5,
    existing_sample_per_category: int = 10,
    augmenter: TermAugmenter = augment_terms_with_llm,
) -> tuple[list[CleanedTerm], list[CleanedTerm], list[ReviewRequiredTerm]]:
    existing_samples = select_existing_samples_by_category(
        existing_rows,
        target_categories=target_categories,
        per_category=existing_sample_per_category,
    )
    raw_results, review = augmenter(seed_terms, existing_samples, target_categories, max_extra_terms_per_category)
    reviews = [review] if review is not None else []
    if raw_results is None:
        return [], [], reviews

    results, validation_reviews = validate_augmented_terms(raw_results, existing_rows)
    reviews.extend(validation_reviews)
    return raw_results, results, reviews


def generate_source_conflict_groups(cleaned_rows: list[CleanedTerm], raw_rows: list[RawTerm]) -> list[SourceConflictGroup]:
    raw_by_key: dict[str, list[RawTerm]] = defaultdict(list)
    for row in raw_rows:
        raw_by_key[normalize_term(clean_display_term(row.term))].append(row)

    groups: list[SourceConflictGroup] = []
    for cleaned in cleaned_rows:
        keys = {normalize_term(clean_display_term(cleaned.term))}
        keys.update(normalize_term(clean_display_term(alias)) for alias in cleaned.aliases)
        sources: list[RawTerm] = []
        seen_source_definitions: set[tuple[str, str]] = set()
        for key in sorted(keys):
            for raw in raw_by_key.get(key, []):
                source_definition = (raw.source_name, raw.raw_definition)
                if source_definition not in seen_source_definitions:
                    sources.append(raw)
                    seen_source_definitions.add(source_definition)
        unique_definitions = {source.raw_definition for source in sources}
        unique_sources = {source.source_name for source in sources}
        if len(sources) >= 2 and len(unique_sources) >= 2 and len(unique_definitions) >= 2:
            groups.append((cleaned.term, cleaned.category, sources))
    return groups


def _source_name_for_id(sources: list[RawTerm], source_id: str) -> str:
    source = _source_for_id(sources, source_id)
    return source.source_name if source else ""


def _source_url_for_id(sources: list[RawTerm], source_id: str) -> str:
    source = _source_for_id(sources, source_id)
    return source.source_url if source else ""


def _source_for_id(sources: list[RawTerm], source_id: str) -> RawTerm | None:
    match = re.fullmatch(r"source_(\d+)", source_id.strip())
    if not match:
        return None
    index = int(match.group(1)) - 1
    if index < 0 or index >= len(sources):
        return None
    return sources[index]


def run_source_conflict_samples(
    groups: list[SourceConflictGroup],
    parallelism: int = 10,
    resolver: SourceConflictResolver = resolve_source_conflict_with_llm,
) -> tuple[list[dict[str, str]], list[ReviewRequiredTerm]]:
    if parallelism < 1:
        raise ValueError("parallelism must be greater than 0")

    results: list[dict[str, str] | None] = [None] * len(groups)
    reviews: list[tuple[int, ReviewRequiredTerm]] = []

    with ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {executor.submit(resolver, term, sources, category): (index, term, category, sources) for index, (term, category, sources) in enumerate(groups)}
        for future in as_completed(futures):
            index, term, category, sources = futures[future]
            try:
                result, review = future.result()
            except Exception as exc:
                result = None
                review = ReviewRequiredTerm(
                    term=term,
                    aliases=[],
                    category=category,
                    reason="llm_sample_execution_failed",
                    source_name="multiple",
                    source_url="multiple",
                    notes=str(exc),
                )
            if result is not None:
                results[index] = {
                    "term": term,
                    "decision": result.decision,
                    "recommended_definition": result.recommended_definition,
                    "representative_source_id": result.representative_source_id,
                    "representative_source_name": _source_name_for_id(sources, result.representative_source_id),
                    "representative_source_url": _source_url_for_id(sources, result.representative_source_id),
                    "source_count": str(len(sources)),
                }
            if review is not None:
                reviews.append((index, review))

    return [row for row in results if row is not None], [review for _, review in sorted(reviews, key=lambda item: item[0])]


def load_terms_from_raw_terms(path: str | Path) -> list[CleanedTerm]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        raw_terms = [RawTerm(**row) for row in csv.DictReader(f)]
    return clean_raw_terms(raw_terms)


def write_review_terms(path: str | Path, rows: list[ReviewRequiredTerm]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["term", "aliases", "category", "reason", "source_name", "source_url", "notes"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def load_cleaned_terms(path: str | Path) -> list[CleanedTerm]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return [CleanedTerm(**row) for row in csv.DictReader(f)]


def load_raw_terms(path: str | Path) -> list[RawTerm]:
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        return [RawTerm(**row) for row in csv.DictReader(f)]


def write_duplicate_alias_results(path: str | Path, rows: list[dict[str, str]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["candidate_terms", "decision", "representative_term", "aliases"])
        writer.writeheader()
        writer.writerows(rows)


def write_source_conflict_results(path: str | Path, rows: list[dict[str, str]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "term",
                "decision",
                "recommended_definition",
                "representative_source_id",
                "representative_source_name",
                "representative_source_url",
                "source_count",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def write_category_assignment_outputs(
    output_dir: str | Path,
    results: list[CleanedTerm],
    reviews: list[ReviewRequiredTerm],
) -> tuple[list[CleanedTerm], list[ReviewRequiredTerm]]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    included, excluded = apply_category_gate(results)

    write_cleaned_terms(output_dir / "category_assignment_all.csv", results)
    write_cleaned_terms(output_dir / "category_assignment_results.csv", included)
    write_review_terms(output_dir / "category_assignment_excluded.csv", excluded)
    write_review_terms(output_dir / "category_assignment_review.csv", reviews)
    return included, excluded


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--task",
        choices=[
            "category_assignment",
            "duplicate_alias_judgment",
            "definition_rewrite",
            "source_conflict_resolution",
            "term_augmentation",
        ],
        default="category_assignment",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--parallelism", type=int, default=10)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="data/llm_samples")
    parser.add_argument("--input-csv", default=None)
    parser.add_argument("--raw-csv", default=None)
    parser.add_argument("--seed-csv", default=None)
    parser.add_argument("--max-extra-terms-per-category", type=int, default=5)
    parser.add_argument("--existing-sample-per-category", type=int, default=10)
    args = parser.parse_args()

    load_dotenv()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.task == "category_assignment":
        rows = load_terms_from_raw_terms(data_dir / "raw_terms.csv")
        results, reviews = run_category_assignment_samples(rows, limit=args.limit, parallelism=args.parallelism)
        included, excluded = write_category_assignment_outputs(output_dir, results, reviews)
        print(
            f"task={args.task} results={len(included)} excluded={len(excluded)} "
            f"reviews={len(reviews)} parallelism={args.parallelism}"
        )
        return

    default_input = output_dir / "definition_rewrite_results.csv" if args.task == "term_augmentation" else output_dir / "category_assignment_results.csv"
    input_csv = Path(args.input_csv) if args.input_csv else default_input
    rows = load_cleaned_terms(input_csv)

    if args.task == "duplicate_alias_judgment":
        selected_rows = _limited_rows(rows, args.limit)
        groups = generate_duplicate_alias_candidate_groups(selected_rows)
        results, reviews = run_duplicate_alias_samples(groups, parallelism=args.parallelism)
        write_duplicate_alias_results(output_dir / "duplicate_alias_judgment_results.csv", results)
        write_review_terms(output_dir / "duplicate_alias_judgment_review.csv", reviews)
        print(
            f"task={args.task} input_terms={len(selected_rows)} groups={len(groups)} "
            f"results={len(results)} reviews={len(reviews)} parallelism={args.parallelism}"
        )
        return

    if args.task == "source_conflict_resolution":
        raw_csv = Path(args.raw_csv) if args.raw_csv else data_dir / "raw_terms.csv"
        selected_rows = _limited_rows(rows, args.limit)
        groups = generate_source_conflict_groups(selected_rows, load_raw_terms(raw_csv))
        results, reviews = run_source_conflict_samples(groups, parallelism=args.parallelism)
        write_source_conflict_results(output_dir / "source_conflict_resolution_results.csv", results)
        write_review_terms(output_dir / "source_conflict_resolution_review.csv", reviews)
        print(
            f"task={args.task} input_terms={len(selected_rows)} groups={len(groups)} "
            f"results={len(results)} reviews={len(reviews)} parallelism={args.parallelism}"
        )
        return

    if args.task == "term_augmentation":
        seed_csv = Path(args.seed_csv) if args.seed_csv else data_dir / "term_augmentation_seed.csv"
        seed_terms = load_term_augmentation_seed(seed_csv)
        raw_results, results, reviews = run_term_augmentation_samples(
            rows,
            seed_terms,
            max_extra_terms_per_category=args.max_extra_terms_per_category,
            existing_sample_per_category=args.existing_sample_per_category,
        )
        write_cleaned_terms(output_dir / "term_augmentation_raw.csv", raw_results)
        write_cleaned_terms(output_dir / "term_augmentation_results.csv", results)
        write_review_terms(output_dir / "term_augmentation_review.csv", reviews)
        print(
            f"task={args.task} input_terms={len(rows)} seeds={len(seed_terms)} raw={len(raw_results)} "
            f"results={len(results)} reviews={len(reviews)} max_extra_terms_per_category={args.max_extra_terms_per_category}"
        )
        return

    selected = _limited_rows(rows, args.limit)
    results, reviews = run_definition_rewrite_samples(selected, parallelism=args.parallelism)
    write_cleaned_terms(output_dir / "definition_rewrite_results.csv", results)
    write_review_terms(output_dir / "definition_rewrite_review.csv", reviews)
    print(
        f"task={args.task} input_terms={len(selected)} results={len(results)} "
        f"reviews={len(reviews)} parallelism={args.parallelism}"
    )


if __name__ == "__main__":
    main()
