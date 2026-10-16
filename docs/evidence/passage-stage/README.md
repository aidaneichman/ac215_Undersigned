# passage-stage evidence

Ticket U-26 (#43). One `docker compose up --build -d` on a fresh clone, default `.env` plus an API key, 15 Oct 2026, on `main` with the rule-passages markup fix (#67). The input is the 40-record lead and copper sample.

Refreshed 16 Oct from a rerun of the merged stage on the same letters (same `letters_sha256`). The table had come from a run before the last review changes to #68: § 141.81 now has one more link and § 141.86 one fewer. All totals are unchanged, and the counts below match the `links.parquet` the API reads (#79).

| File | What it shows |
| --- | --- |
| `run.log` | The stage's one line of output |
| `summary.json` | Counts and the checksum of the letters file read |

40 letters in, 1 skipped as an exact copy, 831 passages out. 155 passages cite a section, giving 204 links: 203 to 15 of the rule's 18 sections and 1 to `§141.42(d)`, an existing regulation outside the proposal.

Links per section:

| section_ref | links |
| --- | --- |
| `PART 141/§ 141.84` | 39 |
| `PART 141/§ 141.85` | 31 |
| `PART 141/§ 141.86` | 28 |
| `PART 141/§ 141.82` | 20 |
| `PART 141/§ 141.90` | 19 |
| `PART 141/§ 141.92` | 19 |
| `PART 141/§ 141.81` | 18 |
| `PART 141/§ 141.2` | 13 |
| `PART 141/§ 141.80` | 9 |
| `PART 141/§ 141.87` | 2 |
| `PART 141/§ 141.93` | 1 |
| `PART 142/§ 142.16` | 1 |
| `PART 142/§ 142.15` | 1 |
| `(not a section of the rule)` | 1 |
| `PART 142/§ 142.14` | 1 |
| `PART 141/§ 141.154` | 1 |

Eight links drawn at random were read against their passage. All eight cite the section they were linked to.

What this does not show: the links come from 5 of the 39 letters. Citations are concentrated in long organization letters, as the linking test found on seven dockets (3.7% of substantive comments carry a usable citation). Passages that cite nothing get no link here; that is the reader's job in MS3.

`text_masked` was checked on all 831 passages: none still contains a 141.x or 142.x number. That includes 10 passages whose PDF text garbles "Section" (the "ti" ligature is lost), which the citation reader cannot match and the masking catches by number.

