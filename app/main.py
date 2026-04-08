from typing import List

from app.config import settings
from app.confluence.client import ConfluenceClient
from app.embeddings.indexing import IndexingService
from app.embeddings.retriever import RetrieverService
from app.processing.chunker import chunk_documents
from app.processing.models import ParsedDocument
from app.processing.normalize import parse_confluence_page

ICT_WIKI_SPACE = "720898"
TEST_PAGE_LIMIT = 5
TEST_QUERY = "Wie kann ich die VPN einrichten?"


def main():
    client = ConfluenceClient(base_url=settings.confluence_base_url, api_token=settings.confluence_api_key)
    pages = client.get_pages_by_space_id(space_id=ICT_WIKI_SPACE, limit=TEST_PAGE_LIMIT)
    documents: List[ParsedDocument] = []
    for page in pages:
        documents.append(parse_confluence_page(page))

    chunks = chunk_documents(documents)
    vectorstore = IndexingService().index_chunks(chunks)
    retriever = RetrieverService().get_retriever()
    matches = retriever.invoke(TEST_QUERY)

    print(f"Fetched pages: {len(pages)}")
    print(f"Built parsed documents: {len(documents)}")
    print(f"Built chunks: {len(chunks)}")
    print(f"Indexed documents: {vectorstore.index.ntotal}")
    print(f"Query: {TEST_QUERY}")

    for index, match in enumerate(matches, start=1):
        print("=" * 80)
        print(f"Match {index}")
        print(f"Title: {match.metadata.get('title')}")
        print(f"Chunk ID: {match.metadata.get('chunk_id')}")
        print(f"Heading Path: {' > '.join(match.metadata.get('heading_path', []))}")
        print(match.page_content)


if __name__ == "__main__":
    main()
