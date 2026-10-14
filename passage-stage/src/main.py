"""passage-stage: split each distinct letter into passages and read the rule sections it cites.

For each docket in DOCKET_IDS it reads the processor's letters and the grouper's assignments, keeps one
letter per exact-match group, splits each into passages, and finds citations of the proposed rule's
sections. Section numbers are resolved to rule-passages' `section_ref`, so the API, the rule page and
the baseline table use one key.

Writes to DATA_DIR/derived/passages/<docket>/:
  passages.parquet   one row per passage: passage_id, letter_id, docket_id, index, text, n_words,
                     n_citations
  links.parquet      one row per (passage, cited section): passage_id, letter_id, docket_id,
                     section_ref (null when the cited number is not a section of the rule),
                     citation_raw, source ("citation")
  summary.json       counts, and the sha256 of the letters file read

Needs rule-passages to have collected the rule text under DATA_DIR/raw/federal_register/.

Environment:
  DOCKET_IDS   comma-separated, default EPA-HQ-OW-2018-0149
  DATA_DIR     default /app/data
  RULE_DOCKETS, RULE_DOCUMENTS, RULE_DOC_TYPES   as for rule-passages, so both read the same rule
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from citations import find_citations
from passages import MAX_WORDS, MIN_WORDS, TARGET_WORDS, split_passages

SECTION_NUMBER = re.compile(r"§\s*(\d{1,4}[a-z]?\.\d{1,5}[a-z]{0,2})$")


def section_refs_by_number(section_refs: list[str]) -> dict[str, str]:
    """Section number -> section_ref, for the refs that name one regulatory section.

    "PART 141/§ 141.84" gives "141.84" -> "PART 141/§ 141.84". Preamble refs such as "V/E" have no
    section number and are left out: commenters cite the regulatory text far more often.
    """
    out: dict[str, str] = {}
    for ref in section_refs:
        m = SECTION_NUMBER.search(ref.split("/")[-1].strip())
        if m:
            out.setdefault(m.group(1), ref)
    return out


def rule_section_refs(docket: str, data_dir: Path) -> tuple[list[str], list[str]]:
    """The section_refs of the document this docket's comments answered, as rule-passages chunks it.

    Returns (section_refs in reading order, document numbers used).
    """
    from rule_passages.chunking import chunk_document
    from rule_passages.collect import load_documents
    from rule_passages.config import Settings

    settings = Settings.from_env()
    rule_dir = data_dir / "raw" / "federal_register"
    refs: list[str] = []
    used: list[str] = []
    for doc in load_documents(docket, rule_dir):
        if settings.wanted(docket, doc.document_number, doc.doc_type):
            used.append(doc.document_number)
            for chunk in chunk_document(doc, settings.max_words, settings.overlap_words):
                if chunk.section_ref not in refs:
                    refs.append(chunk.section_ref)
    return refs, used


def distinct_letters(letters: pd.DataFrame, assignments: pd.DataFrame) -> pd.DataFrame:
    """One letter per exact-match group (the one the group is named after) plus every ungrouped one."""
    group = dict(zip(assignments["letter_id"], assignments["campaign_id"], strict=True))
    keep = [
        pd.isna(group.get(letter_id)) or group.get(letter_id) == letter_id
        for letter_id in letters["letter_id"]
    ]
    return letters[keep]


def build(
    letters: pd.DataFrame, docket: str, by_number: dict[str, str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Passages and citation links for the given letters."""
    passage_rows, link_rows = [], []
    rule_numbers = set(by_number)
    for letter_id, text in zip(letters["letter_id"], letters["text"], strict=True):
        for index, passage in enumerate(split_passages(text if isinstance(text, str) else "")):
            passage_id = f"{letter_id}:p{index:03d}"
            cites = find_citations(passage, rule_numbers)
            passage_rows.append(
                {
                    "passage_id": passage_id,
                    "letter_id": letter_id,
                    "docket_id": docket,
                    "index": index,
                    "text": passage,
                    "n_words": len(passage.split()),
                    "n_citations": len(cites),
                }
            )
            seen: set[tuple[str | None, str]] = set()
            for cite in cites:
                ref = by_number.get(cite.number)
                key = (ref, cite.number if ref is None else "")
                if key in seen:  # the same section cited twice in one passage is one link
                    continue
                seen.add(key)
                link_rows.append(
                    {
                        "passage_id": passage_id,
                        "letter_id": letter_id,
                        "docket_id": docket,
                        "section_ref": ref,
                        "citation_raw": cite.raw,
                        "source": "citation",
                    }
                )
    passages = pd.DataFrame(
        passage_rows,
        columns=["passage_id", "letter_id", "docket_id", "index", "text", "n_words", "n_citations"],
    )
    links = pd.DataFrame(
        link_rows,
        columns=["passage_id", "letter_id", "docket_id", "section_ref", "citation_raw", "source"],
    ).astype({"section_ref": "string"})
    return passages, links


def build_docket(docket: str, data_dir: Path, section_refs: list[str] | None = None) -> bool:
    """Write passages, links and summary for one docket. False if an input is missing."""
    letters_path = data_dir / "derived" / "letters" / docket / "letters.parquet"
    groups_path = data_dir / "derived" / "campaigns" / docket / "assignments.parquet"
    for path, stage in ((letters_path, "data-processor"), (groups_path, "campaign-builder")):
        if not path.exists():
            print(f"[{docket}] no {path.name} at {path}; run {stage} first", file=sys.stderr)
            return False
    letters = pd.read_parquet(letters_path)
    if letters.empty:
        print(f"[{docket}] {letters_path} is empty; see the processor's report", file=sys.stderr)
        return False
    documents: list[str] = []
    if section_refs is None:
        section_refs, documents = rule_section_refs(docket, data_dir)
    by_number = section_refs_by_number(section_refs)
    if not by_number:
        print(
            f"[{docket}] no rule sections found under {data_dir / 'raw' / 'federal_register'}; "
            "run rule-passages first",
            file=sys.stderr,
        )
        return False

    distinct = distinct_letters(letters, pd.read_parquet(groups_path))
    passages, links = build(distinct, docket, by_number)
    out = data_dir / "derived" / "passages" / docket
    out.mkdir(parents=True, exist_ok=True)
    passages.to_parquet(out / "passages.parquet", index=False)
    links.to_parquet(out / "links.parquet", index=False)

    resolved = links["section_ref"].notna()
    summary = {
        "docket_id": docket,
        "letters_read": len(letters),
        "letters_skipped_as_copies": int(len(letters) - len(distinct)),
        "passages": len(passages),
        "passages_with_citation": int((passages["n_citations"] > 0).sum()),
        "links": len(links),
        "links_resolved": int(resolved.sum()),
        "links_unresolved": int((~resolved).sum()),
        "sections_cited": int(links.loc[resolved, "section_ref"].nunique()),
        "rule_sections_known": len(by_number),
        "rule_documents": documents,
        "passage_words": {"target": TARGET_WORDS, "max": MAX_WORDS, "min": MIN_WORDS},
        "letters_file": str(letters_path.relative_to(data_dir)),
        "letters_sha256": hashlib.sha256(letters_path.read_bytes()).hexdigest(),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(
        f"[{docket}] {summary['letters_read'] - summary['letters_skipped_as_copies']} letters, "
        f"{summary['passages']} passages, {summary['passages_with_citation']} cite the rule's "
        f"sections or other CFR text, {summary['links_resolved']} links to "
        f"{summary['sections_cited']} sections of the rule, "
        f"{summary['links_unresolved']} to numbers outside it"
    )
    return True


def main() -> int:
    load_dotenv()
    dockets = [
        d.strip() for d in os.getenv("DOCKET_IDS", "EPA-HQ-OW-2018-0149").split(",") if d.strip()
    ]
    data_dir = Path(os.getenv("DATA_DIR", "/app/data"))
    done = [build_docket(docket, data_dir) for docket in dockets]
    return 0 if all(done) else 1


if __name__ == "__main__":
    sys.exit(main())
