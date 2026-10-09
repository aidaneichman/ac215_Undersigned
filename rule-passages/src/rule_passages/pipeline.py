"""The batch stages: collect rule text, chunk it, index it, and compare chunk sizes."""

from __future__ import annotations

import logging

import chromadb

from .chunking import Chunk, chunk_document
from .collect import collect, load_documents
from .config import Settings
from .embedding import Embedder
from .evaluate import LabeledQuery, top_k_accuracy
from .retrieve import BM25Retriever, DenseRetriever
from .store import PassageStore

log = logging.getLogger("rule-passages")


def build_chunks(
    settings: Settings, max_words: int | None = None, overlap_words: int | None = None
) -> list[Chunk]:
    """Chunks of every collected document of the configured dockets and document types."""
    max_words = max_words or settings.max_words
    overlap = settings.overlap_words if overlap_words is None else overlap_words
    chunks: list[Chunk] = []
    for docket in settings.dockets:
        for doc in load_documents(docket, settings.rule_dir):
            if doc.doc_type in settings.doc_types:
                made = chunk_document(doc, max_words, overlap)
                log.info("[%s] %s: %d chunks", docket, doc.document_number, len(made))
                chunks.extend(made)
    return chunks


def section_outline(chunks: list[Chunk]) -> list[tuple[str, str, str, int | None, int]]:
    """One row per section in reading order: (document, section_ref, heading, first page, chunks).

    These are the section references a hand label can name in its `gold` list.
    """
    rows: dict[tuple[str, str], list] = {}
    for chunk in sorted(chunks, key=lambda c: (c.document_number, c.index)):
        key = (chunk.document_number, chunk.section_ref)
        if key not in rows:
            parts = chunk.heading.split(" > ")
            rows[key] = [" > ".join(parts[1:] or parts), chunk.page, 0]
        rows[key][2] += 1
    return [(doc, ref, heading, page, n) for (doc, ref), (heading, page, n) in rows.items()]


def collect_all(settings: Settings) -> None:
    for docket in settings.dockets:
        collect(docket, settings.rule_dir)


def index(settings: Settings, client: chromadb.ClientAPI, embedder: Embedder) -> PassageStore:
    store = PassageStore(client, settings.collection, embedder)
    chunks = build_chunks(settings)
    embedded = store.upsert(chunks)
    log.info(
        "[%s] %d chunks, %d embedded this run, %d in the collection",
        settings.collection, len(chunks), embedded, store.count(),
    )  # fmt: skip
    return store


def sweep(
    settings: Settings,
    client: chromadb.ClientAPI,
    embedder: Embedder,
    labels: list[LabeledQuery],
    sizes: list[int],
) -> list[tuple[str, dict[int, float]]]:
    """Index the rule once per chunk size and score both retrievers on the labeled campaigns."""
    rows = []
    for size in sizes:
        chunks = build_chunks(settings, max_words=size, overlap_words=size // 5)
        store = PassageStore(client, f"{settings.collection}_w{size}", embedder)
        store.upsert(chunks)
        for retriever in (BM25Retriever(chunks), DenseRetriever(store)):
            rows.append((f"{retriever.name} @ {size} words", top_k_accuracy(retriever, labels)))
    return rows
