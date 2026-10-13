"""campaign-builder: group the processor's letters into campaigns.

For each docket in DOCKET_IDS, reads DATA_DIR/derived/letters/<docket>/letters.parquet and writes
DATA_DIR/derived/campaigns/<docket>/assignments.parquet, the paths in schema.md. Exact match is
the only grouper so far (U-09); MinHash follows (U-05).

Beside the assignments it writes summary.json: the counts, B-cubed when EPA grouped any of the
letters, and the sha256 of the letters file it read, so the result can be tied to its input
without reading the container's output.

Environment:
  DOCKET_IDS   comma-separated, default EPA-HQ-OW-2018-0149
  DATA_DIR     default /app/data
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from bcubed import score_frames
from exact_match import MIN_WORDS, group_exact, summarize


def build_docket(docket: str, data_dir: Path) -> bool:
    """Group one docket's letters. False if the processor has not written them."""
    letters_path = data_dir / "derived" / "letters" / docket / "letters.parquet"
    if not letters_path.exists():
        print(f"[{docket}] no letters at {letters_path}; run data-processor first", file=sys.stderr)
        return False
    letters = pd.read_parquet(letters_path)
    assignments = group_exact(letters)
    out = data_dir / "derived" / "campaigns" / docket / "assignments.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    assignments.to_parquet(out, index=False)
    print(f"[{docket}] {summarize(assignments)}")

    grouped = assignments["campaign_id"].notna()
    summary = {
        "docket_id": docket,
        "method": "exact",
        "min_words": MIN_WORDS,
        "letters": int(len(assignments)),
        "letters_grouped": int(grouped.sum()),
        "groups": int(assignments.loc[grouped, "campaign_id"].nunique()),
        "individual": int((~grouped).sum()),
        "bcubed": None,
        "letters_file": str(letters_path.relative_to(data_dir)),
        "letters_sha256": hashlib.sha256(letters_path.read_bytes()).hexdigest(),
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # EPA's grouping only exists for letters inside campaign attachments, so score when present.
    if "epa_campaign_id" in letters and letters["epa_campaign_id"].notna().any():
        scores = score_frames(assignments, letters)
        summary["bcubed"] = {
            "n_scored": int(scores.n_scored),
            "precision": round(float(scores.precision), 4),
            "recall": round(float(scores.recall), 4),
            "f1": round(float(scores.f1), 4),
        }
        print(
            f"[{docket}] B-cubed on {scores.n_scored} labeled letters: "
            f"precision {scores.precision:.3f}  recall {scores.recall:.3f}  f1 {scores.f1:.3f}"
        )
    (out.parent / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
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
