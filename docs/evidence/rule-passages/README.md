# rule-passages evidence

Real runs of the `rule-passages` container against the live ChromaDB service from `docker-compose.yml`.
Rule text is the 2019 proposed rule (`84 FR 4154`, document 2019-00791) and two short notices from docket
`EPA-HQ-OW-2018-0149`, collected from the Federal Register API on 9 Oct 2026.

| File | What it shows |
| --- | --- |
| `run-cold.log` | `docker compose run --rm rule-passages` from nothing: download, 556 chunks, 556 embedded, 24 s |
| `run-rerun.log` | The same command again: 556 chunks, 0 embedded. Chunk ids and a hash of each chunk make reruns free |
| `section-outline.txt` | Every section of the proposed rule with its first page and chunk count. These are the section references a hand label can name |
| `query-letter-*.json` | Top 3 passages from BM25 and from the embedding search for three real comments, as the code returns them |

## One retrieval flow, query to retrieved context

**Query.** Comment `EPA-HQ-OW-2018-0149-0390`, anonymous public comment, 729 words, HTML removed:

> The EPA and the Department of the Armys proposed rule revises the definition of the WOTUS specifically focusing on defining tributaries and adjacent wetlands. By defining these two terms, the rule significantly excludes federal protection for ephemeral streams that pool or flow with precipitation. Waters that intermittently flow would only be protected if surface water ...

**Retrieved context** (`python src/main.py query --file letter_0390.txt --method both -k 3`):

| Retriever | # | Score | Citation | Section | Heading | Passage (start) |
|---|---|---|---|---|---|---|
| bm25 | 1 | 72.09 | 84 FR 4154, p. 4177 | `III/D/1` | D. Tributaries > 1. What are the agencies proposing? | The agencies also solicit comment on other implementation tools available to determine the flow regime of a river or stream and it... |
| bm25 | 2 | 65.44 | 84 FR 4154, p. 4173 | `III/D/1` | D. Tributaries > 1. What are the agencies proposing? | The agencies recognize that perennial or intermittent flow in certain mountain streams, for example, may result primarily from mel... |
| bm25 | 3 | 59.84 | 84 FR 4154, p. 4173 | `III/D/1` | D. Tributaries > 1. What are the agencies proposing? | The agencies propose to define the term “perennial” to mean surface water flowing continuously year-round during a typical year. T... |
| dense | 1 | 0.83 | 84 FR 4154, p. 4173 | `III/D/1` | D. Tributaries > 1. What are the agencies proposing? | Similarly, such a wetland would be considered “adjacent” and thus jurisdictional under this proposal given the wetland abuts (i.e.... |
| dense | 2 | 0.83 | 84 FR 4154, p. 4173 | `III/D/1` | D. Tributaries > 1. What are the agencies proposing? | The agencies intend to distinguish flow resulting from snow fall from sustained flow resulting from melting snowpack in these defi... |
| dense | 3 | 0.81 | 84 FR 4154, p. 4173 | `III/D/1` | D. Tributaries > 1. What are the agencies proposing? | In this proposed rule, the agencies would retain tributaries as a category of jurisdictional waters subject to CWA jurisdiction. T... |

Both retrievers put all three top passages in section III.D, Tributaries, which is the section the letter
argues about (ephemeral and intermittent streams).

## Where the two retrievers disagree

A letter about data and science, `EPA-HQ-OW-2018-0149-0171`, gets III/D from BM25 (the passages that discuss the
science behind the connectivity report) and III/I from the embedding search (the comparison with the 2015 rule).
A broad objection letter, `EPA-HQ-OW-2018-0149-0130`, scatters across both. Nobody has said which section is
right for these two, which is why the next step is 10 hand-mapped campaigns and `eval` rather than a
judgement from three examples.

## Reproduce

```bash
docker compose up -d chromadb
docker compose run --rm rule-passages                       # collect, chunk, embed, load
docker compose run --rm rule-passages python src/main.py outline
docker compose run --rm rule-passages python src/main.py query --file /app/data/samples/letter.txt
```
