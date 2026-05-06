import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from app.config import settings
from app.evaluation.constants import DEFAULT_RESULTS_DIR, DEFAULT_DATASET_PATH, ROOT_DIR
from app.evaluation.models import EvaluationCase, MetricSet


def _string_values(sources: list[dict[str, str | list[str] | None]], *, key: str) -> list[str]:
    """
    Gets the values from sources and cleans them.
    :param sources: the raw sources
    :param key: name of the source, for example "content"
    :return: a list of cleaned strings
    """
    values: list[str] = []
    for source in sources:
        value = source.get(key)
        if isinstance(value, str):
            stripped_value = value.strip()
            if stripped_value:
                values.append(stripped_value)
    return values


async def _score_case(case: EvaluationCase, result: Any, metrics: MetricSet) -> dict[str, float]:
    """
    Always tests faithfulness and answer relevancy
    and optionally does factual correctness, context precision and context recall if a reference answer is provided.
    :param case: the test case to be evaluated
    :param result: answer from chatbot
    :param metrics:
    :return: name & value/score of the metrics as a dict
    """
    metric_values = {
        "faithfulness": (
            await metrics.faithfulness.ascore(
                user_input=case.question,
                response=result.answer,
                retrieved_contexts=result.retrieved_contexts,
            )
        ).value,
        "answer_relevancy": (
            await metrics.answer_relevancy.ascore(
                user_input=case.question,
                response=result.answer,
            )
        ).value,
    }

    if case.reference_answer:
        metric_values["factual_correctness"] = (
            await metrics.factual_correctness.ascore(
                response=result.answer,
                reference=case.reference_answer,
            )
        ).value
        metric_values["context_precision"] = (
            await metrics.context_precision.ascore(
                user_input=case.question,
                reference=case.reference_answer,
                retrieved_contexts=result.retrieved_contexts,
            )
        ).value
        metric_values["context_recall"] = (
            await metrics.context_recall.ascore(
                user_input=case.question,
                retrieved_contexts=result.retrieved_contexts,
                reference=case.reference_answer,
            )
        ).value

    return {name: round(value, 4) for name, value in metric_values.items()}


def _summarize_results(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Build aggregate counts and metric summaries across all evaluated cases."""
    metric_names = sorted(
        {
            metric_name
            for case in case_results
            for metric_name in case.get("metrics", {}).keys()
        }
    )
    metric_summary = {
        metric_name: _metric_summary(metric_name, case_results) for metric_name in metric_names
    }
    error_count = sum(1 for case in case_results if case.get("error"))

    return {
        "total_cases": len(case_results),
        "successful_cases": len(case_results) - error_count,
        "failed_cases": error_count,
        "metrics": metric_summary
    }


def _metric_summary(metric_name: str, case_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Return count, average, min, and max for one metric across all cases."""
    values = [case["metrics"][metric_name] for case in case_results if metric_name in case.get("metrics", {})]
    if not values:
        return {"count": 0, "average": None, "minimum": None, "maximum": None}

    return {
        "count": len(values),
        "average": round(mean(values), 4),
        "minimum": round(min(values), 4),
        "maximum": round(max(values), 4),
    }


def _write_run_artifacts(payload: dict[str, Any], results_dir: Path) -> dict[str, str]:
    """Persist the full run payload plus a summary snapshot to disk."""
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_path = results_dir / f"ragas_eval_{timestamp}.json"
    latest_path = results_dir / "ragas_eval_latest.json"
    summary_path = results_dir / f"ragas_eval_{timestamp}_summary.json"

    serialized_payload = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    summary_payload = json.dumps(payload["summary"], ensure_ascii=False, indent=2) + "\n"

    run_path.write_text(serialized_payload, encoding="utf-8")
    latest_path.write_text(serialized_payload, encoding="utf-8")
    summary_path.write_text(summary_payload, encoding="utf-8")

    return {
        "run_path": str(run_path),
        "latest_path": str(latest_path),
        "summary_path": str(summary_path),
    }


def _git_revision() -> str | None:
    """Return the current git revision for traceability, if available."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT_DIR,
            text=True,
        ).strip()
    except Exception:
        return None


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the local evaluation runner."""
    parser = argparse.ArgumentParser(description="Run local RAGAS evaluation")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
        help="Path to a JSONL evaluation dataset",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Directory where evaluation artifacts are written",
    )
    parser.add_argument(
        "--judge-model",
        default="gpt-4.1-nano",
        help="LLM used by RAGAS to judge answers",
    )
    parser.add_argument(
        "--judge-embedding-model",
        default=settings.embedding_model,
        help="Embedding model used by RAGAS answer relevancy",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of cases to run from the dataset",
    )
    return parser.parse_args()
