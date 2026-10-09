from __future__ import annotations

from pathlib import Path

import pytest

from conftest import DOCKET, FakeSession
from rule_passages import pipeline
from rule_passages.collect import collect
from rule_passages.config import Settings
from rule_passages.store import PassageStore


def settings(tmp_path: Path, **overrides) -> Settings:
    base = {
        "data_dir": tmp_path,
        "chroma_host": "localhost",
        "chroma_port": 8000,
        "collection": "rule_passages_test",
        "dockets": (DOCKET,),
        "doc_types": ("Proposed Rule",),
        "documents": (),
        "max_words": 80,
        "overlap_words": 15,
    }
    return Settings(**{**base, **overrides})


def test_a_docket_with_a_known_commented_on_document_indexes_only_that_one(tmp_path, raw_excerpt):
    collect(DOCKET, settings(tmp_path).rule_dir, FakeSession(raw_excerpt))
    chunks = pipeline.build_chunks(settings(tmp_path))
    assert {c.document_number for c in chunks} == {"2019-00791"}


def test_other_dockets_fall_back_to_the_configured_document_types(tmp_path, raw_excerpt):
    other = "OTHER-2020-0001"
    collect(other, settings(tmp_path).rule_dir, FakeSession(raw_excerpt))
    only_proposed = settings(tmp_path, dockets=(other,))
    assert {c.document_number for c in pipeline.build_chunks(only_proposed)} == {"2019-00791"}
    both = settings(tmp_path, dockets=(other,), doc_types=("Proposed Rule", "Notice"))
    assert {c.document_number for c in pipeline.build_chunks(both)} == {"2019-00791", "2019-01483"}


def test_an_explicit_document_list_overrides_everything_else(tmp_path, raw_excerpt):
    collect(DOCKET, settings(tmp_path).rule_dir, FakeSession(raw_excerpt))
    cfg = settings(tmp_path, documents=("2019-01483",))
    assert {c.document_number for c in pipeline.build_chunks(cfg)} == {"2019-01483"}


def test_index_is_idempotent(tmp_path, raw_excerpt, chroma, embedder, collection_name):
    cfg = settings(tmp_path, collection=collection_name)
    collect(DOCKET, cfg.rule_dir, FakeSession(raw_excerpt))
    store = pipeline.index(cfg, chroma, embedder)
    first = embedder.passages_embedded
    assert first == store.count() > 0
    pipeline.index(cfg, chroma, embedder)
    assert embedder.passages_embedded == first


def test_index_prunes_chunks_that_no_longer_belong(tmp_path, raw_excerpt, chroma, embedder):
    name = "prune_test"
    collect(DOCKET, settings(tmp_path).rule_dir, FakeSession(raw_excerpt))
    wide = settings(tmp_path, collection=name, documents=("2019-00791", "2019-01483"))
    pipeline.index(wide, chroma, embedder)
    kept = pipeline.index(
        settings(tmp_path, collection=name, documents=("2019-00791",)), chroma, embedder
    )
    assert {c.document_number for c in kept.chunks()} == {"2019-00791"}


def test_sweep_scores_both_retrievers_at_each_size(tmp_path, raw_excerpt, chroma, embedder):
    from rule_passages.evaluate import LabeledQuery

    cfg = settings(tmp_path, collection="sweep_test")
    collect(DOCKET, cfg.rule_dir, FakeSession(raw_excerpt))
    labels = [LabeledQuery("c1", "ditch farm tributary", ("I/D",))]
    rows = pipeline.sweep(cfg, chroma, embedder, labels, sizes=[60, 120])
    assert [name for name, _ in rows] == [
        "bm25 @ 60 words",
        "dense @ 60 words",
        "bm25 @ 120 words",
        "dense @ 120 words",
    ]
    assert all(set(acc) == {1, 3} for _, acc in rows)


def test_section_outline_counts_chunks_per_section_in_reading_order():
    from conftest import make_chunk

    chunks = [
        make_chunk(0, "a", "III/E", "III > E. Ditches"),
        make_chunk(1, "b", "III/E", "III > E. Ditches"),
        make_chunk(2, "c", "III/G/1", "III > G. Wetlands > 1. What is proposed?"),
    ]
    assert pipeline.section_outline(chunks) == [
        ("2019-00791", "III/E", "E. Ditches", 4170, 2, False),
        ("2019-00791", "III/G/1", "G. Wetlands > 1. What is proposed?", 4172, 1, False),
    ]


def test_a_docket_that_yields_no_chunks_stops_the_stage_and_names_what_is_on_disk(
    tmp_path, raw_excerpt
):
    collect(DOCKET, settings(tmp_path).rule_dir, FakeSession(raw_excerpt))
    wrong = settings(tmp_path, documents=("0000-00000",))
    with pytest.raises(RuntimeError, match=r"no chunks to index.*2019-00791"):
        pipeline.build_chunks(wrong)


def test_a_docket_with_nothing_collected_fails_instead_of_indexing_nothing(tmp_path):
    with pytest.raises(RuntimeError, match=r"Documents on disk: none"):
        pipeline.build_chunks(settings(tmp_path))


def test_a_failed_build_leaves_the_existing_index_untouched(
    tmp_path, raw_excerpt, chroma, embedder, collection_name
):
    good = settings(tmp_path, collection=collection_name)
    collect(DOCKET, good.rule_dir, FakeSession(raw_excerpt))
    store = pipeline.index(good, chroma, embedder)
    before = store.count()
    broken = settings(tmp_path, collection=collection_name, documents=("0000-00000",))
    with pytest.raises(RuntimeError):
        pipeline.index(broken, chroma, embedder)
    assert PassageStore(chroma, collection_name, embedder).count() == before > 0
