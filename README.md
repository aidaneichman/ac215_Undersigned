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
docs/              MS1 mock-up and architecture figures
docker-compose.yml One service per container plus ChromaDB
.dvc/              DVC config; remote is the GCS bucket
```

Each container has its own `Dockerfile`, `pyproject.toml` (managed with `uv`) and `src/main.py`. The root `pyproject.toml` is the template new containers copy from.

## Prerequisites

- Docker and Docker Compose
- [uv](https://docs.astral.sh/uv/) (for local development outside containers)
- A `data.gov` API key, free at https://api.data.gov/signup/ (covers both Regulations.gov and FCC ECFS, 1,000 requests/hour per key)
- Access to the `ac215-undersigned` GCP project and its service-account key

## Setup

1. Clone the repo and check out the milestone branch:

   ```bash
   git clone https://github.com/aidaneichman/ac215_Undersigned.git
   cd ac215_Undersigned
   ```

2. Create your environment file and fill in the keys:

   ```bash
   cp .env.example .env
   ```

   Five `API_DATA_GOV_KEYS` bring the development docket pull from about 11 hours to about 2.5.

3. Put the GCP service-account JSON at `secrets/undersigned-key.json`. The `secrets/` directory is git-ignored; never commit a key.

4. Pull the data version you need (see [Data versions](#data-versions)):

   ```bash
   uv sync
   uv run dvc pull
   ```

## Running the pipeline

One command builds every container, runs the batch stages in order and starts the serving stack:

```bash
docker compose up --build
```

Stage order is enforced in `docker-compose.yml` with `depends_on` conditions: `data-collector` → `data-processor` → `campaign-builder`, and `rule-passages` (which needs ChromaDB) in parallel; `api-service` starts once both chains have completed, then `frontend`. A batch stage that exits non-zero stops everything behind it.

**For a first run, leave `MAX_RECORDS=50` as it is in `.env`.** The collector then pulls 50 records and their attachments instead of the whole development docket, which takes minutes, not the 11 hours the full docket needs on one key. Set it blank to pull everything, and use `SHARD` (for example `2/5`) to split a full pull across containers with their own keys. Anything already on disk is skipped, so reruns are quick, and a capped run does not stop a later uncapped one from finishing the index. A key that another job is using is rested for an hour by the collector, so give the pipeline its own key.

Once up:

- Frontend: http://localhost:3000
- API: http://localhost:8000 (`GET /health` returns `{"status": "ok"}`)
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
| data-collector   | Regulations.gov / ECFS APIs        | `data/raw/<docket>/`                 | `data/raw/EPA-HQ-OW-2018-0149.dvc`, partial (5,160 of 11,444 details) |
| data-processor   | `data/raw/<docket>/`               | `data/letters/<docket>.parquet`      | TBD          |
| campaign-builder | `data/letters/`, `data/labels/`    | `data/campaigns/<docket>/`           | TBD          |
| rule-passages    | `data/raw/federal_register/<docket>/` | ChromaDB collection `rule_passages` | TBD       |

Hand labels (200 letter pairs, 100 personalization checks, 50 campaign-to-section mappings) live in `data/labels/` and are DVC-tracked too.

## Containers

<!-- Each owner fills in their section: what it does, inputs and outputs, how to run it alone, and a link to run logs. -->

### data-collector

TBD

### data-processor

TBD

### campaign-builder

TBD. Baseline results: TBD.

### rule-passages

Finds the rule sections a comment argues about. A comment goes in; ranked passages of the proposed rule come out, each with its Federal Register citation, page and section.

**Stages** (`docker compose run --rm rule-passages`, exits 0 when done):

1. **Collect.** Downloads every document filed under each docket in `RULE_DOCKETS` from the Federal Register API (no key). Saved to `data/raw/federal_register/<docket>/`. Files already on disk are skipped.
2. **Chunk.** Strips the GPO markup, drops the table of contents, tracks headings and the printed page, and packs paragraphs into chunks of about 200 words (`CHUNK_MAX_WORDS`) that never cross a section. A chunk after the first opens with the last sentence or two of the one before (`CHUNK_OVERLAP_WORDS`). Only the document the comments answered is indexed (`COMMENTED_ON` in `config.py`, or `RULE_DOCUMENTS`), since comments cannot argue about text that did not exist yet. Summary, dates, addresses and general-information sections are flagged `procedural` and left out of retrieval by default: letters quote them without arguing about them.
3. **Embed and load.** `BAAI/bge-small-en-v1.5` through ONNX (no PyTorch), vectors stored in the ChromaDB collection `rule_passages` (cosine). Ids are `<document_number>:<index>` and each chunk carries a hash, so a rerun embeds only what changed and removes chunks that no longer belong.

**Look at the result:**

```bash
docker compose run --rm rule-passages python src/main.py outline                      # section references
docker compose run --rm rule-passages python src/main.py query --file /app/data/samples/letter.txt
docker compose run --rm rule-passages python src/main.py eval --labels /app/data/labels/campaign_sections.jsonl
docker compose run --rm rule-passages python src/main.py sweep --labels /app/data/labels/campaign_sections.jsonl --sizes 120,250
```

`eval` reports top-1 and top-3 accuracy for BM25 and for the embedding search on hand-mapped campaigns (format in `rule_passages/evaluate.py`; a campaign labeled "nothing specific" is left out of the score). `sweep` re-indexes at each chunk size into its own collection and scores both. These are the numbers for the BM25-first, embeddings-second comparison in the MS1 proposal.

**For api-service** (the retrieval contract):

- Collection `rule_passages` at `CHROMA_HOST:CHROMA_PORT`. Document is the passage text. Metadata: `docket_id`, `document_number`, `doc_title`, `citation`, `url`, `publication_date`, `index`, `heading`, `section_ref`, `page`, `procedural`, `sha1`. Query with `where={"procedural": False}` (the retrievers do this by default).
- A query is cleaned of HTML, then embedded with the same model and the prefix in `rule_passages/embedding.py`. `DenseRetriever` and `BM25Retriever` in `rule_passages/retrieve.py` do both and return `Hit` objects. BM25 is built from `PassageStore.chunks()`, so it searches exactly what was indexed.
- `section_ref` is a path such as `III/D/1` (Roman numeral, letter, number) or `PART 328/§ 328.3`.

**Tests:** `cd rule-passages && uv run pytest` (64 tests, offline, no model download). `uv run ruff check .` is clean. Example run and logs: [`docs/evidence/rule-passages/`](docs/evidence/rule-passages/README.md).

### api-service

Endpoints:

- `GET /health` — liveness check

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