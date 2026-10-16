"""Repair letter pairs that PDF text extraction lost.

Word documents set in Calibri join some letter pairs into one glyph: "ti", "ft", "tti" and "tf".
Saved as PDF, those glyphs map to the wrong characters, and pypdf (data-processor) writes U+FFFD
for all of them: "Associa�on", "a�er". In the 40-record lead and copper sample one letter
has 1,336 such words.

The letters file keeps the text as extracted. This stage repairs it before splitting, so the passages,
the citations read from them ("Sec�on 141.84" is a citation) and the text people read are whole.
For each damaged word it tries each pair and keeps the one that makes a word the docket's letters
use elsewhere, "ti" when none does, since it is by far the most common. Checked against an exact
decoding of that letter, 1,334 of the 1,336 words come out right; the two misses are words no other
letter spells out ("submitting", "straightforward").

Typographic ligatures that did decode ("ﬁ" for fi, "ﬀ" for ff) are spelled out too, so a
search for "definition" finds "deﬁnition".
"""

from __future__ import annotations

import itertools
import re
from collections import Counter
from collections.abc import Iterable

LOST = "�"
# Most common first: the fallback when no candidate is a known word.
PAIRS = ("ti", "ft", "tti", "tf")
LIGATURES = str.maketrans(
    {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
     "ﬅ": "st", "ﬆ": "st"}
)  # fmt: skip
# A run of letters and lost glyphs. A lost glyph with no letter beside it is left alone: it was
# a bullet or a symbol, not part of a word.
WORD = re.compile(rf"[A-Za-z{LOST}]*[A-Za-z][A-Za-z{LOST}]*|[A-Za-z{LOST}]*{LOST}[A-Za-z]+")
# More lost glyphs than this in one word is not ligature damage; leave it.
MAX_LOST = 3


def spell_out_ligatures(text: str) -> str:
    return text.translate(LIGATURES)


def vocabulary(texts: Iterable[str]) -> Counter[str]:
    """How often each undamaged word appears, lowercased."""
    words: Counter[str] = Counter()
    for text in texts:
        for word in re.findall(rf"[A-Za-z{LOST}]+", spell_out_ligatures(text)):
            if LOST not in word:
                words[word.lower()] += 1
    return words


def repair_word(word: str, known: Counter[str]) -> str:
    holes = word.count(LOST)
    if not holes or holes > MAX_LOST:
        return word
    pieces = word.split(LOST)

    def fill(choice: tuple[str, ...]) -> str:
        return pieces[0] + "".join(pair + piece for pair, piece in zip(choice, pieces[1:]))

    choices = list(itertools.product(PAIRS, repeat=holes))
    # The best-known word wins; ties go to the most common pairs, which come first in PAIRS.
    best = max(choices, key=lambda c: (known[fill(c).lower()], [-PAIRS.index(p) for p in c]))
    return fill(best)


def repair(text: str, known: Counter[str]) -> tuple[str, int]:
    """The text with ligatures spelled out and lost pairs restored, and how many words changed."""
    text = spell_out_ligatures(text)
    if LOST not in text:
        return text, 0
    changed = 0

    def fix(match: re.Match) -> str:
        nonlocal changed
        word = match.group(0)
        fixed = repair_word(word, known)
        changed += fixed != word
        return fixed

    return WORD.sub(fix, text), changed
