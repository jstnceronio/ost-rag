import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from openai import AsyncOpenAI
from app.embeddings.factory import create_embeddings
from app.embeddings.retriever import RetrieverService
from ragas.embeddings.base import embedding_factory
from ragas.llms import llm_factory
from ragas.metrics.collections import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
    FactualCorrectness,
)

from app.config import settings
from app.evaluation.constants import DEFAULT_DATASET_PATH, DEFAULT_RESULTS_DIR
from app.evaluation.dataset import load_evaluation_cases
from app.evaluation.helpers import _parse_args, _summarize_results, _git_revision, _write_run_artifacts, _score_case, \
    _string_values
from app.evaluation.models import MetricSet, EvaluationCase, RunnerConfig, EvaluationResult
from app.services.helpers import _build_context, _document_to_source
from app.services.llm_service import LLMService


async def main() -> None:
    """
    Entry point for the evaluation runner.
    Takes the following arguments:
      *  dataset_path: Path to the dataset.
      *  results_dir: Path to the output directory.
      *  judge_model: Choose the judge model.
      *  judge_embedding_model: Choose the judge embedding model.
      *  case_limit: Limit the number of cases to evaluate.
    """
    args = _parse_args()
    config = RunnerConfig(
        dataset_path=args.dataset,
        results_dir=args.output_dir,
        judge_model=args.judge_model,
        judge_embedding_model=args.judge_embedding_model,
        case_limit=args.limit,
    )
    payload = await run_local_evaluation(config)
    # Log the results
    print(json.dumps(payload["summary"], indent=2))
    print(f"Saved evaluation run to: {payload['artifacts']['run_path']}")


async def run_local_evaluation(config: RunnerConfig) -> dict[str, Any]:
    """
    Runs the evaluation on the local machine.
    If you have FAISS configured it will take the existing index from data/faiss_index.
    Otherwise, the remote Supabase embeddings are used.
    :param config: that can be configured via args
    :return:
    """
    cases = load_evaluation_cases(config.dataset_path)
    if config.case_limit is not None:
        cases = cases[: config.case_limit]

    retriever = RetrieverService().get_retriever()
    llm_service = LLMService()
    embeddings = create_embeddings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    judge_llm = llm_factory(config.judge_model, client=client)
    judge_embeddings = embedding_factory(
        "openai",
        model=config.judge_embedding_model,
        client=AsyncOpenAI(api_key=settings.openai_api_key),
    )
    metrics = MetricSet(
        faithfulness=Faithfulness(llm=judge_llm),
        answer_relevancy=AnswerRelevancy(llm=judge_llm, embeddings=judge_embeddings),
        factual_correctness=FactualCorrectness(llm=judge_llm),
        context_precision=ContextPrecision(llm=judge_llm),
        context_recall=ContextRecall(llm=judge_llm),
    )

    started_at = datetime.now(UTC)
    case_results: list[dict[str, Any]] = []
    for case in cases:
        case_results.append(
            await _evaluate_case(
                case,
                retriever=retriever,
                llm_service=llm_service,
                embeddings=embeddings,
                metrics=metrics,
            )
        )
    completed_at = datetime.now(UTC)

    payload = {
        "metadata": {
            "started_at_utc": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "completed_at_utc": completed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dataset_path": str(config.dataset_path),
            "dataset_case_count": len(cases),
            "judge_model": config.judge_model,
            "judge_embedding_model": config.judge_embedding_model,
            "answer_model": settings.openai_model,
            "git_revision": _git_revision(),
        },
        "summary": _summarize_results(case_results),
        "cases": case_results,
    }
    payload["artifacts"] = _write_run_artifacts(payload, config.results_dir)
    return payload


async def _evaluate_case(case: EvaluationCase, *, retriever: Any, llm_service: LLMService, embeddings: Any, metrics: MetricSet) -> dict[str, Any]:
    started_at = datetime.now(UTC)

    try:
        result = _answer_question(
            case.question,
            retriever=retriever,
            llm_service=llm_service,
            embeddings=embeddings,
        )
        metric_values = await _score_case(case, result, metrics)
        error = None
    except Exception as exc:
        result = None
        metric_values = {}
        error = str(exc)

    completed_at = datetime.now(UTC)
    latency_ms = int((completed_at - started_at).total_seconds() * 1000)

    case_payload = asdict(case)
    case_payload.update(
        {
            "answer": result.answer if result is not None else None,
            "retrieved_context_count": len(result.retrieved_contexts) if result is not None else 0,
            "retrieved_contexts": result.retrieved_contexts if result is not None else [],
            "retrieved_doc_ids": result.retrieved_doc_ids if result is not None else [],
            "retrieved_chunk_ids": result.retrieved_chunk_ids if result is not None else [],
            "sources": result.sources if result is not None else [],
            "latency_ms": latency_ms,
            "metrics": metric_values,
            "error": error,
        }
    )
    return case_payload


def _answer_question(question: str, *, retriever: Any, llm_service: LLMService, embeddings: Any) -> EvaluationResult:
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ValueError("Frage darf nicht leer sein")

    embeddings.embed_query(cleaned_question)
    matches = retriever.invoke(cleaned_question)
    context = _build_context(matches)
    answer = llm_service.generate_answer(question=cleaned_question, context=context)
    raw_sources = [_document_to_source(match) for match in matches]

    seen_doc_ids: set[str] = set()
    sources = [
        _document_to_source(match)
        for match in matches
        if not (doc_id := match.metadata.get("doc_id"))
        or (doc_id not in seen_doc_ids and not seen_doc_ids.add(doc_id))
    ]

    return EvaluationResult(
        answer=answer,
        sources=sources,
        retrieved_contexts=_string_values(raw_sources, key="content"),
        retrieved_chunk_ids=_string_values(raw_sources, key="chunk_id"),
        retrieved_doc_ids=_string_values(raw_sources, key="doc_id"),
    )


if __name__ == "__main__":
    asyncio.run(main())
