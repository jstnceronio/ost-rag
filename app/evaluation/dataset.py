import json
from pathlib import Path
from typing import Any

from app.evaluation.models import EvaluationCase


def load_evaluation_cases(path: Path) -> list[EvaluationCase]:
    """
    Load all evaluation cases from a file
    :param path: to the test_cases.jsonl file
    :return: EvaluationCases

    Note: Each entry in this file must contain a question and can have optional references
    """
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    cases: list[EvaluationCase] = []

    with path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                payload = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on line {line_number} of {path}: {error.msg}") from error

            if not isinstance(payload, dict):
                raise ValueError(f"Line {line_number} of {path} must contain a JSON object")

            cases.append(_parse_case(payload=payload, line_number=line_number))

    if not cases:
        raise ValueError(f"Evaluation dataset is empty: {path}")

    return cases


def _parse_case(payload: dict[str, Any], line_number: int) -> EvaluationCase:
    question = str(payload.get("question") or "").strip()
    # Reference is optional.
    reference_answer = str(payload.get("reference_answer") or payload.get("reference") or "").strip()

    if not question:
        raise ValueError(f"Line {line_number} contains an empty question")

    return EvaluationCase(
        question=question,
        reference_answer=reference_answer,
    )
