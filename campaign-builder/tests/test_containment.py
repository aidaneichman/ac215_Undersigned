"""Containment grouping: personalized form letters, and the cases that must stay apart."""

import pandas as pd
import pytest

from containment import core_of, group_containment
from exact_match import normalize
from minhash_grouping import group_minhash, shingles

TEMPLATE = " ".join(f"template{i}" for i in range(150))


def personal(i: int, words: int = 90) -> str:
    """What one sender adds: words no other letter uses."""
    return " ".join(f"sender{i}x{j}" for j in range(words))


def frame(texts: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"letter_id": [f"id{i:03}" for i in range(len(texts))], "text": texts})


def test_personalized_letters_group_where_jaccard_does_not():
    # Each letter is the template plus 90 words of its own: Jaccard between two is about 0.45,
    # containment about 0.6.
    letters = frame([TEMPLATE + " " + personal(i) for i in range(6)])
    grouped = group_containment(letters)
    assert grouped["campaign_id"].tolist() == ["id000"] * 6
    assert grouped["similarity"].iloc[1:].between(0.5, 1).all()
    assert group_minhash(letters, threshold=0.8)["campaign_id"].isna().all()


def test_unrelated_letters_stay_apart_even_with_shared_boilerplate():
    boiler = "thank you for the opportunity to comment on the proposed rule"
    letters = frame([boiler + " " + personal(i, 150) for i in range(5)])
    assert group_containment(letters)["campaign_id"].isna().all()


def test_a_long_letter_that_reprints_a_campaign_does_not_join_it():
    exhibit = " ".join([personal(99, 400), TEMPLATE, personal(98, 400)])  # 950 words around it
    letters = frame([TEMPLATE + " " + personal(0), TEMPLATE + " " + personal(1), exhibit])
    grouped = group_containment(letters)
    assert grouped["campaign_id"].tolist()[:2] == ["id000", "id000"]
    assert pd.isna(grouped["campaign_id"].iloc[2])


def test_two_campaigns_are_not_joined_through_a_letter_that_mixes_them():
    other = " ".join(f"second{i}" for i in range(150))
    half = " ".join(TEMPLATE.split()[:75] + other.split()[:75])
    letters = frame(
        [TEMPLATE, TEMPLATE + " " + personal(1), other, other + " " + personal(2), half]
    )
    grouped = group_containment(letters).set_index("letter_id")["campaign_id"]
    assert grouped["id000"] == grouped["id001"] == "id000"
    assert grouped["id002"] == grouped["id003"] == "id002"
    # The mixed letter joins at most one campaign and never merges the two.
    assert pd.isna(grouped["id004"]) or grouped["id004"] in ("id000", "id002")


def test_exact_copies_short_letters_and_empty_text():
    letters = frame([TEMPLATE, TEMPLATE.upper(), "See attached", "", None])
    grouped = group_containment(letters)
    assert grouped["campaign_id"].tolist()[:2] == ["id000", "id000"]
    assert grouped["campaign_id"].iloc[2:].isna().all()
    assert grouped["similarity"].tolist()[:2] == [1.0, 1.0]


def test_input_order_does_not_change_membership():
    texts = [TEMPLATE + " " + personal(i) for i in range(4)] + [personal(9, 150)]
    forward = group_containment(frame(texts)).sort_values("letter_id").reset_index(drop=True)
    shuffled = frame(texts).sample(frac=1, random_state=3)
    backward = group_containment(shuffled).sort_values("letter_id").reset_index(drop=True)
    pd.testing.assert_frame_equal(forward, backward)


def test_bad_input_is_rejected():
    with pytest.raises(ValueError):
        group_containment(frame([TEMPLATE]), threshold=0)
    with pytest.raises(ValueError):
        group_containment(pd.DataFrame({"letter_id": ["a", "a"], "text": [TEMPLATE, TEMPLATE]}))


def test_small_groups_do_not_chain_into_an_unrelated_campaign():
    # A short campaign, a long one, and middle-sized letters that each share part of both. Merging
    # everything connected at once joined the short campaign to the long one through the middle.
    short = " ".join(f"short{i}" for i in range(40))
    long_ = " ".join(f"long{i}" for i in range(200))
    middle = " ".join(short.split()[:30] + long_.split()[:40])
    texts = [short + " " + personal(i, 10) for i in range(3)]
    texts += [middle + " " + personal(10 + i, 10) for i in range(3)]
    texts += [long_ + " " + personal(20 + i, 60) for i in range(4)]
    grouped = group_containment(frame(texts))["campaign_id"]
    assert grouped.iloc[:3].nunique() == 1 and grouped.iloc[6:].nunique() == 1
    assert grouped.iloc[0] != grouped.iloc[6]


def test_every_grouped_letter_fits_its_campaign_template():
    texts = [TEMPLATE + " " + personal(i, 20 + 15 * i) for i in range(8)]
    texts += [" ".join(TEMPLATE.split()[:100]) + " " + personal(50 + i) for i in range(4)]
    letters = frame(texts)
    grouped = group_containment(letters)
    shingle_sets = {
        lid: shingles(normalize(text))
        for lid, text in zip(letters.letter_id, letters.text, strict=True)
    }
    for _, members in grouped.dropna(subset=["campaign_id"]).groupby("campaign_id"):
        core = core_of(list(members.letter_id), shingle_sets)
        assert (members.similarity >= 0.5).all()
        for lid in members.letter_id:
            small = min(len(shingle_sets[lid]), len(core))
            assert len(shingle_sets[lid] & core) / small >= 0.5
