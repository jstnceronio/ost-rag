from dataclasses import dataclass
from pathlib import Path

from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
    FactualCorrectness,
)


@dataclass(frozen=True)
class EvaluationCase:
    question: str
    reference_answer: str | None = None


@dataclass(frozen=True)
class EvaluationResult:
    answer: str
    sources: list[dict[str, str | list[str] | None]]
    retrieved_contexts: list[str]
    retrieved_chunk_ids: list[str]
    retrieved_doc_ids: list[str]


@dataclass(frozen=True)
class MetricSet:
    faithfulness: Faithfulness
    answer_relevancy: AnswerRelevancy
    factual_correctness: FactualCorrectness
    context_precision: ContextPrecision
    context_recall: ContextRecall


@dataclass(frozen=True)
class RunnerConfig:
    dataset_path: Path
    results_dir: Path
    judge_model: str
    judge_embedding_model: str
    case_limit: int | None