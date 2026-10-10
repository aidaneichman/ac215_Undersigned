"""Undersigned API: the HTTP service the frontend calls.

At startup it opens the rule passage index that the rule-passages stage loaded into ChromaDB and
reads every passage once, so a request only has to search. The retrieval code lives in
rule-passages (the `rule_passages` package); this service imports it rather than keeping a copy.

Environment, with the same names rule-passages uses: CHROMA_HOST, CHROMA_PORT, RULE_COLLECTION,
FASTEMBED_CACHE_PATH.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from rule_passages.chunking import Chunk
from rule_passages.config import Settings
from rule_passages.embedding import BgeEmbedder
from rule_passages.store import PassageStore, connect

# uvicorn only prints its own loggers, so startup messages go through this one.
log = logging.getLogger("uvicorn.error")


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

    @property
    def dockets(self) -> list[str]:
        return sorted({c.docket_id for c in self.chunks})


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

    return app


app = create_app()
