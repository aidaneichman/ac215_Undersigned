# MS2 task list

Working draft. Owners may change.

Due Tue 20 Oct, 10:00 PM ET. Commit hash on Canvas from the `milestone2` branch. 15 minute talk to Alyssa, and anyone can be asked about any part.

## What MS2 asks for, and where we are

| Requirement | State today | Gap |
|---|---|---|
| Each component in a container, one command to run | Seven services in `docker-compose.yml`. Chain runs on a 50 record sample. | Add the new stage. Clean-clone test. |
| Data versioning | DVC on GCS | Add the lead and copper docket |
| RAG: collection, chunking, vector DB | `rule-passages` with ChromaDB, 79 tests | Point it at the new docket. Index paragraphs as well as sections. |
| One retrieval flow, query to context, with input and output | Works on the water rule | Redo on a real organization letter, with logs and one failure |
| App skeleton with UI calling the back end | `api-service` and `frontend` exist. PR #35 adds `/retrieve`. | New page for the new scope |
| Setup doc and screenshot of running instances | Not done | Do it |

## What changes in the tickets

| Ticket | Was | Now |
|---|---|---|
| U-01, U-03, U-04, U-05, U-08, U-10, U-11, U-20, U-21, U-22, U-23, U-24 | | Keep as written |
| U-09 | Exact-match baseline and B-cubed on the sample | Keep. This is the evidence for the duplicate-removal step. |
| U-12 | Processor at full scale, reproduce 7% and 78% | Keep, lower priority. Do after the new stage runs. |
| U-13 | MinHash, bge with HDBSCAN, BM25, scored by B-cubed | Drop the clustering comparison. Replaced by U-28. |
| U-14 | Two chunk sizes on 10 hand-mapped campaigns | Same test on citation-labeled passages from the lead and copper docket |
| U-15 | React page from the MS1 mock | Rule page: section list with counts, click a section to see who argued and what they asked. Calls the API. |
| U-16 | Hand labels, 60 items each | Replaced by U-30 |
| U-17 | MinHash on LLM-reworded letters | Move to MS4 |
| U-18 | Trace one CREDO letter end to end | Trace one organization passage from query to ranked sections, with logs and one failure |

## New tickets

| Ticket | What | Owner | Starts from |
|---|---|---|---|
| U-25 | Pull docket EPA-HQ-OW-2022-0801 (comments and extracted attachment text) from the public mirror into `data/raw`, tracked in DVC | Livia | Prototype reader exists |
| U-26 | New stage: split substantive comments into passages and read section citations. Output is one file of passages and one of passage-to-section links. Own container, in the compose chain after `campaign-builder`. | Aidan | Prototype exists |
| U-27 | `rule-passages`: add the lead and copper proposal (88 FR 84878), index by section and paragraph | Aidan | With U-14 |
| U-28 | Baseline table on held-out passages: BM25, embeddings, both, and a small model on a sample. Cost per 1,000 passages. | Aadil | Weekend numbers to reproduce in the repo |
| U-29 | API: `GET /rules/{docket}/sections` (arguments per section by group) next to `POST /retrieve` | Rishi | PR #35 |
| U-30 | Label set: 180 passages labeled by two models with adjudication (done), checked by one of us on a blind 30-passage sample. Report the agreement. | One of us, Aadil runs the scoring | Model labels and the 30-passage sheet are ready |
| U-31 | Short note in the README on what changed since MS1 and why | Aidan | |

## By person

| Person | This week |
|---|---|
| Aidan | Review #35 Monday. U-26, U-27, U-14, U-21, U-31. With Livia on U-10. |
| Livia | Merge #33 and #34 once reviewed. U-25. U-20. U-24. With Aidan on U-10. |
| Andrew | Review #33 and #34. U-04, U-05 into the chain as the duplicate-removal step. U-18. U-23. |
| Rishi | Land #35. U-29. U-15. |
| Aadil | Review #33. U-09. U-28. U-30 scoring. Ask the API-232 instructors about a section activity. |
| Everyone | U-22: slides, then each person explains someone else's part |

## Dates

| By | What should be true |
|---|---|
| Mon 12 | #33, #34, #35 reviewed. 30-passage check sheet out to one reader. |
| Wed 14 | Lead and copper docket in DVC. New stage runs on a sample. Human check back and scored. |
| Fri 16, 3:30 PM | Check-in with Alyssa. Chain runs end to end on the sample with one command. Baseline table has numbers. |
| Sun 18 | Page calls the API. README and setup doc drafted. Retrieval example written up. |
| Mon 19 | Clean-clone test by someone who did not write the compose file. Slides. Drill. |
| Tue 20, 10 PM | Hash on Canvas |

## Not in MS2

Reading every open rule. The reranker and any training. The forecast. Exhibit detection. The map view. These are MS3 and later.
