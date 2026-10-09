"""Two ways to find the rule passages a letter argues about, behind one interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .bm25 import BM25Index
from .chunking import Chunk, clean_markup
from .store import PassageStore


def clean_query(text: str) -> str:
    """Comment bodies arrive as HTML with <br/> and style spans, so clean them like the rule."""
    return " ".join(clean_markup(text).split())


@dataclass(frozen=True)
class Hit:
    rank: int
    score: float
    retriever: str
    chunk: Chunk


class Retriever(Protocol):
    name: str

    def search(self, query: str, k: int) -> list[Hit]: ...


class BM25Retriever:
    name = "bm25"

    def __init__(self, chunks: list[Chunk]):
        self.chunks = sorted(chunks, key=lambda c: c.id)
        self.index = BM25Index([c.embed_text for c in self.chunks])

    def search(self, query: str, k: int) -> list[Hit]:
        return [
            Hit(rank, score, self.name, self.chunks[i])
            for rank, (i, score) in enumerate(self.index.search(clean_query(query), k), start=1)
        ]


class DenseRetriever:
    name = "dense"

    def __init__(self, store: PassageStore):
        self.store = store

    def search(self, query: str, k: int) -> list[Hit]:
        return [
            Hit(rank, score, self.name, chunk)
            for rank, (chunk, score) in enumerate(self.store.query(clean_query(query), k), start=1)
        ]
