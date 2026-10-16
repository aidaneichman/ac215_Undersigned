# Baseline: finding the cited rule section (EPA-HQ-OW-2022-0801)

Built 2026-10-16 17:05 UTC by `python src/main.py baseline` (rule-passages).

**Test set.** 155 passages from 5 letters that cite at least one section of the rule (2023-26148), 15 sections in all. The query is the passage with its citations masked; the answer is the section or sections it cites.

- `passages.parquet` sha256 `3ba44658a1d3b64053e58dbdab3f1cc7b7cd416bad148ea1f480e192e075a842`
- `links.parquet` sha256 `58411ef444aa3ea59c6a7ee40b64f054ccc291522acf307d98f29a15ee1bd347`

**Searched.** 1096 chunks of the rule, procedural sections left out; 281 of them are regulatory text.

**Scoring.** Found at k: one of the top k results is in a cited section. Regulatory text only: results outside the regulatory text are dropped before taking the top k. Seconds per 1,000 passages is search time on the machine that built this file, including embedding the query.

| Method | Top-1 | Top-3 | Top-1, regulatory text only | Top-3, regulatory text only | Seconds per 1,000 passages |
|---|---|---|---|---|---|
| BM25 | 31.6% | 46.5% | 65.8% | 83.9% | 2.4 |
| Embeddings (bge-small) | 12.9% | 31.6% | 61.9% | 81.3% | 50.8 |
| BM25 + embeddings, rank fusion | 21.3% | 37.4% | 68.4% | 84.5% | 59.3 |

## By letter

Passages found at top-1 / top-3, whole rule.

| Letter | Passages | BM25 | Embeddings (bge-small) | BM25 + embeddings, rank fusion |
|---|---|---|---|---|
| EPA-HQ-OW-2022-0801-0775 | 19 | 5 / 8 | 3 / 5 | 3 / 4 |
| EPA-HQ-OW-2022-0801-0849 | 9 | 3 / 4 | 2 / 3 | 4 / 4 |
| EPA-HQ-OW-2022-0801-0935 | 33 | 9 / 15 | 7 / 15 | 8 / 15 |
| EPA-HQ-OW-2022-0801-0972 | 69 | 22 / 31 | 7 / 20 | 14 / 25 |
| EPA-HQ-OW-2022-0801-1131 | 25 | 10 / 14 | 1 / 6 | 4 / 10 |
