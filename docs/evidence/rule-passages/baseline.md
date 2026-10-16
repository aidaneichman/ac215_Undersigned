# Baseline: finding the cited rule section (EPA-HQ-OW-2022-0801)

Built 2026-10-16 16:24 UTC by `python src/main.py baseline` (rule-passages).

**Test set.** 155 passages from 5 letters that cite at least one section of the rule (2023-26148), 15 sections in all. The query is the passage with its citations masked; the answer is the section or sections it cites.

- `passages.parquet` sha256 `b0b4a9e984061fd88c99d1e7f8ea26992c8693646b05c26585826a81790d905c`
- `links.parquet` sha256 `d4a5fb5f65bb9d84f170387fef0bf8dcd4722ab38f7cfc9cb9d64dadad8a0ac6`

**Searched.** 1096 chunks of the rule, procedural sections left out; 281 of them are regulatory text.

**Scoring.** Found at k: one of the top k results is in a cited section. Regulatory text only: results outside the regulatory text are dropped before taking the top k. Seconds per 1,000 passages is search time on the machine that built this file, including embedding the query.

| Method | Top-1 | Top-3 | Top-1, regulatory text only | Top-3, regulatory text only | Seconds per 1,000 passages |
|---|---|---|---|---|---|
| BM25 | 30.3% | 45.8% | 63.2% | 81.9% | 3.7 |
| Embeddings (bge-small) | 14.2% | 30.3% | 59.4% | 81.3% | 69.6 |
| BM25 + embeddings, rank fusion | 20.6% | 38.7% | 63.2% | 84.5% | 75.6 |

## By letter

Passages found at top-1 / top-3, whole rule.

| Letter | Passages | BM25 | Embeddings (bge-small) | BM25 + embeddings, rank fusion |
|---|---|---|---|---|
| EPA-HQ-OW-2022-0801-0775 | 19 | 5 / 8 | 3 / 5 | 3 / 4 |
| EPA-HQ-OW-2022-0801-0849 | 9 | 3 / 4 | 2 / 3 | 4 / 4 |
| EPA-HQ-OW-2022-0801-0935 | 33 | 9 / 15 | 7 / 15 | 8 / 15 |
| EPA-HQ-OW-2022-0801-0972 | 69 | 20 / 30 | 9 / 18 | 13 / 27 |
| EPA-HQ-OW-2022-0801-1131 | 25 | 10 / 14 | 1 / 6 | 4 / 10 |
