"""The citation reader: the three families, lists, and what it must not match."""

from citations import find_citations


def numbers(text, rule=None):
    return [(c.number, c.family) for c in find_citations(text, rule)]


def test_section_sign_and_word():
    assert numbers("We oppose § 141.84(b)(2) as written.") == [("141.84", "R1_section")]
    assert numbers("Section 141.85 should allow mail.") == [("141.85", "R1_section")]
    assert numbers("see sec. 141.2") == [("141.2", "R1_section")]


def test_cfr_reference():
    assert numbers("Under 40 CFR 141.85(a), systems must ...") == [("141.85", "R2_cfr")]
    assert numbers("40 C.F.R. § 141.2 defines it") == [("141.2", "R2_cfr")]


def test_a_list_gives_one_citation_per_section():
    found = find_citations("Sections 141.84 and 141.85, and § 141.86(d)")
    assert [c.number for c in found] == ["141.84", "141.85", "141.86"]


def test_bare_number_only_counts_for_a_section_of_the_rule():
    text = "The requirement in 141.84(a) and the one in 330.5(b)."
    assert numbers(text) == []  # no rule given, no bare matches
    assert numbers(text, {"141.84"}) == [("141.84", "R3_bare")]


def test_raw_text_is_the_citation_as_written():
    (cite,) = find_citations("We ask EPA to revise § 141.84(b)(2) now.")
    assert cite.raw == "§ 141.84(b)(2)"


def test_numbers_that_are_not_citations():
    text = "It costs $1.5 million, a 15.5% increase, on 1.2 million lines, version 2.0 of the plan."
    assert numbers(text, {"141.84", "1.5", "15.5", "1.2", "2.0"}) == []
