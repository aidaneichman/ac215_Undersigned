"""Undersigned API: the HTTP service the frontend calls.

At startup it opens the rule passage index that the rule-passages stage loaded into ChromaDB and
reads every passage once, so a request only has to search. The retrieval code lives in
rule-passages (the `rule_passages` package); this service imports it rather than keeping a copy.

Endpoints:
  GET  /health     liveness, plus how many passages the API can search and for which dockets
  POST /retrieve   a letter in, the rule passages it argues about out (BM25, embeddings, or both)

Environment, with the same names rule-passages uses: CHROMA_HOST, CHROMA_PORT, RULE_COLLECTION,
FASTEMBED_CACHE_PATH.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, Request
from pydantic import BaseModel, Field, StringConstraints
from rule_passages.chunking import Chunk
from rule_passages.config import Settings
from rule_passages.embedding import BgeEmbedder
from rule_passages.retrieve import BM25Retriever, DenseRetriever, Hit, Retriever
from rule_passages.store import PassageStore, connect

# uvicorn only prints its own loggers, so startup messages go through this one.
log = logging.getLogger("uvicorn.error")

Method = Literal["bm25", "dense", "both"]


class PassageIndex:
    """The rule passages the API searches, read from ChromaDB once at startup."""

    def __init__(self, store: PassageStore):
        self.store = store
        self.chunks: list[Chunk] = list(store.chunks())
        # An API that answers "ok" over an empty index looks healthy and finds nothing,
        # so refuse to start instead.
        if not self.chunks:
            raise RuntimeError(
                f"ChromaDB collection {store.name!r} is empty. Fill it with "
                "`docker compose run --rm rule-passages` before starting the API."
            )
        self.dockets: list[str] = sorted({c.docket_id for c in self.chunks})
        # BM25 keeps its index in memory, so build one for all dockets (key None) and one per
        # docket now rather than on every request.
        self._bm25 = {d: BM25Retriever(self.chunks, docket_id=d) for d in [None, *self.dockets]}

    def search(self, text: str, k: int, method: Method, docket_id: str | None) -> list[Hit]:
        """Top-k passages from each requested retriever: BM25 hits first, then embedding hits.

        The two lists stay separate because their scores are on different scales (BM25 is
        unbounded, embeddings are cosine similarity), so sorting them together means nothing.
        """
        if docket_id is not None and docket_id not in self.dockets:
            return []
        retrievers: list[Retriever] = []
        if method in ("bm25", "both"):
            retrievers.append(self._bm25[docket_id])
        if method in ("dense", "both"):
            retrievers.append(DenseRetriever(self.store, docket_id=docket_id))
        return [hit for r in retrievers for hit in r.search(text, k)]


class RetrieveRequest(BaseModel):
    """A letter to find rule passages for. Invalid fields are rejected with a 422."""

    # bge-small reads only the first 512 tokens (a few hundred words) of a query; BM25 reads all
    # of it. The cap only stops absurd payloads.
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000)]
    k: int = Field(3, ge=1, le=20, description="passages per retriever")
    method: Method = "both"
    docket_id: str | None = Field(None, description="only search this docket's rule text")


def open_index() -> PassageIndex:
    """Connect to the ChromaDB that rule-passages filled, with the model it embedded with."""
    settings = Settings.from_env()
    client = connect(settings.chroma_host, settings.chroma_port)
    return PassageIndex(PassageStore(client, settings.collection, BgeEmbedder()))


def create_app(load_index: Callable[[], PassageIndex] = open_index) -> FastAPI:
    """Build the app. Tests pass a `load_index` that serves an in-memory collection."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        index = load_index()
        log.info(
            "Loaded %d rule passages from %r for %s",
            len(index.chunks), index.store.name, ", ".join(index.dockets),
        )  # fmt: skip
        app.state.index = index
        yield

    app = FastAPI(title="Undersigned API", lifespan=lifespan)

    @app.get("/health")
    def health(request: Request) -> dict:
        """Liveness check that also says what the API can search."""
        index: PassageIndex = request.app.state.index
        return {"status": "ok", "passages": len(index.chunks), "dockets": index.dockets}

    # A plain `def`, not `async def`: embedding the query blocks for a moment, and FastAPI runs
    # plain functions in a worker thread so other requests are not held up meanwhile.
    @app.post("/retrieve")
    def retrieve(body: RetrieveRequest, request: Request) -> dict:
        """The rule passages a letter argues about, in the shape `Hit.to_dict()` defines."""
        index: PassageIndex = request.app.state.index
        hits = index.search(body.text, body.k, body.method, body.docket_id)
        return {"hits": [hit.to_dict() for hit in hits]}

    return app


app = create_app()
