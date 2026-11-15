#!/usr/bin/env python3
"""Validate, run, or summarize Delphic's fixed image evaluation set."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from images.evaluation import (  # noqa: E402
    ImageEvaluationError,
    build_blind_review_sheet,
    load_evaluation_cases,
    summarize_human_reviews,
)
from images.providers import (  # noqa: E402
    OpenRouterImageGenerationProvider,
    OpenRouterImageReviewProvider,
)
from images.service import generate_checked_image  # noqa: E402


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def validate_command(_args: argparse.Namespace) -> int:
    cases = load_evaluation_cases()
    allowed = sum(case["expected_safety"] == "allow" for case in cases)
    blocked = len(cases) - allowed
    print(f"Validated {len(cases)} cases: {allowed} allowed and {blocked} blocked locally.")
    return 0


def run_command(args: argparse.Namespace) -> int:
    if not args.live or not args.acknowledge_provider_terms:
        raise ImageEvaluationError(
            "A paid run requires both --live and --acknowledge-provider-terms."
        )
    if args.max_cost_usd <= 0:
        raise ImageEvaluationError("--max-cost-usd must be greater than zero.")
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ImageEvaluationError("Set OPENROUTER_API_KEY only for the approved evaluation run.")

    cases = [case for case in load_evaluation_cases() if case["expected_safety"] == "allow"]
    if args.case:
        cases = [case for case in cases if case["id"] in set(args.case)]
    cases = cases[: args.max_cases]
    if not cases:
        raise ImageEvaluationError("No allowed evaluation cases were selected.")

    output_dir = Path(args.output_dir).resolve()
    image_dir = output_dir / "blind-images"
    output_dir.mkdir(parents=True, exist_ok=False)
    image_dir.mkdir()
    generator = OpenRouterImageGenerationProvider(api_key)
    reviewer = OpenRouterImageReviewProvider(api_key)
    anonymous_ids: dict[str, str] = {}
    private_results = []
    total_cost = 0.0

    for case in cases:
        result = generate_checked_image(case["request"], generator, reviewer)
        case_cost = sum(
            (attempt.generation_cost_usd or 0.0) + (attempt.review_cost_usd or 0.0)
            for attempt in result.attempts
        )
        if any(
            attempt.generation_cost_usd is None or attempt.review_cost_usd is None
            for attempt in result.attempts
        ):
            raise ImageEvaluationError("The provider omitted cost data; stop before another paid case.")
        total_cost += case_cost
        if total_cost > args.max_cost_usd:
            raise ImageEvaluationError("The approved evaluation budget was exceeded; stop the run.")

        anonymous_id = uuid.uuid4().hex
        anonymous_ids[case["id"]] = anonymous_id
        (image_dir / f"{anonymous_id}.png").write_bytes(result.image.data)
        private_results.append({
            "case_id": case["id"],
            "anonymous_id": anonymous_id,
            "provider": result.image.provider,
            "generation_model": result.image.model,
            "review_model": reviewer.model_id,
            "attempt_count": result.attempt_count,
            "automated_review": {
                "passed": result.review.passed,
                "prompt_accuracy": result.review.prompt_accuracy,
                "scientific_accuracy": result.review.scientific_accuracy,
                "readability": result.review.readability,
                "safety_problem": result.review.safety_problem,
            },
            "cost_usd": round(case_cost, 6),
        })

    _write_json(output_dir / "human-review.json", build_blind_review_sheet(cases, anonymous_ids))
    _write_json(output_dir / "private-run-metadata.json", {
        "total_cost_usd": round(total_cost, 6),
        "results": private_results,
    })
    print(f"Created {len(cases)} blind review images in {output_dir}.")
    return 0


def summarize_command(args: argparse.Namespace) -> int:
    path = Path(args.review_sheet)
    try:
        review_sheet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ImageEvaluationError("The human review sheet could not be read.") from error
    summary = summarize_human_reviews(review_sheet)
    output_path = Path(args.output) if args.output else path.with_name("evaluation-summary.json")
    _write_json(output_path, summary)
    print(f"Wrote evaluation summary to {output_path}.")
    return 0 if summary["release_ready"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate every case without calling a provider.")

    run_parser = commands.add_parser("run", help="Run an explicitly approved paid evaluation.")
    run_parser.add_argument("--live", action="store_true")
    run_parser.add_argument("--acknowledge-provider-terms", action="store_true")
    run_parser.add_argument("--max-cost-usd", type=float, required=True)
    run_parser.add_argument("--max-cases", type=int, default=10)
    run_parser.add_argument("--case", action="append")
    run_parser.add_argument("--output-dir", required=True)

    summarize_parser = commands.add_parser("summarize", help="Check completed human scores.")
    summarize_parser.add_argument("review_sheet")
    summarize_parser.add_argument("--output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "validate":
            return validate_command(args)
        if args.command == "run":
            return run_command(args)
        return summarize_command(args)
    except ImageEvaluationError as error:
        print(f"Evaluation stopped: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
