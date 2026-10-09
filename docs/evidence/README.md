# Evidence

Logs and small sample artifacts showing the pipeline runs end-to-end (Milestone 2 deliverable). The data itself is DVC-tracked, not committed here; these are excerpts.

## Pipeline (to be added before submission)

| File | What it shows |
| --- | --- |
| `pipeline-run.log` | `docker compose up --build` output: batch stages exit 0 in order, then api-service and frontend start |
| `pipeline-ps.txt` | `docker compose ps -a`: four batch containers `Exited (0)`, chromadb / api-service / frontend `Up` |
| `pipeline-curl.txt` | Responses from `localhost:8000/health`, `localhost:3000` and the ChromaDB heartbeat |
| `vm.png` | Screenshot of the GCP VM running the stack |

## data-collector

Smoke run on EPA-HQ-OW-2018-0149 with `MAX_RECORDS=50` and one API key (indexes the first full page of 250).

| File | What it shows |
| --- | --- |
| `collector-smoke.log` | Log of the run: index, detail calls, attachment downloads, final summary |
| `collector-manifest.json` | Summary written by the collector: 250 comments indexed, 250 detail records, 34 attachments, 0 failed |
| `collector-sample/comments_index.head.jsonl` | First 5 lines of the index (output of stage 1, the list endpoint) |
| `collector-sample/details_index.head.jsonl` | First 5 lines of the per-comment summary (stage 2): `receive_date`, `posted_date`, whether a body is present, attachment count |
| `collector-sample/attachments_manifest.head.jsonl` | First 5 lines of the attachment manifest (stage 3): which files were downloaded and where |
| `collector-sample/EPA-HQ-OW-2018-0149-0077.json` | One complete detail record as returned by `GET /v4/comments/{id}?include=attachments`: the input to stage 3 and the source of the comment text the processor reads |

Input → output: the docket ID `EPA-HQ-OW-2018-0149` goes in; `data/raw/EPA-HQ-OW-2018-0149/` comes out with `comments_index.jsonl`, `details/<id>.json`, `details_index.jsonl`, `attachments/<id>/<file>`, `attachments_manifest.jsonl` and `manifest.json`. Re-running the collector skips everything already on disk (`api_calls_this_run: 0` in the manifest).

## rule-passages

Cold and warm runs, the section outline, and query-to-passage examples for real comments are in [`rule-passages/`](rule-passages/README.md).

## Other containers

Sections for data-processor, campaign-builder and api-service to be added by their owners as they are implemented.