from __future__ import annotations

import pytest

from conftest import make_chunk
from rule_passages.store import PassageStore

CHUNKS = [
    make_chunk(0, "Wetlands adjacent to a tributary are covered.", "III/G", "G. Wetlands"),
    make_chunk(1, "A ditch that drains a farm field is excluded.", "III/E", "E. Ditches"),
    make_chunk(2, "Lakes and ponds that are not connected are not covered.", "III/F", "F. Lakes"),
]


@pytest.fixture
def store(chroma, collection_name, embedder):
    return PassageStore(chroma, collection_name, embedder)


def test_first_upsert_embeds_everything_and_a_rerun_embeds_nothing(store, embedder):
    assert store.upsert(CHUNKS) == 3
    assert store.upsert(CHUNKS) == 0
    assert store.count() == 3
    assert embedder.passages_embedded == 3


def test_only_changed_chunks_are_embedded_again(store, embedder):
    store.upsert(CHUNKS)
    edited = [
        CHUNKS[0],
        make_chunk(1, "Ditches are now covered.", "III/E", "E. Ditches"),
        CHUNKS[2],
    ]
    assert store.upsert(edited) == 1
    assert store.count() == 3


def test_query_returns_the_nearest_chunk_with_its_metadata(store):
    store.upsert(CHUNKS)
    (chunk, score), *_ = store.query("a ditch on my farm", k=2)
    assert chunk.id == "2019-00791:0001"
    assert (chunk.section_ref, chunk.page, chunk.citation) == ("III/E", 4171, "84 FR 4154")
    assert 0.0 < score <= 1.0 + 1e-6


def test_stored_chunks_round_trip_exactly(store):
    store.upsert(CHUNKS)
    assert sorted(store.chunks(), key=lambda c: c.id) == CHUNKS


def test_a_chunk_without_a_page_round_trips(store):
    from dataclasses import replace

    no_page = replace(CHUNKS[0], page=None)
    store.upsert([no_page])
    assert next(store.chunks()).page is None


def test_chunks_pages_through_more_than_one_batch(store):
    many = [make_chunk(i, f"Permit text {i} wetland.") for i in range(300)]
    store.upsert(many)
    assert len(list(store.chunks())) == 300


def test_flipping_the_procedural_flag_re_embeds_the_chunk(store, embedder):
    from dataclasses import replace

    store.upsert(CHUNKS)
    assert store.upsert([replace(CHUNKS[0], procedural=True)]) == 1
    assert {c.id: c.procedural for c in store.chunks()}["2019-00791:0000"] is True


def test_prune_removes_only_chunks_outside_the_keep_set(store):
    store.upsert(CHUNKS)
    assert store.prune({CHUNKS[0].id, CHUNKS[1].id}) == 1
    assert sorted(c.id for c in store.chunks()) == [CHUNKS[0].id, CHUNKS[1].id]


def test_query_skips_procedural_chunks_unless_asked(store):
    from dataclasses import replace

    store.upsert([replace(CHUNKS[1], procedural=True), CHUNKS[0], CHUNKS[2]])
    default = store.query("a ditch on my farm", k=3, include_procedural=False)
    assert CHUNKS[1].id not in {c.id for c, _ in default}
    everything = store.query("a ditch on my farm", k=3, include_procedural=True)
    assert everything[0][0].id == CHUNKS[1].id
