import argparse
import json
import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas.testset import TestsetGenerator
from ragas.testset.transforms.splitters.headline import num_tokens_from_string


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.config import settings
from app.confluence.client import ConfluenceClient
from app.processing.normalize import parse_confluence_page


DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "resources" / "datasets" / "generated_cases.jsonl"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a RAGAS testset from Confluence data")
    parser.add_argument("--space-id", required=True, help="Confluence space ID to read pages from")
    parser.add_argument("--testset-size", type=int, default=20, help="Number of test cases to generate")
    parser.add_argument("--page-limit", type=int, default=None, help="Optional page limit for source documents")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Output JSONL file for generated cases",
    )
    parser.add_argument(
        "--generator-model",
        default=settings.openai_model,
        help="LLM used by RAGAS to synthesize test cases",
    )
    parser.add_argument(
        "--embedding-model",
        default=settings.embedding_model,
        help="Embedding model used by RAGAS during generation",
    )
    parser.add_argument(
        "--min-chars",
        type=int,
        default=120,
        help="Minimum page length to keep as generation source material",
    )
    return parser.parse_args()


def _is_usable_document(document, min_chars: int) -> bool:
    text = " ".join(document.page_content.split())
    alpha_count = sum(1 for char in text if char.isalpha())
    return len(text) >= min_chars and alpha_count >= 20


def _select_ragas_compatible_documents(documents: list[Document]) -> list[Document]:
    medium_or_long_documents: list[Document] = []
    long_documents: list[Document] = []

    for document in documents:
        token_count = num_tokens_from_string(document.page_content)
        if token_count > 100:
            medium_or_long_documents.append(document)
        if token_count > 500:
            long_documents.append(document)

    if not medium_or_long_documents:
        raise ValueError("No source documents longer than 100 tokens found for RAGAS generation")

    long_ratio = len(long_documents) / len(medium_or_long_documents)
    if 0 < long_ratio >= 0.25 and len(long_documents) < len(medium_or_long_documents):
        return long_documents

    return medium_or_long_documents


def _build_source_documents(space_id: str, page_limit: int | None, min_chars: int) -> list:
    client = ConfluenceClient(
        base_url=settings.confluence_base_url,
        api_token=settings.confluence_api_key,
    )
    pages = client.get_pages_by_space_id(space_id=space_id, limit=page_limit)
    parsed_documents = [parse_confluence_page(page) for page in pages]
    documents = [
        Document(
            page_content=parsed_document.text,
            metadata={
                "doc_id": parsed_document.doc_id,
                "title": parsed_document.title,
                **parsed_document.metadata,
            },
        )
        for parsed_document in parsed_documents
    ]
    filtered_documents = [doc for doc in documents if _is_usable_document(doc, min_chars=min_chars)]
    filtered_documents = _select_ragas_compatible_documents(filtered_documents)

    if not filtered_documents:
        raise ValueError("No usable source documents found after filtering")

    return filtered_documents


def _to_case_payload(sample: dict) -> dict[str, str]:
    question = str(sample.get("user_input") or "").strip()
    reference_answer = str(sample.get("reference") or sample.get("response") or "").strip()

    if not question:
        raise ValueError("Generated sample is missing user_input")

    payload = {"question": question}
    if reference_answer:
        payload["reference_answer"] = reference_answer
    return payload


def main() -> int:
    args = _parse_args()
    documents = _build_source_documents(
        space_id=args.space_id,
        page_limit=args.page_limit,
        min_chars=args.min_chars,
    )

    generator_llm = ChatOpenAI(
        model=args.generator_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    generator_embeddings = OpenAIEmbeddings(
        model=args.embedding_model,
        api_key=settings.openai_api_key,
    )
    generator = TestsetGenerator.from_langchain(generator_llm, generator_embeddings)
    testset = generator.generate_with_langchain_docs(
        documents=documents,
        testset_size=args.testset_size,
    )

    cases = [_to_case_payload(sample) for sample in testset.to_list()]
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with args.output.open("w", encoding="utf-8") as file:
        for case in cases:
            file.write(json.dumps(case, ensure_ascii=False) + "\n")

    print(f"Generated {len(cases)} cases from {len(documents)} source pages.")
    print(f"Saved dataset to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
