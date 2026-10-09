"""Unit tests for data-collector. No network: the API client is stubbed."""

import json
import time

import pytest

import main as m

# --------------------------------------------------------------------------- shards

def test_shards_partition_the_index():
    ids = list(range(10))
    parts = [[i for i in ids if m.in_shard(i, (k, 3))] for k in (1, 2, 3)]
    assert parts == [[0, 3, 6, 9], [1, 4, 7], [2, 5, 8]]
    assert sorted(sum(parts, [])) == ids  # every id in exactly one shard


def test_parse_shard():
    assert m.parse_shard(None) == (1, 1)
    assert m.parse_shard("") == (1, 1)
    assert m.parse_shard("2/5") == (2, 5)
    with pytest.raises(ValueError):
        m.parse_shard("0/5")
    with pytest.raises(ValueError):
        m.parse_shard("6/5")


# --------------------------------------------------------------------------- #27: window dates

def test_filter_date_is_eastern_time_with_backoff():
    # April: EDT is UTC-4. 00:37 UTC -> 20:37 the previous evening, minus one minute.
    assert m._to_filter_date("2019-04-25T00:37:00Z") == "2019-04-24 20:36:00"
    # January: EST is UTC-5.
    assert m._to_filter_date("2019-01-15T05:00:00Z") == "2019-01-14 23:59:00"


def test_filter_date_backoff_is_configurable():
    assert m._to_filter_date("2019-04-25T00:37:00Z", back_off_seconds=0) == "2019-04-24 20:37:00"


def test_index_not_marked_complete_when_count_disagrees(tmp_path):
    ckpt = tmp_path / "ckpt.json"
    with pytest.raises(RuntimeError, match="10906.*11444"):
        m._finish_index("D", ckpt, 10906, 11444)
    assert json.loads(ckpt.read_text())["complete"] is False


def test_index_marked_complete_when_count_matches(tmp_path):
    ckpt = tmp_path / "ckpt.json"
    assert m._finish_index("D", ckpt, 11444, 11444) == 11444
    assert json.loads(ckpt.read_text())["complete"] is True


# --------------------------------------------------------------------------- MAX_RECORDS

def test_trim_index_keeps_first_n(tmp_path):
    p = tmp_path / "comments_index.jsonl"
    m.append_jsonl(p, [{"id": f"X-{i}"} for i in range(250)])
    assert m._trim_index(p, 50) == 50
    assert [r["id"] for r in m.read_jsonl(p)] == [f"X-{i}" for i in range(50)]


# --------------------------------------------------------------------------- keys

def test_key_pool_round_robins_and_skips_resting_keys():
    pool = m.KeyPool(["a", "b", "c"])
    assert [pool.next() for _ in range(4)] == ["a", "b", "c", "a"]
    pool.rest("b", seconds=3600)
    picks = [pool.next() for _ in range(6)]
    assert "b" not in picks
    assert set(picks) == {"a", "c"}


def test_key_pool_rests_key_when_remaining_is_low():
    pool = m.KeyPool(["a", "b"])
    pool.observe("a", remaining=3)  # below RATE_MARGIN
    assert pool.rested_until["a"] > time.time()
    assert pool.next() == "b"
    pool.observe("b", remaining=500)
    assert "b" not in pool.rested_until


# --------------------------------------------------------------------------- resumability

def test_fetch_details_skips_records_already_on_disk(tmp_path):
    out = tmp_path
    m.append_jsonl(out / "comments_index.jsonl", [{"id": "D-1"}, {"id": "D-2"}, {"id": "D-3"}])
    (out / "details").mkdir()
    (out / "details" / "D-2.json").write_text(json.dumps({"data": {"id": "D-2", "attributes": {}}}))

    fetched = []

    class FakeClient:
        calls = 0

        def get(self, path, params=None):
            fetched.append(path)
            return {"data": {"id": path.rsplit("/", 1)[-1], "attributes": {}}, "included": []}

    assert m.fetch_details(FakeClient(), "D", out) == 3
    assert fetched == ["/comments/D-1", "/comments/D-3"]
    assert sorted(p.name for p in (out / "details").glob("*.json")) == [
        "D-1.json",
        "D-2.json",
        "D-3.json",
    ]