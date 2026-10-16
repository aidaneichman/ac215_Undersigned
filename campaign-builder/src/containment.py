"""Group personalized form letters by how much of one letter's wording the other contains.

A campaign letter is a template plus whatever the sender adds. Two letters from one campaign share
most of the template, but each sender's own words enlarge the union of their phrases, so Jaccard
similarity stays low: a median of 0.24 and 0.37 between letters of the two campaigns in the MS2
sample. Containment, the shared phrases over the smaller letter's phrases, ignores what a sender
added: a median of 0.53 and 0.70 in the same campaigns, and at most 0.24 between unrelated letters.

Letters are taken in letter_id order, so a run does not depend on input order. A letter joins the
representative it contains the most of, if that containment is at least `threshold` and neither
letter is more than `max_length_ratio` times as long as the other. Otherwise it becomes a
representative itself. Comparing only with representatives keeps a chain of weak matches from
joining two campaigns. The length guard keeps a long letter that reprints a campaign's text, such as
an exhibit volume, out of that campaign.

A first pass like this splits a large campaign: before a clear template emerges, several early
letters become representatives, and later letters scatter among them. On the full lead and copper
docket one campaign of 155 letters came out as five groups. So a second pass works on templates
instead of letters. Each group's core is the set of phrases at least half its members share, which
is the template without anyone's personal additions. Groups whose cores fit each other are merged
one pair at a time, the closest pair first, and the merged core is recomputed before the next merge.
Ungrouped letters that fit a core then join it, and the pass repeats until nothing changes. Finally
any member that no longer fits its group's core is dropped. So every grouped letter contains at
least `threshold` of its campaign's template, a property the tests check.

Candidates come from an index of the representatives' phrases. A phrase found in more than
`common_limit` representatives is boilerplate and is not used to find candidates, which keeps large
dockets fast. Containment itself is always computed on the full sets, so the result is exact.
"""

from __future__ import annotations

from collections import Counter

import pandas as pd

from exact_match import MIN_WORDS, normalize
from minhash_grouping import shingles

THRESHOLD = 0.5
SHINGLE_SIZE = 5
MAX_LENGTH_RATIO = 4.0
COMMON_LIMIT = 200
CANDIDATES_CHECKED = 25  # representatives sharing the most phrases, checked exactly


def containment(a: set[str], b: set[str]) -> float:
    """Shared phrases over the smaller set's phrases."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def group_containment(
    letters: pd.DataFrame,
    threshold: float = THRESHOLD,
    shingle_size: int = SHINGLE_SIZE,
    min_words: int = MIN_WORDS,
    max_length_ratio: float = MAX_LENGTH_RATIO,
    common_limit: int = COMMON_LIMIT,
) -> pd.DataFrame:
    """One row per letter, in input order: letter_id, campaign_id, method, similarity.

    campaign_id is the representative's letter_id, or null for a letter that matched nothing.
    similarity is the containment between a letter and its representative, null when ungrouped.
    Letters under `min_words` normalized words stay ungrouped. Call once per docket.
    """
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")
    if shingle_size < 1 or min_words < 1 or max_length_ratio < 1 or common_limit < 1:
        raise ValueError("shingle_size, min_words, common_limit >= 1 and max_length_ratio >= 1")
    ids = letters["letter_id"]
    if ids.isna().any() or not ids.map(lambda x: isinstance(x, str)).all():
        raise ValueError("letter_id must contain non-null strings")
    if ids.duplicated().any():
        raise ValueError("letter_id must be unique")
    if "docket_id" in letters and letters["docket_id"].nunique(dropna=False) > 1:
        raise ValueError("group one docket at a time")

    phrases: dict[str, set[str]] = {}  # representative -> its phrases
    index: dict[str, list[str]] = {}  # phrase -> representatives that have it
    by_text: dict[str, str] = {}  # normalized text -> representative, for exact copies
    members: dict[str, list[str]] = {}
    assigned: dict[str, tuple[str, float]] = {}
    ordered = letters.sort_values("letter_id")[["letter_id", "text"]]
    for letter_id, text in ordered.itertuples(index=False, name=None):
        normalized = normalize(text if isinstance(text, str) else "")
        if len(normalized.split()) < min_words:
            continue
        if normalized in by_text:  # an exact copy: no need to compare
            representative = by_text[normalized]
            members[representative].append(letter_id)
            assigned[letter_id] = (representative, 1.0)
            continue
        tokens = shingles(normalized, shingle_size)
        shared: Counter[str] = Counter()
        for phrase in tokens:
            holders = index.get(phrase)
            if holders and len(holders) <= common_limit:
                shared.update(holders)
        best_id, best_score = None, 0.0
        # Highest shared count first, then letter_id, so ties always resolve the same way.
        candidates = sorted(shared.items(), key=lambda kv: (-kv[1], kv[0]))[:CANDIDATES_CHECKED]
        for candidate, _ in candidates:
            other = phrases[candidate]
            small, large = sorted((len(tokens), len(other)))
            if large > max_length_ratio * small:
                continue
            score = containment(tokens, other)
            if score >= threshold and score > best_score:
                best_id, best_score = candidate, score
        if best_id is None:
            best_id, best_score = letter_id, 1.0
            phrases[letter_id] = tokens
            by_text[normalized] = letter_id
            members[letter_id] = []
            for phrase in tokens:
                index.setdefault(phrase, []).append(letter_id)
        members[best_id].append(letter_id)
        assigned[letter_id] = (best_id, best_score)

    texts = {
        letter_id: shingles(normalize(text if isinstance(text, str) else ""), shingle_size)
        for letter_id, text in ordered.itertuples(index=False, name=None)
    }
    eligible = {
        letter_id
        for letter_id, text in ordered.itertuples(index=False, name=None)
        if len(normalize(text if isinstance(text, str) else "").split()) >= min_words
    }
    groups = [sorted(m) for m in members.values() if len(m) > 1]
    groups, cores = merge_by_template(groups, texts, eligible, threshold, max_length_ratio)

    campaign_of: dict[str, tuple[str, float]] = {}
    for group in groups:
        name, core = group[0], cores[group[0]]  # named after its earliest letter
        for letter_id in group:
            campaign_of[letter_id] = (name, containment(texts[letter_id], core))
    rows = []
    for letter_id in ids:
        name, score = campaign_of.get(letter_id, (None, None))
        rows.append((letter_id, name, "containment", None if score is None else round(score, 4)))
    return pd.DataFrame(rows, columns=["letter_id", "campaign_id", "method", "similarity"])


def core_of(group: list[str], texts: dict[str, set[str]]) -> set[str]:
    """The phrases at least half of a group's letters share: its template."""
    counts = Counter(phrase for letter_id in group for phrase in texts[letter_id])
    return {phrase for phrase, n in counts.items() if 2 * n >= len(group)}


def fits(a: set[str], b: set[str], threshold: float, max_length_ratio: float) -> bool:
    small, large = sorted((len(a), len(b)))
    return small > 0 and large <= max_length_ratio * small and containment(a, b) >= threshold


def merge_by_template(
    groups: list[list[str]],
    texts: dict[str, set[str]],
    eligible: set[str],
    threshold: float,
    max_length_ratio: float,
    rounds: int = 5,
) -> tuple[list[list[str]], dict[str, set[str]]]:
    """Merge groups that share a template, then add ungrouped letters that contain one.

    Groups merge one pair at a time, the closest pair first, and the merged group's core is
    recomputed before the next merge, so a merge must fit the template as it now stands. A union of
    everything connected at once let small groups chain into an unrelated campaign through groups in
    between. Afterwards any member that no longer fits its group's core is dropped, so every grouped
    letter fits its campaign's template. Returns the groups, each sorted, and each group's core
    keyed by its earliest letter_id.
    """
    groups = [sorted(g) for g in groups]
    for _ in range(rounds):
        before = sorted(map(tuple, groups))
        groups = agglomerate(groups, texts, threshold, max_length_ratio)
        groups = prune(groups, texts, threshold, max_length_ratio)
        cores = [core_of(g, texts) for g in groups]
        grouped = {letter_id for g in groups for letter_id in g}
        for letter_id in sorted(eligible - grouped):
            best, best_score = None, 0.0
            for k, core in enumerate(cores):
                if fits(texts[letter_id], core, threshold, max_length_ratio):
                    score = containment(texts[letter_id], core)
                    if score > best_score:
                        best, best_score = k, score
            if best is not None:
                groups[best] = sorted(groups[best] + [letter_id])
        groups = prune(groups, texts, threshold, max_length_ratio)
        groups = sorted(groups, key=lambda g: g[0])
        if sorted(map(tuple, groups)) == before:
            break
    return groups, {g[0]: core_of(g, texts) for g in groups}


def agglomerate(
    groups: list[list[str]], texts: dict[str, set[str]], threshold: float, max_length_ratio: float
) -> list[list[str]]:
    """Merge the closest pair of groups whose cores fit each other, until no pair does."""
    groups = [list(g) for g in groups]
    cores = [core_of(g, texts) for g in groups]
    while True:
        best, best_key = None, None
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                if fits(cores[i], cores[j], threshold, max_length_ratio):
                    key = (containment(cores[i], cores[j]), [-ord(c) for c in groups[i][0]])
                    if best_key is None or key > best_key:
                        best, best_key = (i, j), key
        if best is None:
            return groups
        i, j = best
        groups[i] = sorted(groups[i] + groups[j])
        cores[i] = core_of(groups[i], texts)
        del groups[j], cores[j]


def prune(
    groups: list[list[str]], texts: dict[str, set[str]], threshold: float, max_length_ratio: float
) -> list[list[str]]:
    """Drop members that do not fit their group's core; a group left with one letter dissolves."""
    out = []
    for group in groups:
        while True:
            core = core_of(group, texts)
            kept = [m for m in group if fits(texts[m], core, threshold, max_length_ratio)]
            if len(kept) == len(group):
                break
            group = kept
            if len(group) < 2:
                break
        if len(group) >= 2:
            out.append(sorted(group))
    return out
