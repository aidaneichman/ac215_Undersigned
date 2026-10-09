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
| rule-passages    | Federal Register rule text         | ChromaDB collection `rule_passages`  | TBD          |

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

TBD. Example retrieval (query → retrieved rule sections): TBD.

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