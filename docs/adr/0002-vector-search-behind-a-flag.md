# ADR 0002: Vector search stays behind `ENABLE_VECTOR_SEARCH`

**Status:** accepted (2026-09-08)

## Context

The repository includes a Pinecone-backed vector store and embedding generator
(`vector_store/`). The demo does not use retrieval, Pinecone is a paid external dependency, and
importing its SDK at startup would add cold-start time and one more way to crash.

## Decision

- `ENABLE_VECTOR_SEARCH` defaults to `false`.
- `vector_store/__init__.py` imports nothing at package import time. `get_vector_store(settings)`
  returns `None` when the flag is off and imports Pinecone only when it is on.
- A process-isolated unit test asserts that importing the application loads neither `pinecone`
  nor `sklearn`.

## Consequences

- Nothing in `/chat/completions` can touch Pinecone unless the flag is on.
- The vector-store code stays in the repo as a full-deployment artifact and is covered by its own
  unit tests, which mock the SDK.
- Turning the flag on without `PINECONE_API_KEY` is a clear error at first use rather than a
  silent no-op.
