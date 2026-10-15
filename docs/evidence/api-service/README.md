# api-service evidence

Real runs of the `api-service` container (`docker compose up -d --build --no-deps api-service`) against the
ChromaDB service from `docker-compose.yml`, after `docker compose run --rm rule-passages` had loaded the
538 passages of the 2019 proposed rule (`84 FR 4154`). First captured on 9 Oct 2026 (#35); re-captured on
13 Oct 2026 after `k` went up to 50 and `method="merged"` was added (#37). Both times on a laptop.

| File | What it shows |
| --- | --- |
| `startup.log` | The container's log: 538 passages loaded at startup, then the four letter-0390 requests below (`both`, `merged` with `k=3`, `merged` with `k=50`, `k=51`) with their status codes |
| `curl-session.txt` | `/health`, `POST /retrieve` with both retrievers, a merged list, `k=50` accepted, a docket the index does not hold (no hits), and a bad request (422 naming all three wrong fields, including `k` above 50) |
| `retrieve-letter-0390.json` | The full response for a real comment, `EPA-HQ-OW-2018-0149-0390` (anonymous), with `k=3` and both retrievers. Re-run on 13 Oct: same passages, same scores |
| `retrieve-letter-0390-merged.json` | The same letter with `k=3` and `method="merged"` |
| `pytest.txt` | The 22 offline tests, by name |

## Same answer as the rule-passages command line

`retrieve-letter-0390.json` is the API's answer for the letter used in
[`../rule-passages/query-letter-0390.json`](../rule-passages/query-letter-0390.json), which came from
`python src/main.py query` in the rule-passages container. The six hits are the same passages in the same
order with the same scores:

| Retriever | # | Passage | Score (API) | Score (command line) | Section |
|---|---|---|---|---|---|
| bm25 | 1 | `2019-00791:0187` | 72.0219 | 72.0219 | `III/D/1` |
| bm25 | 2 | `2019-00791:0159` | 64.4882 | 64.4882 | `III/D/1` |
| bm25 | 3 | `2019-00791:0158` | 58.6361 | 58.6361 | `III/D/1` |
| dense | 1 | `2019-00791:0161` | 0.8297 | 0.8297 | `III/D/1` |
| dense | 2 | `2019-00791:0160` | 0.8252 | 0.8252 | `III/D/1` |
| dense | 3 | `2019-00791:0155` | 0.8092 | 0.8092 | `III/D/1` |

So the image runs the same retrieval code and the same model as rule-passages. The API's hits also carry
`docket_id` and `document_number`, which `Hit.to_dict()` added after the command-line evidence was saved.

## Merged list

`retrieve-letter-0390-merged.json` is the same letter with `"method": "merged"`. Each retriever is searched
50 deep, and a passage scores `1 / (60 + rank)` for every list it appears in. The ranks below come from
asking the same container for `bm25` and `dense` with `k=50`:

| Merged # | Passage | Rank in BM25 | Rank in embeddings | Fused score | Section |
|---|---|---|---|---|---|
| 1 | `2019-00791:0160` | 34 | 2 | 1/94 + 1/62 = 0.0268 | `III/D/1` Tributaries |
| 2 | `2019-00791:0010` | 27 | 6 | 1/87 + 1/66 = 0.0266 | `II/A` Executive summary (its definition of a tributary) |
| 3 | `2019-00791:0157` | 9 | 26 | 1/69 + 1/86 = 0.0261 | `III/D/1` Tributaries |

On this letter the two retrievers mostly disagree. Only 8 passages are in both top-50 lists, and of the six
passages in the `both` answer only `0160` is one of them. Fusion puts those 8 first, because any passage in
both lists (at least 1/110 + 1/110 = 0.0182) beats any passage in only one (at most 1/61 = 0.0164). The
other five passages from the `both` answer come back at merged ranks 9 to 13. So a reranker reading the
merged top 30 sees every passage `both` would have returned, plus the ones both retrievers agree on.

## Reproduce

```bash
docker compose up -d chromadb
docker compose run --rm rule-passages
docker compose up -d --build --no-deps api-service
curl -s localhost:8000/health
curl -s -X POST localhost:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"text": "The rule removes protection for ephemeral streams and intermittent tributaries", "k": 1}'
curl -s -X POST localhost:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"text": "The rule removes protection for ephemeral streams and intermittent tributaries", "k": 3, "method": "merged"}'
```
