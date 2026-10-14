"""Find citations of rule sections in comment text.

The patterns are the ones measured in the linking test: on 80 sampled citations, 6 (7.5%) were not
about a section of the proposal. Three families:

  R1  a section sign or the word section:  § 141.84(b)(2), Sections 141.84 and 141.85
  R2  a CFR reference:                      40 CFR 141.85, 40 C.F.R. § 141.2
  R3  a bare number with a paragraph:       141.84(a), only when 141.84 is a section of the rule
"""

from __future__ import annotations

import re
from dataclasses import dataclass

NUM = r"\d{1,4}[a-z]?\.\d{1,5}[a-z]{0,2}(?:-\d{1,2})?(?![\d%])"
DESIG = r"(?:\s?\((?:[a-z]{1,4}|[A-Z]{1,2}|\d{1,3})\)){0,6}"
PREFIX = (
    r"(?:§\s?§|§|\bSections?\b|\bSecs?\.|\bsections?\b|\bsecs?\.|"
    r"\b\d{1,2}\s?C\.?\s?F\.?\s?R\.?\s?(?:[Pp]arts?\s|§\s?§?|[Ss]ections?\s|[Ss]ec\.\s)?)"
)
CONT = (
    r"(?:\s?(?:,|;|and|or|through|to|–|-|&|,\s?and|,\s?or)\s?(?:§\s?§?\s?)?" + NUM + DESIG + r")*"
)
CITE = re.compile(r"(?P<prefix>" + PREFIX + r")\s{0,3}(?P<body>" + NUM + DESIG + CONT + r")")
ONE = re.compile(r"(?P<num>" + NUM + r")(?P<des>" + DESIG + r")")
BARE = re.compile(
    r"(?<![\w.$§])(?P<num>" + NUM + r")(?P<des>(?:\s?\((?:[a-z]{1,4}|[A-Z]{1,2}|\d{1,3})\)){1,6})"
)


@dataclass(frozen=True)
class Citation:
    start: int
    number: str  # the section number, e.g. "141.84"
    raw: str  # the citation as written, e.g. "§ 141.84(b)(2)"
    family: str  # R1_section, R2_cfr or R3_bare


def find_citations(text: str, rule_sections: set[str] | None = None) -> list[Citation]:
    """Every section citation in the text, in order. R3 fires only for sections of the rule."""
    found: list[Citation] = []
    taken: list[tuple[int, int]] = []
    for m in CITE.finditer(text):
        family = "R2_cfr" if re.search(r"C\.?\s?F\.?\s?R", m.group("prefix")) else "R1_section"
        body_start = m.start("body")
        for k, one in enumerate(ONE.finditer(m.group("body"))):
            start = m.start() if k == 0 else body_start + one.start()
            raw = text[start : body_start + one.end()].strip()
            found.append(Citation(start, one.group("num"), raw, family))
        taken.append((m.start(), m.end()))
    if rule_sections:
        for m in BARE.finditer(text):
            inside = any(a <= m.start() < b for a, b in taken)
            if m.group("num") in rule_sections and not inside:
                found.append(Citation(m.start(), m.group("num"), m.group(0).strip(), "R3_bare"))
    return sorted(found, key=lambda c: c.start)
