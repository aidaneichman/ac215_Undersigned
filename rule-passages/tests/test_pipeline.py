from __future__ import annotations

from pathlib import Path

from conftest import DOCKET, FakeSession
from rule_passages import pipeline
from rule_passages.collect import collect
from rule_passages.config import Settings


def settings(tmp_path: Path, **overrides) -> Settings:
    base = {
        "data_dir": tmp_path,
        "chroma_host": "localhost",
        "chroma_port": 8000,
        "collection": "rule_passages_test",
        "dockets": (DOCKET,),
        "doc_types": ("Proposed Rule",),
        "max_words": 80,
        "overlap_words": 15,
    }
    return Settings(**{**base, **overrides})


def test_build_chunks_keeps_only_the_configured_document_types(tmp_path, raw_excerpt):
    collect(DOCKET, settings(tmp_path).rule_dir, FakeSession(raw_excerpt))
    chunks = pipeline.build_chunks(settings(tmp_path))
    assert {c.document_number for c in chunks} == {"2019-00791"}
    both = pipeline.build_chunks(settings(tmp_path, doc_types=("Proposed Rule", "Notice")))
    assert {c.document_number for c in both} == {"2019-00791", "2019-01483"}


def test_index_is_idempotent(tmp_path, raw_excerpt, chroma, embedder, collection_name):
    cfg = settings(tmp_path, collection=collection_name)
    collect(DOCKET, cfg.rule_dir, FakeSession(raw_excerpt))
    store = pipeline.index(cfg, chroma, embedder)
    first = embedder.passages_embedded
    assert first == store.count() > 0
    pipeline.index(cfg, chroma, embedder)
    assert embedder.passages_embedded == first


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
        ("2019-00791", "III/E", "E. Ditches", 4170, 2),
        ("2019-00791", "III/G/1", "G. Wetlands > 1. What is proposed?", 4172, 1),
    ]
