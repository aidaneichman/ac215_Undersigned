"""Settings read from the environment, with defaults that work inside the compose network."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_COLLECTION = "rule_passages"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    chroma_host: str
    chroma_port: int
    collection: str
    dockets: tuple[str, ...]
    doc_types: tuple[str, ...]
    max_words: int
    overlap_words: int

    @property
    def rule_dir(self) -> Path:
        return self.data_dir / "raw" / "federal_register"

    @classmethod
    def from_env(cls) -> Settings:
        dockets = os.environ.get("RULE_DOCKETS", "EPA-HQ-OW-2018-0149")
        # Comments answer a proposal, so only proposed rules are searched by default.
        doc_types = os.environ.get("RULE_DOC_TYPES", "Proposed Rule")
        return cls(
            data_dir=Path(os.environ.get("DATA_DIR", "/app/data")),
            chroma_host=os.environ.get("CHROMA_HOST", "localhost"),
            chroma_port=int(os.environ.get("CHROMA_PORT", "8000")),
            collection=os.environ.get("RULE_COLLECTION", DEFAULT_COLLECTION),
            dockets=tuple(d.strip() for d in dockets.split(",") if d.strip()),
            doc_types=tuple(t.strip() for t in doc_types.split(",") if t.strip()),
            max_words=int(os.environ.get("CHUNK_MAX_WORDS", "200")),
            overlap_words=int(os.environ.get("CHUNK_OVERLAP_WORDS", "40")),
        )
