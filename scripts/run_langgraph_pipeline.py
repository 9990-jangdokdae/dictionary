from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from stock_dictionary.graph_pipeline import PipelineMode, build_dictionary_pipeline_graph


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["full", "term_augmentation_only", "augmented_definition_rewrite_only", "build_only"],
        default="full",
    )
    parser.add_argument("--parallelism", type=int, default=10)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--samples-dir", default="data/llm_full")
    parser.add_argument("--raw-csv", default=None)
    parser.add_argument("--seed-csv", default=None)
    parser.add_argument("--max-extra-terms-per-category", type=int, default=5)
    parser.add_argument("--existing-sample-per-category", type=int, default=10)
    args = parser.parse_args()

    load_dotenv()
    graph = build_dictionary_pipeline_graph()
    result = graph.invoke(
        {
            "mode": args.mode,
            "parallelism": args.parallelism,
            "limit": args.limit,
            "data_dir": args.data_dir,
            "output_dir": args.output_dir,
            "samples_dir": args.samples_dir,
            "raw_csv": args.raw_csv or "",
            "seed_csv": args.seed_csv or "",
            "max_extra_terms_per_category": args.max_extra_terms_per_category,
            "existing_sample_per_category": args.existing_sample_per_category,
            "logs": [],
        }
    )
    for log in result.get("logs", []):
        print(log)
    if "final_terms" in result:
        print(f"final_terms={result['final_terms']} output_dir={args.output_dir}")


if __name__ == "__main__":
    main()
