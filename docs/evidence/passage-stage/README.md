# passage-stage evidence

Ticket U-26 (#43). One `docker compose up --build -d` on a fresh clone, default `.env` plus an API key, 15 Oct 2026, on `main` with the rule-passages markup fix (#67). The input is the 40-record lead and copper sample.

Updated 16 Oct from a rerun on the same letters (same `letters_sha256`), with two changes since the first run:

- The last review changes to #68: § 141.81 has one more link and § 141.86 one fewer than the first table said.
- Lost ligatures repaired (`glyphs.py`). One letter, EPA-HQ-OW-2022-0801-0972, was saved from Word in Calibri, whose "ti", "ft", "tti" and "tf" glyphs pypdf reads as U+FFFD ("Associa�on", "Sec�on 141.84"). The stage restores 1,336 words in it, picking the pair that makes a word the docket's letters use. Against an exact decoding of that PDF (PyMuPDF, which keeps the four glyphs apart), 1,334 of the 1,336 are right; the misses are "submitting" and "straightforward", which no other letter spells out. Ten of its citations now read as written ("Section 141.84(b)(5)"); nine had already been linked from the bare number, and one is new, so § 141.90 goes from 19 to 20 links and the total from 204 to 205. No passage still contains U+FFFD or a ligature character such as "ﬁ".

The API evidence in `../api-service/` was recorded before the repair: it reads 204 links and shows 19 citing passages for § 141.90.

| File | What it shows |
| --- | --- |
| `run.log` | The stage's one line of output |
| `summary.json` | Counts and the checksum of the letters file read |

40 letters in, 1 skipped as an exact copy, 831 passages out. 155 passages cite a section, giving 205 links: 204 to 15 of the rule's 18 sections and 1 to `§141.42(d)`, an existing regulation outside the proposal.

Links per section:

| section_ref | links |
| --- | --- |
| `PART 141/§ 141.84` | 39 |
| `PART 141/§ 141.85` | 31 |
| `PART 141/§ 141.86` | 28 |
| `PART 141/§ 141.82` | 20 |
| `PART 141/§ 141.90` | 20 |
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

`text_masked` was checked on all 831 passages of the repaired run: none still contains a 141.x or 142.x number. Masking also hides any bare mention of a rule section number, which still matters for PDF text that garbles the word before a number in some other way.

