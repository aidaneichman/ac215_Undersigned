"""Shared test setup: an in-memory ChromaDB and a fake embedder, so tests run offline.

Same approach as rule-passages/tests/conftest.py: no Docker, no network, no model download.
"""

from __future__ import annotations

import re
import uuid

import chromadb
import pytest
from rule_passages.chunking import Chunk
from rule_passages.store import PassageStore

DEV_DOCKET = "EPA-HQ-OW-2018-0149"
VOCAB = ["wetland", "ditch", "tributary", "ephemeral", "permit", "farm"]


class FakeEmbedder:
    """Vectors from keyword counts, so search results are predictable."""

    @staticmethod
    def _vector(text: str) -> list[float]:
        words = re.findall(r"[a-z]+", text.lower())
        vec = [float(sum(w.startswith(v) for w in words)) for v in VOCAB]
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm + 1e-6 for x in vec]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def make_chunk(
    index: int,
    text: str,
    docket: str = DEV_DOCKET,
    doc: str = "2019-00791",
    ref: str = "III/D/1",
    heading: str = "D. Tributaries",
    procedural: bool = False,
) -> Chunk:
    return Chunk(
        id=f"{doc}:{index:04d}",
        docket_id=docket,
        document_number=doc,
        doc_title="Revised Definition",
        citation="84 FR 4154",
        url="https://example.org/doc",
        publication_date="2019-02-14",
        index=index,
        text=text,
        heading=heading,
        section_ref=ref,
        page=4170 + index,
        procedural=procedural,
    )


@pytest.fixture
def store() -> PassageStore:
    # EphemeralClient keeps collections for the whole test run, so each test gets a fresh name.
    name = f"test_{uuid.uuid4().hex[:8]}"
    return PassageStore(chromadb.EphemeralClient(), name, FakeEmbedder())
