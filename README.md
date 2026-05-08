# Confluence RAG Bot

A production-ready Retrieval-Augmented Generation (RAG) backend that turns your Confluence wiki into an intelligent Q&A API. It fetches and indexes Confluence pages, stores embeddings in Supabase (or locally with FAISS), reranks retrieved chunks with an LLM, and answers natural-language questions using OpenAI. It is complete with conversation history, semantic caching, and API-key authentication.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Vector Store Providers](#vector-store-providers)
- [Running Locally](#running-locally)
- [Indexing](#indexing)
- [API Reference](#api-reference)
- [Security](#security)
- [Scripts](#scripts)
- [Project Structure](#project-structure)

---

## Architecture Overview

```
Confluence API
      │
      ▼
 ConfluenceClient          ← fetches pages via REST API
      │
      ▼
  Normalizer + Chunker     ← strips HTML, extracts headings, splits into chunks
      │
      ▼
 IndexingService           ← embeds chunks with text-embedding-3-small
      │
      ├──► Supabase (pgvector)   ← production vector store + semantic cache
      └──► FAISS (local)         ← lightweight local vector store
                │
                ▼
         RetrieverService        ← similarity search at query time
                │
                ▼
          RerankerService        ← optional LLM relevance filter, top N chunks
                │
                ▼
          LLMService             ← GPT-4.1 answers strictly from retrieved context
                │
                ▼
         FastAPI /chat           ← authenticated, rate-limited REST endpoint
```

---

## Features

| Feature | Details |
|---|---|
| **RAG Pipeline** | Confluence pages → HTML normalisation → semantic chunking → vector embeddings → similarity search → optional LLM reranking → answer generation |
| **Dual Vector Store** | Supabase (pgvector) for production, FAISS for local/offline use |
| **LLM Reranking** | Retrieved candidates are scored for question relevance and answer support; only the top reranked chunks are passed into the answer prompt |
| **Semantic Cache** | Identical or near-identical questions (≥ 0.98 cosine similarity) are served instantly from cache, with automatic cache invalidation when source pages are updated |
| **Langfuse Tracing** | Optional request, retrieval, reranking, cache, and LangChain LLM traces when Langfuse credentials are configured |
| **Conversation History** | Stateful multi-turn chat; history is injected into the prompt with structural delimiters. Cache is bypassed when history is present |
| **Prompt Injection Protection** | Context, questions, and history are each wrapped in explicit delimiters with system-level instructions that prevent the LLM from treating user content as directives |
| **`POST /sync` Endpoint** | Triggers an on-demand index of any Confluence space; upserts on `chunk_id` so it is safe to call repeatedly |
| **Daily Sync Scheduler** | Background async task that automatically re-indexes the configured space every morning at a configurable hour; runs inside the server process with no external dependencies |
| **API Key Auth** | `X-API-Key` header enforced on every request via constant-time HMAC comparison |
| **Rate Limiting** | `/chat` — 20 req/min, 300 req/day; `/sync` — 5 req/min, per IP (via SlowAPI) |
| **CORS** | Configurable allowed origins; only `POST` and required headers are permitted |

---

## Prerequisites

- Python ≥ 3.12
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`
- A Confluence instance with a valid API token
- An OpenAI API key
- **For production:** A Supabase project (cloud or self-hosted) with `pgvector` enabled

---

## Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd confluence-rag-bot

# Install dependencies with uv (recommended)
uv sync

# Or with pip
pip install -e .
```

---

## Configuration

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `CONFLUENCE_API_KEY` | Confluence personal access token |
| `CONFLUENCE_BASE_URL` | Base URL of your Confluence instance (e.g. `https://wiki.example.com/`) |
| `CONFLUENCE_SPACE_ID` | Space ID the daily scheduler syncs automatically |
| `SYNC_HOUR` | Hour (0–23, server local time) the daily sync fires — default `6` |
| `API_KEY` | Secret key clients must send in the `X-API-Key` header |
| `VECTOR_STORE_PROVIDER` | `supabase` or `faiss` |
| `SUPABASE_URL` | URL of your Supabase project |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |
| `SUPABASE_TABLE_NAME` | Table that stores document embeddings |
| `FAISS_INDEX_PATH` | Local path for the FAISS index (default: `./data/faiss_index`) |
| `RERANKER_ENABLED` | Enables the LLM reranker before answer generation (default: `true`) |
| `RERANKER_TOP_N` | Maximum number of reranked chunks passed to the answer prompt (default: `5`) |
| `LANGFUSE_ENABLED` | Enables Langfuse tracing when public and secret keys are also set (default: `false`) |
| `LANGFUSE_PUBLIC_KEY` | Langfuse project public key |
| `LANGFUSE_SECRET_KEY` | Langfuse project secret key |
| `LANGFUSE_BASE_URL` | Langfuse host URL, for example `https://cloud.langfuse.com` |
| `ALLOWED_CORS_ORIGINS` | Comma-separated allowed origins (default: `*`) |

---

## Vector Store Providers

### Supabase (Production)

1. Enable the `pgvector` extension in your Supabase project.
2. Create the documents table and the `match_documents` RPC function. Refer to your Supabase project's SQL editor and apply the required schema (vector column dimensions must match `text-embedding-3-small` → **1536**).
3. Set `VECTOR_STORE_PROVIDER=supabase` and provide the three `SUPABASE_*` variables.

### FAISS (Local / Offline)

1. Set `VECTOR_STORE_PROVIDER=faiss`.
2. Optionally set `FAISS_INDEX_PATH` to control where the index is persisted on disk.

The index is created on first run and loaded automatically on subsequent runs.

---

## Running Locally

```bash
# With uv
uv run uvicorn app.api.chat:app --reload --port 3000

# Or directly
uvicorn app.api.chat:app --reload --port 3000
```

The API will be available at `http://localhost:3000`.

---

## Indexing

### Daily Scheduler

At startup the server spawns a background task that sleeps until the next `SYNC_HOUR` and then runs a full index of `CONFLUENCE_SPACE_ID`. It logs the scheduled time once on startup and once when the sync completes — no periodic polling, no spam.

### `POST /sync` — On-Demand Indexing

To trigger an immediate sync without restarting the server:

```bash
curl -X POST http://localhost:3000/sync \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-api-key>" \
  -d '{"space_id": "720898"}'

# → {"pages_indexed": 42, "chunks_indexed": 317}
```

Pass an optional `limit` to index only the first N pages:

```bash
-d '{"space_id": "720898", "limit": 10}'
```

Chunks are upserted on `chunk_id`, so syncing the same space repeatedly is safe and idempotent.

---

## API Reference

### `POST /chat`

**Headers**

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `X-API-Key` | Your configured `API_KEY` |

**Request Body**

```json
{
  "question": "How do I set up VPN?",
  "history": [
    { "role": "user",      "content": "What is the company VPN?" },
    { "role": "assistant", "content": "The company VPN is..." }
  ]
}
```

| Field | Type | Constraints |
|---|---|---|
| `question` | `string` | 1–2000 chars |
| `history` | `array` | max 10 turns |
| `history[].role` | `"user"` \| `"assistant"` | — |
| `history[].content` | `string` | 1–500 chars |

**Response Body**

```json
{
  "answer": "To set up VPN, follow these steps...",
  "sources": [
    {
      "title": "VPN Setup Guide",
      "doc_id": "123456",
      "chunk_id": "123456-3",
      "heading_path": ["Network", "VPN", "Setup"],
      "url": "https://wiki.example.com/pages/viewpage.action?pageId=123456"
    }
  ]
}
```

**Errors**

| Status | Meaning |
|---|---|
| `400` | Empty or invalid question |
| `401` | Missing or invalid `X-API-Key` |
| `429` | Rate limit exceeded |
| `500` | Chat service not initialised |

---

### `POST /sync`

**Headers**

| Header | Value |
|---|---|
| `Content-Type` | `application/json` |
| `X-API-Key` | Your configured `API_KEY` |

**Request Body**

```json
{ "space_id": "720898", "limit": 50 }
```

To index one page and all of its nested subpages, use the root page ID instead:

```json
{ "page_id": "123456789" }
```

| Field | Type | Constraints |
|---|---|---|
| `space_id` | `string` | optional; required if `page_id` is omitted |
| `page_id` | `string` | optional; when set, indexes this page and its descendant pages |
| `limit` | `integer` | optional, > 0 — omit to index the entire space |

**Response Body**

```json
{ "pages_indexed": 42, "chunks_indexed": 317 }
```

**Errors**

| Status | Meaning |
|---|---|
| `401` | Missing or invalid `X-API-Key` |
| `404` | No pages found for the given space ID |
| `429` | Rate limit exceeded (5/min) |

---

## Security

| Control | Implementation |
|---|---|
| **Authentication** | `X-API-Key` header, verified via `hmac.compare_digest` to prevent timing attacks |
| **Rate Limiting** | SlowAPI — 20 req/min, 300 req/day per client IP |
| **Input Validation** | Pydantic field constraints on question length and history depth |
| **Prompt Injection** | Structural delimiters (`--- BEGIN/END CONTEXT ---`, `--- BEGIN/END QUESTION ---`, `--- BEGIN/END HISTORY TURN ---`) with explicit system instructions that treat injected text as plain data only |
| **CORS** | Configurable allowlist; restricted to `POST` method and required headers |

---

## Scripts

### `scripts/test_retrieval.py`

A debugging utility that runs a similarity search against the vector store and prints the top matching chunks with their metadata. Useful for verifying that indexing worked correctly.

```bash
uv run scripts/test_retrieval.py
```

Edit `TEST_QUERY` at the top of the file to test different queries. This script checks raw vector retrieval; it does not apply the LLM reranker.

---

## Project Structure

```
confluence-rag-bot/
├── app/
│   ├── api/
│   │   ├── chat.py          # FastAPI app, lifespan, /chat endpoint
│   │   ├── sync.py          # /sync endpoint
│   │   ├── deps.py          # Shared auth — limiter + verify_api_key
│   │   └── models.py        # Pydantic request/response models
│   ├── confluence/
│   │   ├── auth.py          # Builds authenticated requests session
│   │   ├── client.py        # Confluence REST API client
│   │   ├── errors.py        # Custom API error type
│   │   ├── mapper.py        # Maps raw API payloads to internal models
│   │   └── models.py        # ConfluencePage dataclass
│   ├── embeddings/
│   │   ├── factory.py       # Creates the embedding model
│   │   ├── indexing.py      # IndexingService — embeds and stores chunks
│   │   ├── retriever.py     # RetrieverService — similarity search
│   │   ├── supabase_client.py # Supabase client singleton
│   │   └── vector_store.py  # Supabase / FAISS vector store factory
│   ├── reranking/
│   │   ├── helpers.py       # Reranker prompt and document formatting
│   │   ├── models.py        # Pydantic schema for reranker JSON output
│   │   └── reranker.py      # RerankerService — LLM relevance selection
│   ├── processing/
│   │   ├── chunker.py       # Splits ParsedDocuments into LangChain Documents
│   │   ├── mapper.py        # Maps chunks to metadata
│   │   ├── models.py        # ParsedDocument dataclass
│   │   └── normalize.py     # Parses Confluence HTML → clean text + headings
│   ├── services/
│   │   ├── cache_service.py # Semantic cache — check, save, validate, evict
│   │   ├── chat_service.py  # Orchestrates cache, retrieval, reranking, and LLM
│   │   ├── helpers.py       # Shared utilities (ChatResult, context builder)
│   │   ├── llm_service.py   # LLMService — prompt construction and GPT call
│   │   └── sync_service.py  # run_sync() + start_daily_sync() scheduler
│   ├── config.py            # Pydantic Settings — all env vars in one place
│   └── main.py              # Minimal entry-point (see /sync for indexing)
├── scripts/
│   └── test_retrieval.py    # Debug utility for vector search
├── .env.example             # Environment variable template
├── Procfile                 # Production process definition (uvicorn)
└── pyproject.toml           # Project metadata and pinned dependencies
```
