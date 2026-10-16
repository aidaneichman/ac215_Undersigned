# Containment grouping on the lead and copper docket

Ticket U-05 (#5). 16 Oct 2026, laptop. Letters are the processor's output for the whole docket
EPA-HQ-OW-2022-0801, pulled with `dvc pull data/raw/EPA-HQ-OW-2022-0801.dvc`: 1,589 records, 1,553
letters. The other 36 are bundled campaign records that need a reviewed plan before the processor splits
them. No letter text is reproduced here.

## The 40-record sample, where the campaigns are known

`data-collector/samples/ms2_ids.txt` marks 10 letters from each of two campaigns, 10 organization letters
and 10 individual comments. Scored with B-cubed against those two campaigns:

| Grouper | Campaign letters grouped (of 20) | Groups for them | Other letters grouped | F1 |
|---|---|---|---|---|
| Exact match | 2 | 1 | 0 | 0.20 |
| MinHash, Jaccard 0.8 | 2 | 1 | 0 | 0.20 |
| MinHash, Jaccard 0.3 | 17 | 4 | 0 | 0.65 |
| Containment 0.4 or 0.5 | 20 | 2 (one per campaign) | 0 | 1.00 |
| Containment 0.6 | 15 | 2 | 0 | 0.76 |

Why: between letters of one campaign, the median Jaccard of five-word phrases is 0.24 and 0.37, and the
median containment is 0.53 and 0.70. Between letters that are not in the same campaign, containment is
at most 0.24.

## The full docket, where there is no answer key

| Grouper | Letters grouped | Groups | Largest groups | Time |
|---|---|---|---|---|
| Exact match | 26 | 13 | 2, 2, 2, 2 | 0.2 s |
| MinHash, Jaccard 0.8 | 53 | 22 | 6, 4, 3, 3 | 1.1 s |
| Containment 0.4 | 468 | 42 | 164, 78, 52, 18 | 2.6 s |
| Containment 0.5 | 441 | 43 | 160, 66, 49, 16, 15, 14 | 2.5 s |
| Containment 0.6 | 409 | 39 | 156, 55, 46, 16 | 2.6 s |

Checks:

- **Each large group is one campaign.** The six largest groups were read. Each has one shared template:
  praise for the rule's health benefits and the lower action level (160); a statistic on people served
  water above the lead limit (66); thanks for stronger rules and their effect on low-wealth communities
  (49); holding Chicago to the 10-year replacement standard (16); replacing every line in 10 years at no
  cost to households (15); removing the exceptions to the 10-year mandate (14).
- **Every grouped letter fits its template.** The lowest containment of any member with its group's core
  is 0.51. The code enforces this and the tests check it.
- **Stable across thresholds.** Against 0.5, B-cubed F1 is 0.97 at 0.4 and 0.94 at 0.6.
- **The candidate shortcut loses nothing.** A run that skips no boilerplate phrase and checks every
  candidate gives identical assignments for all 1,553 letters.
- **Close to an independent count.** An earlier analysis of this docket's public mirror, by shared phrase
  runs, found campaigns of 142, 62 and 52 letters. Containment finds 160, 66 and 49.

## What it fixed along the way

A first version assigned each letter to the first representative it fit. That split the largest
campaign into five groups (73, 52, 12, 11 and 7 letters), because several early letters became
representatives before the template was clear. A merge pass over group templates joined them. Merging
everything connected at once then chained a short campaign into an unrelated long one through
middle-sized groups, which the purity check caught (some members shared no phrase with their group's
template). Merging one pair at a time with the template recomputed, and dropping any member that no
longer fits, removed both problems. Both cases are tests.
