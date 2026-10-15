# Undersigned: Who Is Behind a Public Comment Campaign?

AC215 · Aidan Eichman, Aadil Jamari, Livia Jonnatan, Andrew Yuan, Rishi Jain

When a federal agency proposes a rule, most of the public comments it receives are form letters sent by supporters of an advocacy group. Real campaigns and fraudulent ones (stolen names, reworded templates) look the same on arrival. Undersigned takes a rulemaking docket, finds its comment campaigns across exact copies, personalized letters and LLM-reworded letters, and shows an analyst each campaign's size, timing, sponsor, arguments and signer evidence, without labelling any individual comment as fake.

Development docket: EPA-HQ-OW-2018-0149 (2019 "waters of the United States" rule, 518,473 comments). Transfer docket: EPA-HQ-OAR-2017-0355 (Clean Power Plan repeal). Case studies: FCC 17-108 (net neutrality).

Milestone 1 proposal: `main.tex` / `milestone1.tex`. Application mock and architecture: `docs/`.

## Repository layout

```
data-collector/    Pull comments and attachments from Regulations.gov and FCC ECFS
data-processor/    One canonical record per letter; PDF text, OCR, signer hashing
campaign-builder/  MinHash, embeddings and grouping; campaign evidence
rule-passages/     Chunk Federal Register rule text into ChromaDB
api-service/       FastAPI service the frontend calls
frontend/          Static page served by nginx
docs/              Setup, data and evidence; MS1 mock-up and architecture figures
docker-compose.yml One service per container plus ChromaDB
.dvc/              DVC config; remote is the GCS bucket
schema.md          Every file and field the pipeline reads and writes, raw through labels, and why
docs/setup.md      Running it from a fresh clone: the demo, the full data, every .env setting, troubleshooting
```

Each container has its own `Dockerfile`, `pyproject.toml` (managed with `uv`) and `src/main.py`. The root `pyproject.toml` is the template new containers copy from.

## Prerequisites

- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) (for local development outside containers)
- A `data.gov` API key, free at https://api.data.gov/signup/ (covers both Regulations.gov and FCC ECFS, 1,000 requests/hour per key)
- Access to the `ac215-undersigned` GCP project and its service-account key

## Setup

The demo needs Docker and one free API key, nothing else:

1. Clone the repo:

   ```bash
   git clone https://github.com/aidaneichman/ac215_Undersigned.git
   cd ac215_Undersigned
   ```

2. Create your environment file and fill in the keys:

   ```bash
   cp .env.example .env
   ```

   Paste your data.gov key on `API_DATA_GOV_KEY`.

`.env.example` defaults to the 40-record demo sample, so the whole chain takes about a minute after the first build. Full instructions, the team path with the versioned data (`dvc pull`), every `.env` setting and a troubleshooting list are in [`docs/setup.md`](docs/setup.md).

## Running the pipeline

One command builds every container, runs the batch stages in order and starts the serving stack:

```bash
docker compose up --build
```

Stage order is enforced in `docker-compose.yml` with `depends_on` conditions: `data-collector` → `data-processor` → `campaign-builder`, and `rule-passages` (which needs ChromaDB) in parallel; `api-service` starts once both chains have completed, then `frontend`. A batch stage that exits non-zero stops everything behind it.

**A first run uses the fixed 40-record sample.** `.env.example` sets `DOCKET_IDS=EPA-HQ-OW-2022-0801` (Lead and Copper Rule Improvements) and `RECORD_IDS_FILE=/app/samples/ms2_ids.txt`, so the collector fetches exactly those 40 records and their attachments in about 40 API calls, and `rule-passages` indexes the proposal that docket's comments answered (88 FR 84878). The whole chain takes about a minute. The sample is described in [`data-collector/samples/`](data-collector/samples/README.md).

To pull more, empty `RECORD_IDS_FILE`. Then `MAX_RECORDS=50` takes the first 50 records of the docket, and an empty `MAX_RECORDS` takes all of it. A whole docket can take hours: the development docket (EPA-HQ-OW-2018-0149) needs about 11 on one key. Use `SHARD` (for example `2/5`) to split a full pull across containers with their own keys. Anything already on disk is skipped, so reruns are quick, and a capped run does not stop a later uncapped one from finishing the index. A key that another job is using is rested for an hour by the collector, so give the pipeline its own key.

Once up:

- Frontend: http://localhost:3000
- API: http://localhost:8000 (`GET /health` returns `"status": "ok"` and how many rule passages it loaded; interactive docs at `/docs`)
- ChromaDB: http://localhost:9000

Stop everything with `docker compose down`.

To run a single stage, e.g. while developing it:

```bash
docker compose run --rm data-processor
```

Each container mounts its own `src/` and the shared `data/` directory, so code edits take effect without a rebuild.

## Data versions

Raw and processed data live in `data/`, tracked with DVC and stored in `gs://ac215-undersigned-data/dvc`. Each container reads a specific DVC-tracked snapshot; record the version here when it changes.

| Container        | Reads                              | Writes                               | Data version |
| ---------------- | ---------------------------------- | ------------------------------------ | ------------ |
| data-collector   | Regulations.gov / ECFS APIs        | `data/raw/<docket>/`                 | `data/raw/EPA-HQ-OW-2018-0149.dvc`; 11,444 details, 4,011 attachment files, 1 failed (403 on a .jpg) |
| | | | `data/raw/EPA-HQ-OAR-2017-0355.dvc` (26,206 details, 9,699 attachment files, 0 failed) |
| | | | `data/raw/EPA-HQ-OW-2022-0801.dvc` (1,589 details, 482 attachment files, 0 failed) |
| data-processor   | `data/raw/<docket>/`               | `data/derived/letters/<docket>/`     | TBD          |
| campaign-builder | `data/derived/letters/<docket>/`   | `data/derived/campaigns/<docket>/`   | TBD          |
| rule-passages    | `data/raw/federal_register/<docket>/` | ChromaDB collection `rule_passages` | TBD       |

Hand labels (200 letter pairs, 100 personalization checks, 50 campaign-to-section mappings) live in `data/labels/` and are DVC-tracked too.

## Containers

<!-- Each owner fills in their section: what it does, inputs and outputs, how to run it alone, and a link to run logs. -->

### data-collector

Pulls one or more Regulations.gov dockets into `data/raw/<docket>/`. It is the only container that talks to the API; everything downstream reads the files it writes.

**Input** (`.env`): `API_DATA_GOV_KEY` (one or more keys, comma-separated; each allows 1,000 requests an hour), `DOCKET_IDS`, and one of three modes:

| mode | settings | what happens | time |
| --- | --- | --- | --- |
| demo (the `.env.example` default) | `RECORD_IDS_FILE=/app/samples/ms2_ids.txt` | fetches exactly the 40 listed records, no index | ~1 min |
| smoke test | `RECORD_IDS_FILE=` empty, `MAX_RECORDS=50` | the first 50 records of the docket | a few min |
| full pull | both empty | the whole docket | ~1 h per 1,000 records per key |

`SHARD=k/n` splits a full pull across n containers; `SKIP_ATTACHMENTS=1` skips file downloads.

**Output** (`data/raw/<docket>/`, schema in [`schema.md`](schema.md)): `comments_index.jsonl` (every comment's id and dates; absent in demo mode), `details/<id>.json` (each record exactly as the API returned it: text, submitter location, receive date, attachment list), `details_index.jsonl` (the few fields later stages need, one line per record), `attachments/<id>/<file>` and `attachments_manifest.jsonl` (the downloaded files and one line per file), `manifest.json` (counts and failures for the run).

**How it runs.** Three stages: list the docket 250 at a time (walking date windows past the API's 5,000-record cap), fetch each record, download each attachment. Files on disk are the state: a record or file that already exists is skipped, so a run can be stopped and restarted at any point, and a docket that was `dvc pull`ed goes straight to the processor. Keys rotate per request and are rested for an hour when their quota is nearly spent; if all keys are resting it sleeps and logs when it will resume. The index is marked complete only if its count equals the API's `totalElements`; otherwise the run fails rather than letting a short index through. A refused attachment (403/404) is logged and skipped.

**What it has produced**, all versioned in DVC (audits in [`docs/evidence/data-collector/`](docs/evidence/data-collector/)):

| docket | records | comments represented | attachment files |
| --- | --- | --- | --- |
| EPA-HQ-OW-2018-0149 (development) | 11,444 | 518,528 | 4,009 |
| EPA-HQ-OAR-2017-0355 (transfer) | 26,206 | 1,713,467 | 9,699 |
| EPA-HQ-OW-2022-0801 (demo) | 1,589 | 101,510 | 482 |

**Why the demo is a fixed list.** The first rows of any docket's index are early individual comments, so a 50-record smoke sample had nothing to group or link. The 40 ids in `data-collector/samples/ms2_ids.txt` are two personalized campaigns, ten organization letters that cite rule sections, and ten individuals; only ids are in git, text comes from the API at run time. See [`data-collector/samples/README.md`](data-collector/samples/README.md).

**Known limits.** The date filter the API uses for paging is read in Eastern time, which cost 538 records before it was found (#27); the count check now catches that class of error. Running the demo on a machine that holds the full lead-and-copper docket rewrites that folder's `manifest.json`; restore with `dvc checkout`, don't `dvc add`.

**Tests:** `cd data-collector && uv run pytest && uv run ruff check .` (18 tests, offline). Scripts in `audit_attachments.py` checks a pull's completeness and finds scanned PDFs, `make_evidence_sample.py` builds the redacted evidence sample.

### data-processor

Converts raw comments and attachments into canonical letters using inline text, DOCX/PDF extraction, and OCR fallback. Preserves source identifiers, hashes signer metadata, and counts tokens with the bge-small tokenizer.

**Inputs:** `data/raw/<docket>/details/`, `attachments_manifest.jsonl`, and downloaded attachments.

**Outputs:** `data/derived/letters/<docket>/`, containing `letters.parquet`, `records.parquet`, `signers.parquet`, and `processing_report.json`.

**Run independently:** Restore the raw sample through DVC and configure `SIGNER_HASH_KEY` in `.env`, then run:

```bash
cd data-processor
uv sync --frozen
uv run ruff check .
uv run pytest -q
cd ..

docker compose build data-processor
docker compose run --rm --no-deps data-processor python src/main.py \
  --docket EPA-HQ-OW-2018-0149 \
  --data-root /app/data \
  --max-records 50 --strict
```

The image carries the pinned tokenizer at `/app/models/bge/tokenizer.json` (downloaded and checksum-verified at build), so `docker compose up` runs this stage with no extra step. The tests do not need it: the one real-tokenizer check skips unless `BGE_TOKENIZER_TEST_PATH` points at a copy. To run the processor outside Docker, fetch a copy with `uv run python fetch_tokenizer.py --out ../data/models/bge/tokenizer.json` and pass that path as `--tokenizer`.

**Validation:** The real 50-record sample completed inside Docker with zero failures. Inspected letter text matched the source attachments. Real campaign-attachment extraction has not yet been validated.

**Run evidence:** [Data-processor validation](docs/evidence/data-processor/README.md)

### campaign-builder

Groups letters into campaigns. Today it holds the first baseline and the scorer every grouping method is
measured with (U-09). MinHash and embedding grouping follow (U-05, U-13).

Under `docker compose up` the container runs `src/main.py`: for each docket in `DOCKET_IDS` it reads
`data/derived/letters/<docket>/letters.parquet`, groups by exact match, and writes
`data/derived/campaigns/<docket>/assignments.parquet`. It exits non-zero if the processor wrote no letters.
Beside it goes `summary.json` with the counts, B-cubed when EPA grouped any of the letters, and the
sha256 of the letters file it read.

- **Exact match** (`src/exact_match.py`). Two letters are one group when their text is identical after
  normalizing: HTML tags from the API removed, case and punctuation ignored, whitespace collapsed. A group
  is named after its earliest `letter_id`. A letter that matches nothing is an individual comment and gets
  no group (`campaign_id` null), and so does any letter under 20 words (`--min-words`): empty bodies and
  "See attached" stubs are identical to each other but are not a campaign (#40). Reads the schema's
  `letters.parquet`, writes `assignments.parquet`
  (`letter_id`, `campaign_id`, `method="exact"`, `similarity=1.0`).
- **B-cubed** (`src/bcubed.py`). Precision, recall and F1 of a grouping against EPA's, letter by letter:
  a letter's precision is the share of its predicted group that shares its EPA campaign, its recall the
  share of its EPA campaign that landed in its group, both averaged over letters. Letters EPA did not group
  (`epa_campaign_id` null) are left out of the score; a letter with no predicted group counts as a group
  of one. `score_frames` takes the two parquet tables directly.

```bash
cd campaign-builder && uv run pytest && uv run ruff check .        # 20 tests, offline
uv run python src/exact_match.py --letters <letters.parquet> --out assignments.parquet --score
```

`--score` prints B-cubed against `epa_campaign_id`. First run on the inline comment bodies of the
development docket: 3,967 letters, 62 in 17 exact-match groups, 3,905 individual. No F1 yet: EPA's
grouping only exists for letters inside campaign attachments, which the processor extracts. Logs and
the groups by size: [`docs/evidence/campaign-builder/`](docs/evidence/campaign-builder/README.md).

### rule-passages

Finds the rule sections a comment argues about. A comment goes in; ranked passages of the proposed rule come out, each with its Federal Register citation, page and section.

**Stages** (`docker compose run --rm rule-passages`, exits 0 when done):

1. **Collect.** Downloads every document filed under each docket in `RULE_DOCKETS` (default: the chain's `DOCKET_IDS`) from the Federal Register API (no key). Saved to `data/raw/federal_register/<docket>/`. Files already on disk are skipped.
2. **Chunk.** Strips the GPO markup, drops the table of contents, tracks headings and the printed page, and packs paragraphs into chunks of about 200 words (`CHUNK_MAX_WORDS`) that never cross a section. A chunk after the first opens with the last sentence or two of the one before (`CHUNK_OVERLAP_WORDS`). Only the document the comments answered is indexed (`COMMENTED_ON` in `config.py`, or `RULE_DOCUMENTS`), since comments cannot argue about text that did not exist yet. Summary, dates, addresses and general-information sections are flagged `procedural` and left out of retrieval by default: letters quote them without arguing about them.
3. **Embed and load.** `BAAI/bge-small-en-v1.5` through ONNX (no PyTorch), vectors stored in the ChromaDB collection `rule_passages` (cosine). Ids are `<document_number>:<index>` and each chunk carries a hash, so a rerun embeds only what changed and removes chunks that no longer belong.

**Look at the result:**

```bash
docker compose run --rm rule-passages python src/main.py outline                      # section references
docker compose run --rm rule-passages python src/main.py query --file /app/data/samples/letter.txt     # add --docket to limit it to one docket
docker compose run --rm rule-passages python src/main.py eval --labels /app/data/labels/campaign_sections.jsonl
docker compose run --rm rule-passages python src/main.py sweep --labels /app/data/labels/campaign_sections.jsonl --sizes 120,250
```

`eval` reports top-1 and top-3 accuracy for BM25 and for the embedding search on hand-mapped campaigns (format in `rule_passages/evaluate.py`; a campaign labeled "nothing specific" is left out of the score). Add `--include-procedural` to `eval` or `sweep` to also search the summary, addresses and similar sections, which measures what excluding them does. `sweep` re-indexes at each chunk size into its own collection and scores both. These are the numbers for the BM25-first, embeddings-second comparison in the MS1 proposal.

**For api-service** (the retrieval contract):

- Collection `rule_passages` at `CHROMA_HOST:CHROMA_PORT`. Document is the passage text. Metadata: `docket_id`, `document_number`, `doc_title`, `citation`, `url`, `publication_date`, `index`, `heading`, `section_ref`, `page`, `procedural`, `sha1`. Query with `where={"procedural": False}` (the retrievers do this by default).
- A query is cleaned of HTML, then embedded with the same model and the prefix in `rule_passages/embedding.py`. `DenseRetriever` and `BM25Retriever` in `rule_passages/retrieve.py` do both and return `Hit` objects. BM25 is built from `PassageStore.chunks()`, so it searches exactly what was indexed. `FusedRetriever` in the same file combines any retrievers into one list by reciprocal rank fusion (it uses ranks only, since BM25 and cosine scores are on different scales). The API's `"merged"` method and the evaluation both use it, so they fuse the same way.
- `Hit.to_dict()` is the JSON shape of a result (`retriever`, `rank`, `score`, `id`, `docket_id`, `document_number`, `citation`, `page`, `section_ref`, `heading`, `text`). The command line prints it and the API should return it as is, so a field added there reaches both.
- Both retrievers take an optional `docket_id`, so a request can be "this letter, from this docket". All configured dockets share the collection, and indexing one never deletes another's chunks. A docket that yields no chunks stops the stage with an error instead of emptying the index.
- `section_ref` is a path such as `III/D/1` (Roman numeral, letter, number) or `PART 328/§ 328.3`.

**Tests:** `cd rule-passages && uv run pytest` (79 tests, offline, no model download). `uv run ruff check .` is clean. Example run and logs: [`docs/evidence/rule-passages/`](docs/evidence/rule-passages/README.md).

### api-service

The HTTP service the frontend calls. It reads the ChromaDB collection `rule_passages` that rule-passages fills and writes nothing. At startup it loads the embedding model and reads every passage once, so a request only searches. It refuses to start if the collection is empty: run rule-passages first. The retrieval code is not copied: the image gets `rule_passages` from `rule-passages/src` through a second build context (`additional_contexts` in `docker-compose.yml`), and the bge-small model is baked into the image.

**Endpoints** (also browsable at http://localhost:8000/docs):

- `GET /health`: `{"status": "ok", "passages": 538, "dockets": ["EPA-HQ-OW-2018-0149"]}`.
- `POST /retrieve`: a letter in, the rule passages it argues about out.

  | Field | Default | Meaning |
  |---|---|---|
  | `text` | required | The letter. HTML is cleaned the same way as in rule-passages. Blank text is rejected |
  | `k` | `3` | 1 to 50. Passages per retriever for `bm25`, `dense` and `both`; passages in total for `merged` |
  | `method` | `"both"` | `"bm25"`, `"dense"` (embeddings), `"both"` (two separate lists) or `"merged"` (one list, combined by rank) |
  | `docket_id` | none | Only search this docket's rule text. A docket the index does not hold returns no hits |

  The response is `{"hits": [...]}`, each hit in the shape `Hit.to_dict()` defines in rule-passages (`retriever`, `rank`, `score`, `id`, `docket_id`, `document_number`, `citation`, `page`, `section_ref`, `heading`, `text`). With `"both"`, BM25 hits come first, then embedding hits, as two lists that are not sorted together because their scores are on different scales. `"merged"` returns one list combined by reciprocal rank fusion: each retriever is searched 50 deep and a passage scores the sum of `1 / (60 + rank)` over the lists it appears in, so passages both retrievers rank well come first. Its hits have `retriever: "merged"`, and their `score` is that fused score, which cannot be compared with BM25 or cosine scores. Procedural sections are never returned. Invalid input gets a 422 naming the field.

**Run it alone** (ChromaDB must be up and filled: `docker compose up -d chromadb && docker compose run --rm rule-passages`):

```bash
docker compose up -d --build --no-deps api-service
curl -s -X POST localhost:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"text": "The rule removes protection for ephemeral streams and intermittent tributaries", "k": 2}'
# One merged list instead of two
curl -s -X POST localhost:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"text": "The rule removes protection for ephemeral streams and intermittent tributaries", "k": 3, "method": "merged"}'
```

**Develop without Docker**, with reload on save, against the same ChromaDB (published on port 9000):

```bash
cd api-service
PYTHONPATH=../rule-passages/src CHROMA_HOST=localhost CHROMA_PORT=9000 \
  uv run uvicorn main:app --app-dir src --reload --port 8000
```

**Tests:** `cd api-service && uv run pytest && uv run ruff check .` (16 tests, offline: an in-memory ChromaDB and a fake embedder). Example run and logs: [`docs/evidence/api-service/`](docs/evidence/api-service/README.md).

### frontend

TBD

## Evidence (MS2)

- Running VM screenshot: `docs/evidence/vm.png` (TBD)
- End-to-end run logs: `docs/evidence/run.log` (TBD)
- Sample input → output: `docs/evidence/sample/` (TBD)

## Changes since the Milestone 1 mock

TBD

## Milestones

| Milestone | Due    | Scope                                                                 |
| --------- | ------ | --------------------------------------------------------------------- |
| MS2       | 20 Oct | Containers, DVC, FCC download, hand labels, baselines, vector DB, app skeleton |
| MS3       | 12 Nov | Fine-tuning on Vertex AI with W&B, Vertex pipeline, campaign evidence, live API on Cloud Run |
| MS4       | 1 Dec  | Frontend, CI, tests, FCC and transfer evaluations                     |
| MS5       | 11 Dec | GKE, CI/CD, gated retraining, video, blog, public test sets           |