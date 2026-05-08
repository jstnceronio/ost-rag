# Chunking Process

This document explains how Confluence content becomes searchable chunks for the RAG bot. It covers both Confluence page bodies and supported attachments, because both are now indexed through the same final chunking and embedding path.

The main implementation files are:

- `app/services/sync_service.py`: orchestrates page and attachment sync.
- `app/confluence/client.py`: fetches pages, lists attachments, and downloads attachment bytes.
- `app/confluence/mapper.py`: maps Confluence API payloads into local dataclasses.
- `app/processing/normalize.py`: parses Confluence page HTML into normalized text sections.
- `app/processing/attachments.py`: extracts text from supported attachment files.
- `app/processing/chunker.py`: splits parsed documents into retrievable chunks.
- `app/processing/mapper.py`: converts chunks into LangChain `Document` objects.
- `app/embeddings/indexing.py` and `app/embeddings/vector_store.py`: embed and store chunks.
- `app/embeddings/retriever.py`: retrieves relevant chunks at question time.
- `app/reranking/reranker.py`: optionally reranks retrieved chunks before answer generation.

## End-To-End Flow

Sync starts in `run_sync`:

```python
if page_id:
    pages = client.get_page_tree(page_id=page_id, limit=limit)
else:
    pages = client.get_pages_by_space_id(space_id=space_id or "", limit=limit)

documents = [parse_confluence_page(page) for page in pages]
attachments = client.get_attachments_for_pages(pages)
documents.extend(
    doc
    for attachment in attachments
    if (doc := parse_confluence_attachment(attachment)) is not None
)

chunks = chunk_documents(documents)
IndexingService().index_chunks(chunks)
```

The pipeline is:

1. Fetch Confluence pages.
2. Parse every page into a `ParsedDocument`.
3. List and download attachments for those pages.
4. Parse every supported attachment into a `ParsedDocument`.
5. Skip unsupported attachments.
6. Split all parsed documents into `Chunk` objects.
7. Convert chunks to LangChain `Document` objects.
8. Embed and upsert them into the configured vector store.
9. Retrieve the most similar chunks when answering a question.
10. Optionally rerank retrieved chunks with the LLM and keep only the top supported chunks for the answer context.

The chunker itself does not call Confluence, parse HTML, download files, create embeddings, or query the vector store. It receives normalized `ParsedDocument` objects and returns `Chunk` objects.

## Source Models

Pages are represented as `ConfluencePage`:

```python
@dataclass
class ConfluencePage:
    id: str
    title: str
    space_id: str | None
    parent_id: str | None
    status: str | None
    url: str | None
    body_storage: str
    version: int | None
    created_at: datetime | None
    updated_at: datetime | None
```

Attachments are represented as `ConfluenceAttachment`:

```python
@dataclass
class ConfluenceAttachment:
    id: str
    title: str
    page_id: str
    page_title: str
    media_type: str | None
    file_size: int | None
    url: str | None
    download_url: str | None
    version: int | None
    created_at: datetime | None
    updated_at: datetime | None
    content: bytes
```

Both source types are converted into the same intermediate model:

```python
@dataclass
class ParsedDocument:
    doc_id: str
    title: str
    url: str | None
    text: str
    sections: list[tuple[list[str], str]]
    metadata: dict
```

This shared model is what lets pages and attachments use the same chunking, mapping, indexing, and retrieval code.

## Page Parsing

`parse_confluence_page` handles Confluence storage-format HTML. It uses `HTMLParser` to normalize common page structures:

- headings: `h1` through `h6`
- paragraphs and divs: `p`, `div`
- line breaks: `br`
- lists: `ul`, `ol`, `li`
- code blocks: `pre`
- tables: `table`, `tr`, `th`, `td`

The parser maintains a `heading_stack`. When text is parsed under a heading, that heading path is attached to the section block.

For example:

```html
<h2>KI und Leistungsnachweise</h2>
<h3>Einführung</h3>
<p>Der Einsatz von KI soll transparent geregelt werden.</p>
```

becomes a section like:

```python
(
    ["KI und Leistungsnachweise", "Einführung"],
    "Der Einsatz von KI soll transparent geregelt werden.",
)
```

The parser also creates full document text:

```python
text_parts = [f"# {page.title}"]
text_parts.extend(block for block in parser.blocks if block)
text = "\n\n".join(text_parts).strip()
```

The chunker prefers `sections`. The full `text` field is used only when no sections were produced.

Page metadata includes source attributes such as URL, space ID, parent ID, status, version, and timestamps. This metadata is not automatically embedded unless the chunker places parts of it into the chunk text.

## Attachment Loading

Attachments are loaded after pages are fetched. `get_page_attachments` calls:

```text
/rest/api/content/{page.id}/child/attachment
```

with:

```python
params={
    "limit": page_size,
    "start": start,
    "expand": "version,metadata",
}
```

The `metadata` expansion is important for Confluence v1 responses because it exposes fields such as `metadata.mediaType`. The mapper also supports Confluence Cloud v2-style fields such as top-level `mediaType`, `fileSize`, `downloadLink`, and `webuiLink`.

Attachment downloads use:

```python
self.session.get(url, headers={"Accept": "*/*"}, timeout=60)
```

This overrides the JSON `Accept` header used for REST API calls, because attachment downloads return binary file content.

## Attachment Parsing

`parse_confluence_attachment` extracts text from supported attachment types and returns a `ParsedDocument`. If no text can be extracted, it returns `None`, and sync skips that attachment.

Supported attachment content:

- PDF files: `application/pdf` or `.pdf`, parsed with `pypdf`.
- DOCX files: OpenXML `.docx`, parsed by reading `word/document.xml`.
- JSON files: parsed and pretty-printed when valid.
- Text-like files: plain text, markdown, CSV, XML, YAML, SQL, logs, scripts, and similar text formats.

Unsupported examples:

- images
- binary files without a text extractor
- HTML attachments

HTML attachments are intentionally skipped. Confluence page HTML is still parsed by `parse_confluence_page`; uploaded `.html` files are not part of the supported attachment scope.

An attachment `ParsedDocument` uses a document ID that includes both the parent page and attachment ID:

```text
{page_id}:attachment:{attachment_id}
```

For example:

```text
670171635:attachment:670171636
```

Attachment metadata includes:

```python
{
    "source_type": "attachment",
    "url": attachment.url or attachment.download_url,
    "parent_id": attachment.page_id,
    "parent_title": attachment.page_title,
    "attachment_id": attachment.id,
    "media_type": attachment.media_type,
    "file_size": attachment.file_size,
    "version": attachment.version,
    "created_at": ...,
    "updated_at": ...,
}
```

The `source_type`, `parent_title`, and `media_type` fields are important later because the chunker uses them to build attachment-specific prefixes.

## Text Splitting

The low-level splitter is `chunk_text`:

```python
def chunk_text(text: str, max_chars: int = 1200, overlap: int = 200) -> list[str]:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks
```

This splitter is character-based, not token-based.

Before splitting, it collapses whitespace:

```python
text = " ".join(text.split())
```

That means:

- multiple spaces become one space
- newlines become spaces
- tabs become spaces
- blank lines disappear
- table, list, and code formatting is flattened inside the final embedded text

If the normalized text is at most `1200` characters, it creates one piece. If it is longer, it creates overlapping windows of `1200` characters with `200` characters of overlap.

With defaults:

```text
chunk 0: characters 0-1199
chunk 1: characters 1000-2199
chunk 2: characters 2000-3199
```

The overlap reduces boundary loss when a relevant sentence spans two chunks.

The splitter does not search for sentence, paragraph, heading, or word boundaries. It may cut through words or sentences.

## Chunk Prefixes

The vector store embeds only the chunk text. Metadata is stored alongside the vector, but metadata does not influence semantic similarity unless it is included in the text.

For that reason, every chunk gets a prefix that identifies the source.

### Page Prefix

For normal Confluence pages, `_prefix_parts` returns:

```python
[f"Page: {doc.title}"]
```

If the chunk has a heading path, the chunker adds:

```python
Section: {" > ".join(heading_path)}
```

Example:

```text
Page: KI und Leistungsnachweise
Section: Inhalt

Der Einsatz von Künstlicher Intelligenz an der OST ...
```

### Attachment Prefix

For attachments, `_prefix_parts` returns:

```python
[
    "Source type: Confluence attachment",
    f"Parent page: {parent_title}",
    f"Attachment: {doc.title}",
    f"Media type: {media_type}",
]
```

Example:

```text
Source type: Confluence attachment
Parent page: KI und Leistungsnachweise
Attachment: KI und Leistungsnachweise_20240916.pdf
Media type: application/pdf
Section: Attachment

Künstliche Intelligenzen in der Hochschullehre ...
```

This is necessary because a user often asks about the Confluence page title while the detailed content lives in a PDF attachment. Repeating the parent page and attachment filename in every attachment chunk makes those chunks retrievable for title-based questions.

## Section-Based Chunking

When `doc.sections` exists, the chunker processes each section block independently:

```python
if doc.sections:
    for heading_path, section_text in doc.sections:
        prefix_parts = _prefix_parts(doc)
        if heading_path:
            prefix_parts.append(f"Section: {' > '.join(heading_path)}")
        prefix = "\n".join(prefix_parts) + "\n\n"

        for piece in chunk_text(section_text):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.doc_id}:chunk:{chunk_index}",
                    doc_id=doc.doc_id,
                    text=prefix + piece,
                    title=doc.title,
                    heading_path=heading_path,
                    metadata=doc.metadata,
                )
            )
            chunk_index += 1
```

This is the preferred path because it preserves heading context. A short section becomes one chunk. A long section becomes multiple overlapping chunks, each with the same prefix.

The chunker does not merge many small sections into larger chunks. This favors precise attribution over dense chunk packing.

## Full-Document Fallback

If `doc.sections` is empty, the chunker falls back to `doc.text`:

```python
else:
    for piece in chunk_text(doc.text):
        prefix = "\n".join(_prefix_parts(doc)) + "\n\n"
        chunks.append(
            Chunk(
                chunk_id=f"{doc.doc_id}:chunk:{chunk_index}",
                doc_id=doc.doc_id,
                text=prefix + piece,
                title=doc.title,
                heading_path=[],
                metadata=doc.metadata,
            )
        )
        chunk_index += 1
```

This keeps documents indexable even when no section blocks were parsed.

## Chunk IDs

Chunk IDs use:

```text
{doc_id}:chunk:{chunk_index}
```

For page chunks:

```text
670171635:chunk:0
670171635:chunk:1
```

For attachment chunks:

```text
670171635:attachment:670171636:chunk:0
670171635:attachment:670171636:chunk:1
```

The chunk index resets per parsed document. A page and each attachment have their own sequence.

The IDs are deterministic for a given parsed document shape, but they do not include content hashes or versions. If source content changes and the same chunk ID is upserted, the existing vector-store row is updated for Supabase.

## Output Model

The chunker returns `Chunk` objects:

```python
@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    text: str
    title: str
    heading_path: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
```

Important fields:

- `chunk_id`: unique chunk identifier within the indexed corpus.
- `doc_id`: source page ID or attachment document ID.
- `text`: exact text sent to the embedding model.
- `title`: page title or attachment filename.
- `heading_path`: structured section path for display and debugging.
- `metadata`: source attributes preserved for retrieval, source cards, and filtering.

## Mapping to LangChain Documents

`chunks_to_documents` converts chunks into LangChain documents:

```python
Document(
    page_content=chunk.text,
    metadata={
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "title": chunk.title,
        "heading_path": chunk.heading_path,
        **chunk.metadata,
    },
)
```

`page_content` is embedded. `metadata` is stored for attribution.

Because `chunk.metadata` is expanded last, source metadata can override standard fields if it reuses the same keys. Current page and attachment metadata avoid those conflicts.

## Indexing

`IndexingService.index_chunks` converts chunks to LangChain documents and calls `create_vector_store`.

For Supabase:

- Documents are batched.
- Texts are embedded with the configured embedding model.
- Rows are upserted into `settings.supabase_table_name`.
- Upsert conflict handling uses `chunk_id`.

Each row contains:

```python
{
    "content": doc.page_content,
    "metadata": doc.metadata,
    "embedding": vector,
}
```

For FAISS:

- Existing local indexes are loaded and appended to.
- New indexes are created if no index exists.
- The index is saved under `settings.faiss_index_path`.

## Retrieval And Reranking

At query time, `RetrieverService` creates a retriever:

```python
return vectorstore.as_retriever(
    search_type="similarity",
    search_kwargs={"k": 20},
)
```

The retriever returns the top 20 similar chunks. When `settings.reranker_enabled` is true, `ChatService` then passes those candidates to `RerankerService`.

The reranker asks the LLM to score every candidate for the user question and return strict JSON:

```json
{
  "results": [
    {
      "index": 0,
      "relevance": 0.91,
      "supports_answer": true,
      "reason": "enthält die gesuchten Module"
    }
  ]
}
```

Only results with `supports_answer=true` and valid indices are kept. Duplicate indices and out-of-range indices are ignored. The reranker stops at `settings.reranker_top_n`, which defaults to 5. If the LLM returns invalid JSON, the service falls back to the first `top_n` vector matches.

The final matched chunks are passed to `_build_context`, which renders each match as:

```text
Source 1
Title: ...
Document ID: ...
Chunk ID: ...
Heading Path: ...
Content: ...
```

The LLM is instructed to answer only from that context.

Source cards are built from the final matched document metadata after reranking. If an attachment chunk is retrieved and kept by the reranker, the source card should show a chunk ID like:

```text
670171635:attachment:670171636:chunk:3
```

If a source card only shows page chunks such as:

```text
670171635:chunk:1
```

then the final retrieval/reranking path did not use the attachment content for that answer.

## Complete Example

Assume Confluence page `670171635` has this visible page content:

```text
Title: KI und Leistungsnachweise
Section: Inhalt
Der Einsatz von Künstlicher Intelligenz an der OST soll durch alle,
die an der Lehre und der Weiterbildung beteiligt sind, getragen werden.
```

The same page has one PDF attachment:

```text
Attachment ID: 670171636
Filename: KI und Leistungsnachweise_20240916.pdf
Media type: application/pdf
Extracted text length: about 50,000 characters
```

After page parsing, the page becomes:

```python
ParsedDocument(
    doc_id="670171635",
    title="KI und Leistungsnachweise",
    sections=[
        (
            ["Inhalt"],
            "Der Einsatz von Künstlicher Intelligenz an der OST soll ..."
        )
    ],
    metadata={
        "url": "...",
        "space_id": "...",
        "parent_id": "...",
        "status": "current",
        "version": 1,
    },
)
```

The first page chunk looks like:

```text
chunk_id: 670171635:chunk:0
doc_id: 670171635
title: KI und Leistungsnachweise
heading_path: ["Inhalt"]

Page: KI und Leistungsnachweise
Section: Inhalt

Der Einsatz von Künstlicher Intelligenz an der OST soll ...
```

After PDF parsing, the attachment becomes:

```python
ParsedDocument(
    doc_id="670171635:attachment:670171636",
    title="KI und Leistungsnachweise_20240916.pdf",
    sections=[
        (
            ["Attachment"],
            "Attached to page: KI und Leistungsnachweise\n"
            "Filename: KI und Leistungsnachweise_20240916.pdf\n"
            "Media type: application/pdf\n\n"
            "Künstliche Intelligenzen in der Hochschullehre ..."
        )
    ],
    metadata={
        "source_type": "attachment",
        "parent_id": "670171635",
        "parent_title": "KI und Leistungsnachweise",
        "attachment_id": "670171636",
        "media_type": "application/pdf",
    },
)
```

Because the PDF text is long, `chunk_text` splits it into overlapping pieces. The first attachment chunk looks like:

```text
chunk_id: 670171635:attachment:670171636:chunk:0
doc_id: 670171635:attachment:670171636
title: KI und Leistungsnachweise_20240916.pdf
heading_path: ["Attachment"]

Source type: Confluence attachment
Parent page: KI und Leistungsnachweise
Attachment: KI und Leistungsnachweise_20240916.pdf
Media type: application/pdf
Section: Attachment

Attached to page: KI und Leistungsnachweise Filename: KI und Leistungsnachweise_20240916.pdf
Media type: application/pdf Künstliche Intelligenzen in der Hochschullehre
KI und Leistungsnachweise 16. September 2024 ...
```

A later attachment chunk may look like:

```text
chunk_id: 670171635:attachment:670171636:chunk:4
doc_id: 670171635:attachment:670171636
title: KI und Leistungsnachweise_20240916.pdf
heading_path: ["Attachment"]

Source type: Confluence attachment
Parent page: KI und Leistungsnachweise
Attachment: KI und Leistungsnachweise_20240916.pdf
Media type: application/pdf
Section: Attachment

... KI-Tools dürfen zur sprachlichen Überarbeitung genutzt werden,
sofern die fachliche Verantwortung bei der Autorin oder beim Autor bleibt ...
```

The important detail is that every PDF chunk repeats the parent page title and attachment filename. That makes a question such as:

```text
Was steht im Dokument KI und Leistungsnachweise?
```

capable of retrieving both the short Confluence page summary and the deeper PDF chunks.

If retrieval returns the attachment, the source card should include:

```text
Doc 670171635:attachment:670171636
Chunk 670171635:attachment:670171636:chunk:4
```

If retrieval only returns:

```text
Doc 670171635
Chunk 670171635:chunk:0
```

then the answer came from the Confluence page body, not the PDF.

## Design Tradeoffs

Strengths:

- One shared chunking path for pages and attachments.
- Deterministic chunk IDs.
- Page title is embedded in every page chunk.
- Parent page title and filename are embedded in every attachment chunk.
- Heading paths are preserved as both text and metadata.
- Long documents use overlap to reduce boundary loss.
- Supabase upserts on `chunk_id`, so repeated syncs update existing chunks.

Limitations:

- Splitting is character-based, not token-based.
- Chunks can split words or sentences.
- Whitespace is flattened before embedding.
- Small neighboring sections are not merged.
- Large PDFs are split without respecting PDF headings.
- Unsupported attachments are skipped silently by returning `None`.
- HTML attachments are not indexed.
- FAISS appends documents to an existing index and does not upsert by `chunk_id`.

## Operational Notes

After changing parsing, chunk prefixes, chunk sizes, or supported attachment types, rebuild or re-sync the affected content. Existing vectors keep the old text until they are re-indexed.

For a targeted page, re-sync the page tree that contains it. After sync, ask a question and inspect source cards:

- Page-only source: `670171635:chunk:n`
- Attachment source: `670171635:attachment:670171636:chunk:n`

When debugging retrieval quality:

1. Confirm the attachment is listed by Confluence.
2. Confirm the attachment downloads with nonzero bytes.
3. Confirm text extraction returns meaningful characters.
4. Confirm chunks were created with attachment IDs.
5. Confirm the vector store contains those chunk IDs.
6. Confirm retrieval returns attachment chunks for relevant questions.
7. If the chat answer still omits them, check whether reranking is filtering them out.

## Summary

The chunking process turns normalized page bodies and supported attachment text into retrievable semantic units. Pages are chunked with page and heading context. Attachments are chunked with source type, parent page title, filename, media type, and attachment section context. The resulting chunks are embedded and stored with metadata. At answer time, vector search retrieves broad candidates, optional reranking narrows them to supported chunks, and answers can cite either a Confluence page chunk or an attachment chunk.
