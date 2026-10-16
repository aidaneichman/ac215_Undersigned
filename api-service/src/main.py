"""Undersigned API: the HTTP service the frontend calls.

At startup it opens the rule passage index that the rule-passages stage loaded into ChromaDB and
reads every passage once, so a request only has to search. The retrieval code lives in
rule-passages (the `rule_passages` package); this service imports it rather than keeping a copy.

Endpoints:
  GET  /health     liveness, plus how many passages the API can search and for which dockets
  POST /retrieve   a letter in, the rule passages it argues about out (BM25, embeddings, both
                   as separate lists, or one merged list)
  GET  /rules/{docket_id}/sections
                   the rule's sections in reading order, for the rule page

The section counts come from passage-stage's DATA_DIR/derived/passages/<docket>/links.parquet,
also read once at startup. A docket without that file keeps its counts null (unknown).

Environment, with the same names rule-passages uses: CHROMA_HOST, CHROMA_PORT, RULE_COLLECTION,
FASTEMBED_CACHE_PATH, DATA_DIR.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

import pyarrow.parquet as pq
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field, StringConstraints
from rule_passages.chunking import Chunk
from rule_passages.config import Settings
from rule_passages.embedding import BgeEmbedder
from rule_passages.retrieve import BM25Retriever, DenseRetriever, FusedRetriever, Hit
from rule_passages.store import PassageStore, connect

# uvicorn only prints its own loggers, so startup messages go through this one.
log = logging.getLogger("uvicorn.error")

Method = Literal["bm25", "dense", "both", "merged"]

# The most passages a request can ask for. 50, not 20: a reranker will read the top 30 candidates,
# so the API has to be able to supply them.
MAX_K = 50


def rule_sections(chunks: list[Chunk]) -> list[dict]:
    """One entry per section of rule text, in reading order, for a single docket's chunks.

    A section is a `section_ref` within one Federal Register document, plus every heading above
    it, so a parent with no text of its own ("III/D" when all its text sits under "III/D/1" and
    "III/D/2") still gets an entry: commenters cite "Section III.D". A parent comes just before
    its first child, and its counts include its children's. Procedural sections (summary,
    addresses, ...) are left out, as /retrieve leaves them out: nobody argues about them.
    """
    sections: dict[tuple[str, str], dict] = {}
    for chunk in sorted(chunks, key=lambda c: (c.document_number, c.index)):
        if chunk.procedural:
            continue
        refs = chunk.section_ref.split("/")
        headings = chunk.heading.split(" > ")
        # rule-passages builds both from the same heading path, one level per "/" and " > ", so
        # they line up. If a chunk's do not, list just its own section rather than guess its
        # parents' headings, so one odd chunk cannot stop the API from starting.
        first = 1 if len(refs) == len(headings) else len(refs)
        # Ancestors first, then the section itself, so dict order is reading order.
        for depth in range(first, len(refs) + 1):
            key = (chunk.document_number, "/".join(refs[:depth]))
            if key not in sections:
                own = depth == len(refs)
                sections[key] = {
                    "document_number": chunk.document_number,
                    "citation": chunk.citation,
                    "section_ref": key[1],
                    "parent_ref": "/".join(refs[: depth - 1]) or None,
                    "heading": chunk.heading if own else " > ".join(headings[:depth]),
                    "title": headings[-1] if own else headings[depth - 1],
                    "depth": depth,
                    # Where the section's first passage starts; for a parent, its first child's.
                    "page": chunk.page,
                    "rule_passages": 0,
                    # Comment passages, and distinct letters, that cite this section or one
                    # under it. Filled by add_citation_counts; null when the passage stage has
                    # not run for the docket, which is unknown, not zero.
                    "citing_passages": None,
                    "citing_letters": None,
                }
            sections[key]["rule_passages"] += 1
    return list(sections.values())


def read_links(passages_dir: Path | None, docket_id: str) -> list[dict] | None:
    """passage-stage's citation links for one docket, or None if it has not written them."""
    if passages_dir is None:
        return None
    path = passages_dir / docket_id / "links.parquet"
    if not path.exists():
        return None
    return pq.read_table(path, columns=["passage_id", "letter_id", "section_ref"]).to_pylist()


def add_citation_counts(sections: list[dict], links: list[dict]) -> int:
    """Fill each section's citing counts from the links, and return how many links are unresolved.

    A link names one section by rule-passages' `section_ref`, so it counts for that section and
    every section above it ("PART 141/§ 141.84" also counts for "PART 141"). Counts are of distinct
    passages and distinct letters: a passage citing two sections under one parent counts once there.
    A link whose `section_ref` is null cites something that is not a section of the rule.
    """
    passages: dict[str, set[str]] = defaultdict(set)
    letters: dict[str, set[str]] = defaultdict(set)
    unresolved = 0
    for link in links:
        ref = link["section_ref"]
        if ref is None:
            unresolved += 1
            continue
        parts = ref.split("/")
        for depth in range(1, len(parts) + 1):
            passages["/".join(parts[:depth])].add(link["passage_id"])
            letters["/".join(parts[:depth])].add(link["letter_id"])
    listed = {s["section_ref"] for s in sections}
    if missing := sorted(set(passages) - listed):
        # Both stages read the rule with rule-passages' chunking, so this means they ran on
        # different versions of the rule text.
        log.warning("Links cite sections the rule's index does not list: %s", ", ".join(missing))
    for section in sections:
        section["citing_passages"] = len(passages.get(section["section_ref"], ()))
        section["citing_letters"] = len(letters.get(section["section_ref"], ()))
    return unresolved


class PassageIndex:
    """The rule passages the API searches, read from ChromaDB once at startup."""

    def __init__(self, store: PassageStore, passages_dir: Path | None = None):
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
        # The rule text does not change while the API runs, so its sections are listed once.
        self.sections: dict[str, list[dict]] = {
            d: rule_sections([c for c in self.chunks if c.docket_id == d]) for d in self.dockets
        }
        # Links that cite something outside the rule, per docket; None where counts are unknown.
        self.unresolved_citations: dict[str, int | None] = {}
        for d in self.dockets:
            links = read_links(passages_dir, d)
            if links is None:
                self.unresolved_citations[d] = None
                log.info("No passage links for %s, so its citation counts stay null", d)
                continue
            self.unresolved_citations[d] = add_citation_counts(self.sections[d], links)
            log.info("Read %d passage links for %s", len(links), d)

    def search(self, text: str, k: int, method: Method, docket_id: str | None) -> list[Hit]:
        """Top-k passages from each requested retriever, or one merged top-k list.

        For "both", BM25 hits come first, then embedding hits. They stay separate lists because
        their scores are on different scales (BM25 is unbounded, embeddings are cosine
        similarity), so sorting them together by score means nothing. "merged" combines them by
        rank instead (`FusedRetriever` in rule-passages, the same one its evaluation uses).
        """
        if docket_id is not None and docket_id not in self.dockets:
            return []
        bm25 = self._bm25[docket_id]
        dense = DenseRetriever(self.store, docket_id=docket_id)
        if method == "merged":
            return FusedRetriever([bm25, dense]).search(text, k)
        if method == "bm25":
            return bm25.search(text, k)
        if method == "dense":
            return dense.search(text, k)
        return bm25.search(text, k) + dense.search(text, k)


class RetrieveRequest(BaseModel):
    """A letter to find rule passages for. Invalid fields are rejected with a 422."""

    # bge-small reads only the first 512 tokens (a few hundred words) of a query; BM25 reads all
    # of it. The cap only stops absurd payloads.
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50_000)]
    k: int = Field(3, ge=1, le=MAX_K, description="passages per retriever, or in total for merged")
    method: Method = "both"
    docket_id: str | None = Field(None, description="only search this docket's rule text")


def open_index() -> PassageIndex:
    """Connect to the ChromaDB that rule-passages filled, with the model it embedded with."""
    settings = Settings.from_env()
    client = connect(settings.chroma_host, settings.chroma_port)
    store = PassageStore(client, settings.collection, BgeEmbedder())
    return PassageIndex(store, settings.data_dir / "derived" / "passages")


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

    @app.get("/rules/{docket_id}/sections")
    def sections(docket_id: str, request: Request) -> dict:
        """The sections of the rule a docket's comments answered, in reading order."""
        index: PassageIndex = request.app.state.index
        if docket_id not in index.sections:
            # A 404, not an empty list: the rule page should say "no such rule", not "no sections".
            raise HTTPException(
                status_code=404,
                detail=f"No rule text indexed for docket {docket_id!r}. "
                f"Indexed: {', '.join(index.dockets)}.",
            )
        return {
            "docket_id": docket_id,
            "unresolved_citations": index.unresolved_citations[docket_id],
            "sections": index.sections[docket_id],
        }

    return app


app = create_app()
