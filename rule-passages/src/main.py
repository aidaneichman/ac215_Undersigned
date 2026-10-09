"""rule-passages: chunk Federal Register rule text into ChromaDB; BM25 baseline.

Run with no arguments it does the batch stage: download the rule text for each docket in
RULE_DOCKETS, chunk it, embed it, and load it into the ChromaDB collection `rule_passages`.
The other commands are for looking at the result:

  query   find the rule passages a letter argues about (BM25, dense, or both)
  outline list the section references a hand label can name
  eval    top-k accuracy on hand-mapped campaigns
  sweep   index at several chunk sizes and score each

Environment: DATA_DIR, CHROMA_HOST, CHROMA_PORT, RULE_DOCKETS, RULE_DOC_TYPES, RULE_COLLECTION,
CHUNK_MAX_WORDS, CHUNK_OVERLAP_WORDS, FASTEMBED_CACHE_PATH.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from rule_passages import pipeline
from rule_passages.config import Settings
from rule_passages.embedding import BgeEmbedder
from rule_passages.evaluate import format_table, load_labels, top_k_accuracy
from rule_passages.retrieve import BM25Retriever, DenseRetriever, Hit
from rule_passages.store import PassageStore, connect

log = logging.getLogger("rule-passages")


def read_query(args: argparse.Namespace) -> str:
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")
    return args.text if args.text else sys.stdin.read()


def show(hits: list[Hit]) -> None:
    for h in hits:
        c = h.chunk
        page = f", p. {c.page}" if c.page else ""
        print(f"{h.retriever:5s} #{h.rank} {h.score:6.3f}  {c.citation}{page}  [{c.section_ref}]")
        print(f"      {c.heading}")
        print(f"      {' '.join(c.text.split())[:240]}...")


def cmd_query(settings: Settings, args: argparse.Namespace) -> None:
    store = PassageStore(connect(settings.chroma_host, settings.chroma_port),
                         settings.collection, BgeEmbedder())  # fmt: skip
    text = read_query(args)
    retrievers = []
    if args.method in ("bm25", "both"):
        retrievers.append(BM25Retriever(list(store.chunks())))
    if args.method in ("dense", "both"):
        retrievers.append(DenseRetriever(store))
    hits = [h for r in retrievers for h in r.search(text, args.k)]
    if args.json:
        print(json.dumps([
            {"retriever": h.retriever, "rank": h.rank, "score": round(h.score, 4),
             "id": h.chunk.id, "citation": h.chunk.citation, "page": h.chunk.page,
             "section_ref": h.chunk.section_ref, "heading": h.chunk.heading,
             "text": h.chunk.text}
            for h in hits
        ], indent=2))  # fmt: skip
    else:
        show(hits)


def cmd_outline(settings: Settings) -> None:
    store = PassageStore(connect(settings.chroma_host, settings.chroma_port),
                         settings.collection, BgeEmbedder())  # fmt: skip
    for doc, ref, heading, page, n in pipeline.section_outline(list(store.chunks())):
        print(f"{doc}:{ref:<24s} p.{page or '?':<5} {n:>3} chunks  {heading[:90]}")


def cmd_eval(settings: Settings, args: argparse.Namespace) -> None:
    store = PassageStore(connect(settings.chroma_host, settings.chroma_port),
                         settings.collection, BgeEmbedder())  # fmt: skip
    labels = load_labels(Path(args.labels))
    rows = [
        (r.name, top_k_accuracy(r, labels))
        for r in (BM25Retriever(list(store.chunks())), DenseRetriever(store))
    ]
    print(f"{len(labels)} labeled campaigns\n{format_table(rows)}")


def cmd_sweep(settings: Settings, args: argparse.Namespace) -> None:
    client = connect(settings.chroma_host, settings.chroma_port)
    labels = load_labels(Path(args.labels))
    sizes = [int(s) for s in args.sizes.split(",")]
    rows = pipeline.sweep(settings, client, BgeEmbedder(), labels, sizes)
    print(f"{len(labels)} labeled campaigns\n{format_table(rows)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("run", help="collect and index (the default)")
    sub.add_parser("collect", help="download rule text only")
    sub.add_parser("index", help="chunk and index collected rule text only")
    q = sub.add_parser("query", help="find passages for a letter")
    q.add_argument("--text")
    q.add_argument("--file")
    q.add_argument("--method", choices=["bm25", "dense", "both"], default="both")
    q.add_argument("-k", type=int, default=3)
    q.add_argument("--json", action="store_true")
    sub.add_parser("outline", help="list the section references labels can use")
    e = sub.add_parser("eval", help="top-k accuracy on labeled campaigns")
    e.add_argument("--labels", required=True)
    s = sub.add_parser("sweep", help="compare chunk sizes")
    s.add_argument("--labels", required=True)
    s.add_argument("--sizes", default="120,250")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one INFO line per Chroma call
    settings = Settings.from_env()
    command = args.command or "run"
    if command in ("run", "collect"):
        pipeline.collect_all(settings)
    if command in ("run", "index"):
        pipeline.index(settings, connect(settings.chroma_host, settings.chroma_port), BgeEmbedder())
    if command == "query":
        cmd_query(settings, args)
    elif command == "outline":
        cmd_outline(settings)
    elif command == "eval":
        cmd_eval(settings, args)
    elif command == "sweep":
        cmd_sweep(settings, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
