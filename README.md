# Undersigned: Who Is Behind a Public Comment Campaign?

AC215 · Aidan Eichman, Aadil Jamari, Livia Jonnatan, Andrew Yuan, Rishi Jain

When a federal agency proposes a rule, most of the public comments it receives are form letters sent by supporters of an advocacy group. Real campaigns and fraudulent ones (stolen names, reworded templates) look the same on arrival. Undersigned takes a rulemaking docket, finds its comment campaigns across exact copies, personalized letters and LLM-reworded letters, and shows an analyst each campaign's size, timing, sponsor, arguments and signer evidence, without labelling any individual comment as fake.

Development docket: EPA-HQ-OW-2018-0149 (2019 "waters of the United States" rule, 518,473 comments). Transfer docket: EPA-HQ-OAR-2017-0355 (Clean Power Plan repeal). Case studies: FCC 17-108 (net neutrality).

Milestone 1 proposal: `main.tex` / `milestone1.tex`. Application mock: `docs/`.

## Architecture

![The design, and where each part stands](docs/architecture/design-and-status.png)

Green runs in main from one command; amber is partly there; faded is not started. The second page,
[`solution.png`](docs/architecture/solution.png), shows who uses the system, where each container runs,
its ports and mounts, and what persists, with a table of what each container is given at build and at
start. Both pages: [PDF](docs/architecture/undersigned-architecture.pdf) and
[HTML](docs/architecture/undersigned-architecture.html).

## Repository layout

```
data-collector/    Pull comments and attachments from Regulations.gov and FCC ECFS
data-processor/    One canonical record per letter; PDF text, OCR, signer hashing
campaign-builder/  MinHash, embeddings and grouping; campaign evidence
rule-passages/     Chunk Federal Register rule text into ChromaDB
api-service/       FastAPI service the frontend calls
frontend/          React rule page served by nginx; calls the API through /api
docs/              Setup, data and evidence; architecture diagrams; MS1 mock-up and figures
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

Stage order is enforced in `docker-compose.yml` with `depends_on` conditions: `data-collector` → `data-processor` → `campaign-builder` → `passage-stage`, with `rule-passages` (which needs ChromaDB) in parallel and finished before `passage-stage` starts; `api-service` starts once both chains have completed, then `frontend`. A batch stage that exits non-zero stops everything behind it.

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
| passage-stage    | `data/derived/letters/`, `data/derived/campaigns/`, rule text | `data/derived/passages/<docket>/` | TBD |
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
  --record-ids-file "" \
  --max-records 50 --strict
```

`--record-ids-file ""` turns off the demo list from `.env`, which would otherwise override `--max-records`.

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

### passage-stage

Splits each distinct letter into passages and reads the rule sections it cites (U-26, #43). It keeps one
letter per exact-match group, so a campaign's copies are read once.

- **Passages** (`src/passages.py`). The processor stores a letter as one line, so a passage is a run of
  whole sentences of about 120 words and never more than 250. A short last run joins the one before it.
  Sentences come from rule-passages' splitter, which does not split after "Sec." or "C.F.R.", so a
  citation is never cut away from its number.
- **Citations** (`src/citations.py`). The patterns measured in the linking test: a section sign
  (`§ 141.84(b)(2)`), the word section in any case (`SECTION 141.84`), a CFR reference (`40 CFR 141.85`),
  and a bare number with a paragraph (`141.84(a)`) only when that number is a section of the rule. On 80
  sampled citations, 6 (7.5%) were not about a section of the proposal. In a list, a later number counts
  only if it is in the same CFR part or is a section of the rule, so "40 CFR 141.80(c) to 0.010 mg/L" is
  one citation. A range (`§ 141.80–141.93`, `141.84 through 141.86`) links every section of the rule
  between its ends.
- **Resolution.** Each cited number is mapped to rule-passages' `section_ref` (for example
  `PART 141/§ 141.84`), read with rule-passages' own chunking from the rule text it collected. A number
  that is not a section of the rule keeps its `citation_raw` with `section_ref` null. A "section 2.4"
  style reference with a first number below 100 is read as the letter's own outline and left out. A
  section sign or "CFR" is always kept, so `§ 60.5740(a)` stays as an unresolved link.

Writes `data/derived/passages/<docket>/`: `passages.parquet` (one row per passage, with `text_masked`,
the text with every citation replaced, for scoring retrieval without handing it the answer),
`links.parquet` (one row per passage and cited section: `passage_id`, `letter_id`, `docket_id`,
`section_ref`, `citation_raw`, `source`) and `summary.json` (counts and the sha256 of the letters file
read). It exits non-zero if the letters, the groups or the rule text are missing. A rule with no
numbered sections, such as the Clean Power Plan repeal, still gets passages, with every link
unresolved, so the API still starts.

Only cited passages get links for now. Most passages cite nothing; linking those is the reader's job (MS3).

```bash
cd passage-stage && uv run pytest && uv run ruff check .        # 33 tests, offline
docker compose run --rm passage-stage                            # after campaign-builder and rule-passages
```

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
docker compose run --rm rule-passages python src/main.py baseline                     # U-28 table, in data/derived/baseline/<docket>/
```

`eval` reports top-1 and top-3 accuracy for BM25 and for the embedding search on hand-mapped campaigns (format in `rule_passages/evaluate.py`; a campaign labeled "nothing specific" is left out of the score). Add `--include-procedural` to `eval` or `sweep` to also search the summary, addresses and similar sections, which measures what excluding them does. `sweep` re-indexes at each chunk size into its own collection and scores both. These are the numbers for the BM25-first, embeddings-second comparison in the MS1 proposal.

**For api-service** (the retrieval contract):

- Collection `rule_passages` at `CHROMA_HOST:CHROMA_PORT`. Document is the passage text. Metadata: `docket_id`, `document_number`, `doc_title`, `citation`, `url`, `publication_date`, `index`, `heading`, `section_ref`, `page`, `procedural`, `sha1`. Query with `where={"procedural": False}` (the retrievers do this by default).
- A query is cleaned of HTML, then embedded with the same model and the prefix in `rule_passages/embedding.py`. `DenseRetriever` and `BM25Retriever` in `rule_passages/retrieve.py` do both and return `Hit` objects. BM25 is built from `PassageStore.chunks()`, so it searches exactly what was indexed. `FusedRetriever` in the same file combines any retrievers into one list by reciprocal rank fusion (it uses ranks only, since BM25 and cosine scores are on different scales). The API's `"merged"` method and the evaluation both use it, so they fuse the same way.
- `Hit.to_dict()` is the JSON shape of a result (`retriever`, `rank`, `score`, `id`, `docket_id`, `document_number`, `citation`, `page`, `section_ref`, `heading`, `text`). The command line prints it and the API should return it as is, so a field added there reaches both.
- Both retrievers take an optional `docket_id`, so a request can be "this letter, from this docket". All configured dockets share the collection, and indexing one never deletes another's chunks. A docket that yields no chunks stops the stage with an error instead of emptying the index.
- `section_ref` is a path such as `III/D/1` (Roman numeral, letter, number) or `PART 328/§ 328.3`.

**Tests:** `cd rule-passages && uv run pytest` (87 tests, offline, no model download). `uv run ruff check .` is clean. Example run and logs: [`docs/evidence/rule-passages/`](docs/evidence/rule-passages/README.md).

### api-service

The HTTP service the frontend calls. It reads the ChromaDB collection `rule_passages` that rule-passages fills, and passage-stage's `links.parquet` and `passages.parquet` when they exist, and writes nothing. At startup it loads the embedding model and reads every passage and every link once, so a request only searches. It refuses to start if the collection is empty: run rule-passages first. A docket with no passage-stage files keeps its citation counts and citing-passage lists `null` (unknown, not zero). The retrieval code is not copied: the image gets `rule_passages` from `rule-passages/src` through a second build context (`additional_contexts` in `docker-compose.yml`), and the bge-small model is baked into the image. Compose mounts `./data/derived/passages` into the API read-only.

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
- `GET /rules/{docket_id}/sections`: the sections of the rule that docket's comments answered, for the rule page. The response is `{"docket_id": ..., "unresolved_citations": ..., "sections": [...]}`, one entry per section in reading order. `unresolved_citations` is how many links have a null `section_ref` (a citation that is not a section of this rule), or `null` when there is no links file.

  | Field | Example | Meaning |
  |---|---|---|
  | `section_ref` | `"III/D/1"`, `"PART 328/§ 328.3"` | The same key `/retrieve` hits carry, so a hit can be placed on the page |
  | `parent_ref` | `"III/D"` | The section it sits under; `null` at the top level |
  | `heading`, `title` | `"III. Proposed Definition … > D. Tributaries"`, `"D. Tributaries"` | The full heading path, and its last part |
  | `depth` | `2` | 1 for a top-level section |
  | `document_number`, `citation` | `"2019-00791"`, `"84 FR 4154"` | Which Federal Register document |
  | `page` | `4173` | Where the section's first passage starts |
  | `rule_passages` | `46` | Passages of rule text in the section, including the sections under it |
  | `citing_passages`, `citing_letters` | `39`, `5` | Distinct comment passages, and distinct letters, that cite the section or one under it. `0` once the links file exists and nobody cites it; `null` without that file (unknown, not zero) |

  Every heading above a section gets an entry, just before its first child, even with no text of its own (`III/D` when all its text is under `III/D/1`), because commenters cite "Section III.D". A section's counts include the sections under it. One passage that cites two sections counts in both, and once in the parent. Procedural sections are left out, as in `/retrieve`. A docket the index does not hold is a 404 naming the dockets it does.

  The passage stage only resolves regulatory citations (`§ 141.84`, `PART 141`). Preamble headings such as `V/B` therefore show `0` even when letters argue about them: that is the link reader's limit, not a claim that nobody discussed the preamble.
- `GET /rules/{docket_id}/passages?section_ref=...`: the comment passages that cite a section or one under it, for the rule page's details panel. `section_ref` is a query parameter because refs contain `/`. `limit` (1 to 200, default 50) and `offset` (default 0) page the list; `total` is the count across all pages.

  The response is `{"docket_id", "section_ref", "total", "passages"}`. Each passage has `passage_id`, `letter_id`, `index` (its place in the letter), `text`, `n_words`, and `citations` (the `section_ref` and `citation_raw` it makes inside this section). Order is by letter, then by position in the letter. `text` is the letter as written, not `text_masked`, so the citations stay visible. A parent includes its children's passages, so the list agrees with the rolled-up counts. A docket or section the index does not hold is a 404. Without a passage-stage file, `total` and `passages` are `null`.

**Run it alone** (ChromaDB must be up and filled: `docker compose up -d chromadb && docker compose run --rm rule-passages`). Citation counts and citing passages also need passage-stage's files under `data/derived/passages/`.

```bash
docker compose up -d --build --no-deps api-service
curl -s -X POST localhost:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"text": "The rule removes protection for ephemeral streams and intermittent tributaries", "k": 2}'
# One merged list instead of two
curl -s -X POST localhost:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"text": "The rule removes protection for ephemeral streams and intermittent tributaries", "k": 3, "method": "merged"}'
# The rule's sections, for the rule page
curl -s localhost:8000/rules/EPA-HQ-OW-2018-0149/sections
# Comment passages citing a section of the lead and copper rule (children included)
curl -sG localhost:8000/rules/EPA-HQ-OW-2022-0801/passages \
  --data-urlencode 'section_ref=PART 141/§ 141.84'
```

**Develop without Docker**, with reload on save, against the same ChromaDB (published on port 9000):

```bash
cd api-service
PYTHONPATH=../rule-passages/src CHROMA_HOST=localhost CHROMA_PORT=9000 \
  uv run uvicorn main:app --app-dir src --reload --port 8000
```

**Tests:** `cd api-service && uv run pytest && uv run ruff check .` (47 tests, offline: an in-memory ChromaDB and a fake embedder). Example run and logs: [`docs/evidence/api-service/`](docs/evidence/api-service/README.md).

### frontend

The rule page: the sections of the rule a docket's comments answered, with a count beside each, from `GET /rules/{docket_id}/sections`. React 19 built with Vite, plain JavaScript and CSS, served by nginx on port 3000.

- **Which rule:** `?docket=EPA-HQ-OW-2022-0801` in the address picks one. Without it the page shows the first docket `GET /health` lists.
- **The table:** every section in reading order, indented by depth, with its Federal Register page, its rule passages, and the citing passages and letters. Citing counts show "—" while the API sends `null` (not counted yet, not zero).
- **Details:** clicking a section opens a panel with its full heading path (titles repeat, for example "1. What are the agencies proposing?" under every part of III of the 2019 rule), its citation linked to federalregister.gov, its page and its counts. The list of comment passages that cite it is still a placeholder; the API now serves them at `GET /rules/{docket_id}/passages`.

The page only calls relative `/api/...` URLs. In the container, nginx forwards them to `api-service:8000` (`frontend/nginx.conf`), so the browser talks to one origin and the API needs no CORS. nginx looks the API up when a request arrives, not at startup, so the page loads while the API is still starting and shows the error instead of nginx refusing to start.

**Run it** (the API must be up; the full `docker compose up --build` starts it):

```bash
docker compose up -d --build --no-deps frontend
# then open http://localhost:3000/?docket=EPA-HQ-OW-2022-0801
```

**Develop without Docker**, with reload on save. Vite's server forwards `/api` to the API on `localhost:8000`, as nginx does:

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

**Tests:** `cd frontend && npm test` (14 tests with Vitest and React Testing Library in a simulated browser; `fetch` is faked, so no API is needed). CI runs them and `npm run build` in the `frontend` job. Screenshot and request log: [`docs/evidence/frontend/`](docs/evidence/frontend/README.md).

## Evidence (MS2)

- Running VM screenshot: `docs/evidence/vm.png` (TBD)
- End-to-end run logs: `docs/evidence/run.log` (TBD)
- Sample input → output: `docs/evidence/sample/` (TBD)

## Changes since the Milestone 1 mock

TBD

## Targets, uncertainty, scope and risks (MS2)

From the MS1 feedback: absolute targets next to the baselines, how uncertainty is reported, which goals
are stretch, and the misuse and presentation risks. **The targets are proposals for the team to agree on
before the MS2 presentation.**

### Targets

| Measure | Target | Where we are |
|---|---|---|
| Linking: right section first, on held-out passages that cite one | At least 69%, aim 75% | Large model 75.4% (69.5 to 81.5). Small model 69.0% (62.3 to 75.5). Our reranker 65.9% (59.3 to 72.2). Hybrid search 53.0% (45.8 to 60.2). 232 passages, seven dockets, prototype runs |
| Reading cost | At most $5 per 1,000 passages, keeping at least 94% of the large model's accuracy | Cascade 71.1% (64.8 to 77.4) at $4.82, against $19.58 for the large model alone. The cutoff was chosen on the same passages, so it is set again on held-out data |
| Quotes shown to users | 100% verbatim in the source letter, checked by code | 683 of 683 in the reading prototype, after one retry |
| Grouping: B-cubed F1 on letters EPA grouped | At least 0.90 | Not met in the repository. Exact match finds 2 of 20 campaign letters in the sample, because those campaigns are personalized. Shared-phrase grouping is #5 |
| `/retrieve` latency | p90 at most 250 ms on a laptop. Cloud Run target set at MS3 | p90 119 ms, p50 67 ms, p99 192 ms over 200 real passages ([evidence](docs/evidence/api-service/retrieve-latency.json), `scripts/retrieve_latency.py`) |
| Serving cost per request | No model call at request time | Met. The API reads a stored index. Model cost is paid once per docket in batch: about $17 for the lead and copper docket's 896 passages with the large model, about $4 with the cascade |
| One-command run on the sample | Under 5 minutes from a fresh clone | About 1.5 minutes ([evidence](docs/evidence/README.md)) |

For reference, two of us labeled the same 30 passages without seeing each other's answers and gave the same
label on 21 (95% interval 51% to 85%). A model scored against one reader cannot meaningfully beat the rate at
which two readers agree.

### How uncertainty is reported

- Every accuracy has a 95% interval from 2,000 bootstrap resamples of **organizations** within each docket.
  Passages from one letter are not independent, so resampling passages would make intervals too narrow.
- Results are reported per docket across the seven dockets, and pooled. The dockets play the role the
  sponsor folds played in MS1: a method that only works on one docket shows up as a spread.
- Two methods are compared on the same passages, as a paired difference with its interval. In the linking
  test the large model beat hybrid search by 22.8 points (14.9 to 30.4) on the same 232 passages.
- Small hand-checked sets get exact binomial intervals, as above.
- A target counts as met when the lower end of the interval clears it, not the point estimate.

### Core and stretch

| Core: in scope for MS2 to MS5 | Stretch: only if the core is on time |
|---|---|
| One-command pipeline, DVC, CI | MCP server |
| Grouping by shared phrases | Showing conflicts between positions to users |
| Passage stage and citation links | A distilled linker that beats the hosted small model |
| Reader with the small-then-large cascade and the quote check | Topic-level linking (preamble mapped to provisions) |
| API and rule page | Reworded-letter stress test of the grouper |
| A Vertex AI training run tracked in W&B, Cloud Run, Kubernetes | Running every open rule |
| | Analysts using it, with their corrections feeding training |

### Risks and responsible use

- **The paste-a-comment endpoint** (`POST /retrieve`) takes any text up to 50,000 characters and returns rule
  passages. It makes no claim about who wrote the text. Request bodies are not logged or stored: the server
  logs the client address, method, path and status, never the text. A public deployment adds a rate limit.
- **People.** Signer names are hashed with a secret key and never stored or shown in clear. Nothing is
  reported per person. Organizations are named because they file in their own name. The system never says a
  comment or campaign is fake: a missing sponsor or a form letter is not evidence of fraud.
- **Presenting model output.** Every claim on the rule page carries a word-for-word quote and a link to the
  original letter. Model-made links are marked as such. A passage that is not about one provision is kept
  apart, never forced onto a paragraph. Conflicts are shown only after a second check. Numbers come with
  their intervals, and counts say whether they count letters or people.
- **Text in letters is data, not instructions.** Attachments can contain text aimed at a model. The reader
  treats them as evidence only, and a quote that is not in the source letter is dropped by code.

## Milestones

| Milestone | Due    | Scope                                                                 |
| --------- | ------ | --------------------------------------------------------------------- |
| MS2       | 20 Oct | Containers, DVC, FCC download, hand labels, baselines, vector DB, app skeleton |
| MS3       | 12 Nov | Fine-tuning on Vertex AI with W&B, Vertex pipeline, campaign evidence, live API on Cloud Run |
| MS4       | 1 Dec  | Frontend, CI, tests, FCC and transfer evaluations                     |
| MS5       | 11 Dec | GKE, CI/CD, gated retraining, video, blog, public test sets           |