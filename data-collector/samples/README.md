# Sample record lists

`ms2_ids.txt` is the fixed sample for the MS2 one-command run: 40 records from docket
EPA-HQ-OW-2022-0801 (Lead and Copper Rule Improvements), chosen on purpose so every stage has
something to do. `MAX_RECORDS=50` takes the first 50 index rows, and none of those is a campaign
record, so grouping had nothing to group.

| Group | Records | Why |
|---|---|---|
| campaign_a | 10 letters from a 142-letter campaign | grouping |
| campaign_b | 10 letters from a 62-letter campaign | grouping, a second template |
| organizations | 10 letters whose attachments cite rule sections (316 citations) | linking |
| individuals | 10 unrelated short comments | should stay ungrouped |

On this sample exact match groups almost nothing (the campaign letters are personalized) and
shared 5-word runs find both campaigns.

To run the chain on it, set two lines in `.env` and start as usual:

```
DOCKET_IDS=EPA-HQ-OW-2022-0801
RECORD_IDS_FILE=/app/samples/ms2_ids.txt
```

The collector then skips its index stage and fetches exactly these 40 records and their
attachments, about 60 API calls. `MAX_RECORDS` is ignored while the list is set.

The same records are in the public mirror (`mirrulations.s3.amazonaws.com`). The mirror also
holds files named `<id>(1).json` that repeat a record word for word (1,351 of 2,940 files in this
docket, which has 1,589 real records), so a mirror reader has to skip them.

Only ids are stored here. Comment text stays out of git.
