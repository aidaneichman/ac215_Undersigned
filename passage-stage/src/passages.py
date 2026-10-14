"""Split a letter into passages.

The processor stores each letter as one line of text, so paragraph breaks are gone. A passage is a
run of whole sentences of about TARGET_WORDS, never more than MAX_WORDS. A single sentence longer than
MAX_WORDS is cut at MAX_WORDS. The last run is merged into the one before when it is shorter than
MIN_WORDS, so a letter does not end in a stray fragment.
"""

from __future__ import annotations

import re

TARGET_WORDS = 120
MAX_WORDS = 250
MIN_WORDS = 20

# A sentence ends at . ! or ? (and any closing quote or bracket) followed by space and something that
# starts a sentence. A bullet also starts a new sentence. Abbreviations such as "U.S." can split a
# sentence early; that is harmless, since sentences are only packed into passages.
BOUNDARY = re.compile(r"[.!?][\"”')\]]?\s+(?=[A-Z0-9\"“(•§\[])|\s+(?=•)")


def sentences(text: str) -> list[str]:
    out, start = [], 0
    for m in BOUNDARY.finditer(text):
        piece = text[start : m.end()].strip()
        if piece:
            out.append(piece)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        out.append(tail)
    return out


def split_passages(
    text: str,
    target: int = TARGET_WORDS,
    max_words: int = MAX_WORDS,
    min_words: int = MIN_WORDS,
) -> list[str]:
    """The letter as a list of passages, in order, covering all of its words."""
    runs: list[list[str]] = []
    current: list[str] = []
    for sentence in sentences(text or ""):
        words = sentence.split()
        while len(words) > max_words:  # one very long "sentence", often a table or a list
            if current:
                runs.append(current)
                current = []
            runs.append(words[:max_words])
            words = words[max_words:]
        if current and len(current) + len(words) > max_words:
            runs.append(current)
            current = []
        current = current + words
        if len(current) >= target:
            runs.append(current)
            current = []
    if current:
        if runs and len(current) < min_words and len(runs[-1]) + len(current) <= max_words:
            runs[-1] = runs[-1] + current
        else:
            runs.append(current)
    return [" ".join(run) for run in runs]
