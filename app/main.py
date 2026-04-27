from typing import List

from app.config import settings
from app.confluence.client import ConfluenceClient
from app.embeddings.indexing import IndexingService
from app.embeddings.retriever import RetrieverService
from app.processing.chunker import chunk_documents
from app.processing.models import ParsedDocument
from app.processing.normalize import parse_confluence_page
from app.config import settings


ICT_WIKI_SPACE = "720898"
TEST_PAGE_LIMIT = 5 
TEST_QUERY = "Wie kann ich die VPN einrichten?"

# TODO: Move me to a /sync endpoint
def main():
    client = ConfluenceClient(base_url=settings.confluence_base_url, api_token=settings.confluence_api_key)
    pages = client.get_pages_by_space_id(space_id=ICT_WIKI_SPACE, limit=TEST_PAGE_LIMIT)
    documents: List[ParsedDocument] = []
    for page in pages:
        documents.append(parse_confluence_page(page))
        
    print(f"Fetched and parsed {len(documents)} pages.")
    chunks = chunk_documents(documents)
    print(f"Created {len(chunks)} chunks. Starting indexing...")
    
    indexing_service = IndexingService()
    indexing_service.index_chunks(chunks)
    print("Indexing completed!")

    from app.services.chat_service import ChatService
    chat_service = ChatService()
    result = chat_service.answer_question(TEST_QUERY)
    
    print("=" * 80)
    print(f"ANSWER:\n{result.answer}\n")
    print("SOURCES:")
    for src in result.sources:
        print(f"- {src.get('title')} | {src.get('url')}")
    print("=" * 80)


if __name__ == "__main__":
    main()
