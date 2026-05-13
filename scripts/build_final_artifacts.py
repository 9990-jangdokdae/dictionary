from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stock_dictionary.exporters import build_sqlite, export_postgres_artifacts
from stock_dictionary.augmentation import merge_augmented_terms
from stock_dictionary.models import CleanedTerm, ReviewRequiredTerm
from stock_dictionary.preprocess import normalize_term_aliases, write_cleaned_terms


def build_final_artifacts(
    data_dir: str | Path = "data",
    output_dir: str | Path = "output",
    samples_dir: str | Path = "data/llm_samples",
    limit: int | None = None,
) -> list[CleanedTerm]:
    if limit is not None and limit < 1:
        raise ValueError("limit must be greater than 0")

    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    samples_dir = Path(samples_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    terms = _load_cleaned_terms(samples_dir / "definition_rewrite_results.csv")
    if limit is not None:
        terms = terms[:limit]
    terms = _apply_source_conflict_resolutions(terms, samples_dir / "source_conflict_resolution_results.csv")
    terms = _normalize_and_merge_aliases(terms)
    terms = _apply_term_augmentation(terms, samples_dir / "term_augmentation_results.csv", data_dir / "term_augmentation_merge_review.csv")
    terms = _normalize_and_merge_aliases(terms)

    write_cleaned_terms(data_dir / "cleaned_terms.csv", terms)
    build_sqlite(output_dir / "stock_dictionary.sqlite", terms)
    export_postgres_artifacts(output_dir, terms)
    return terms


def _load_cleaned_terms(path: Path) -> list[CleanedTerm]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return [CleanedTerm(**row) for row in csv.DictReader(f)]


def _normalize_aliases(term: CleanedTerm) -> CleanedTerm:
    normalized_term, aliases = normalize_term_aliases(term.term, term.aliases)
    return term.model_copy(update={"term": normalized_term, "aliases": aliases})


def _normalize_and_merge_aliases(terms: list[CleanedTerm]) -> list[CleanedTerm]:
    merged: dict[str, CleanedTerm] = {}
    for term in terms:
        normalized = _normalize_aliases(term)
        existing = merged.get(normalized.term)
        if existing is None:
            merged[normalized.term] = normalized
            continue
        aliases = [*existing.aliases]
        for alias in normalized.aliases:
            if alias not in aliases:
                aliases.append(alias)
        merged[normalized.term] = existing.model_copy(update={"aliases": aliases})
    return list(merged.values())


def _apply_source_conflict_resolutions(terms: list[CleanedTerm], path: Path) -> list[CleanedTerm]:
    if not path.exists():
        return terms
    with path.open("r", encoding="utf-8", newline="") as f:
        resolutions = {
            row["term"]: row
            for row in csv.DictReader(f)
            if row.get("decision") == "resolved" and row.get("recommended_definition", "").strip()
        }

    updated: list[CleanedTerm] = []
    for term in terms:
        resolution = resolutions.get(term.term)
        if not resolution:
            updated.append(term)
            continue
        update = {"definition": resolution["recommended_definition"]}
        if resolution.get("representative_source_name"):
            update["source_name"] = resolution["representative_source_name"]
        if resolution.get("representative_source_url"):
            update["source_url"] = resolution["representative_source_url"]
        updated.append(term.model_copy(update=update))
    return updated


def _apply_term_augmentation(
    terms: list[CleanedTerm],
    path: Path,
    review_path: Path,
) -> list[CleanedTerm]:
    if not path.exists():
        return terms
    augmented_terms = _load_cleaned_terms(path)
    merged, reviews = merge_augmented_terms(terms, augmented_terms)
    if reviews:
        _write_review_terms(review_path, reviews)
    elif review_path.exists():
        review_path.unlink()
    return merged


def _write_review_terms(path: Path, rows: list[ReviewRequiredTerm]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["term", "aliases", "category", "reason", "source_name", "source_url", "notes"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_csv_row())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--samples-dir", default="data/llm_samples")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    terms = build_final_artifacts(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        samples_dir=args.samples_dir,
        limit=args.limit,
    )
    print(f"final_terms={len(terms)} output_dir={args.output_dir}")


if __name__ == "__main__":
    main()
