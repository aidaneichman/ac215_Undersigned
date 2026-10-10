# api-service evidence

Real runs of the `api-service` container (`docker compose up -d --build --no-deps api-service`) against the
ChromaDB service from `docker-compose.yml`, after `docker compose run --rm rule-passages` had loaded the
538 passages of the 2019 proposed rule (`84 FR 4154`). Captured on 9 Oct 2026 on a laptop.

| File | What it shows |
| --- | --- |
| `startup.log` | The container's log: 538 passages loaded at startup, then the requests below with their status codes |
| `curl-session.txt` | `/health`, one `POST /retrieve`, a docket the index does not hold (no hits), and a bad request (422 naming both wrong fields) |
| `retrieve-letter-0390.json` | The full response for a real comment, `EPA-HQ-OW-2018-0149-0390` (anonymous), with `k=3` and both retrievers |
| `pytest.txt` | The 16 offline tests, by name |

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

## Reproduce

```bash
docker compose up -d chromadb
docker compose run --rm rule-passages
docker compose up -d --build --no-deps api-service
curl -s localhost:8000/health
curl -s -X POST localhost:8000/retrieve -H 'Content-Type: application/json' \
  -d '{"text": "The rule removes protection for ephemeral streams and intermittent tributaries", "k": 1}'
```
