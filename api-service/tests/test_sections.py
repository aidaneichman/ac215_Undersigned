"""GET /rules/{docket_id}/sections: the rule's sections, in reading order, for the rule page."""

import pytest
from fastapi.testclient import TestClient

from conftest import DEV_DOCKET, make_chunk
from main import PassageIndex, create_app

TRANSFER_DOCKET = "EPA-HQ-OAR-2017-0355"
# The fields the rule page reads; this pins the contract from the API's side.
SECTION_FIELDS = {
    "document_number", "citation", "section_ref", "heading", "title", "depth", "page",
    "rule_passages", "citing_passages",
}  # fmt: skip
FLOW = "III. Proposed Definition > D. Tributaries"
WETLANDS = "III. Proposed Definition > G. Adjacent Wetlands"


@pytest.fixture
def client(store):
    # Upserted out of order on purpose: the endpoint must sort by position in the document.
    store.upsert([
        make_chunk(3, "Wetland adjacency.", ref="III/G", heading=WETLANDS),
        make_chunk(1, "Tributary flow.", ref="III/D", heading=FLOW),
        make_chunk(2, "Ephemeral streams.", ref="III/D", heading=FLOW),
        make_chunk(0, "Send comments by mail.", ref="SUMMARY", heading="Summary", procedural=True),
        make_chunk(0, "Power plants.", docket=TRANSFER_DOCKET, doc="2017-22349", ref="II/A",
                   heading="II. Background > A. Power"),
    ])  # fmt: skip
    with TestClient(create_app(lambda: PassageIndex(store))) as client:
        yield client


def sections(client, docket_id=DEV_DOCKET):
    response = client.get(f"/rules/{docket_id}/sections")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["docket_id"] == docket_id
    return body["sections"]


def test_sections_come_in_reading_order_with_their_passage_counts(client):
    found = sections(client)
    assert [(s["section_ref"], s["rule_passages"]) for s in found] == [("III/D", 2), ("III/G", 1)]


def test_each_section_carries_what_the_rule_page_shows(client):
    flow = sections(client)[0]
    assert set(flow) == SECTION_FIELDS
    assert flow["heading"] == FLOW
    assert (flow["title"], flow["depth"]) == ("D. Tributaries", 2)
    # A section's page is where its first passage starts.
    assert flow["page"] == 4171
    assert (flow["document_number"], flow["citation"]) == ("2019-00791", "84 FR 4154")


def test_procedural_sections_are_left_out(client):
    assert "SUMMARY" not in {s["section_ref"] for s in sections(client)}


def test_each_docket_lists_only_its_own_rule(client):
    assert [s["section_ref"] for s in sections(client, TRANSFER_DOCKET)] == ["II/A"]


def test_citing_passages_is_unknown_until_the_passage_stage_exists(client):
    assert {s["citing_passages"] for s in sections(client)} == {None}


def test_an_unknown_docket_is_a_404_that_names_the_indexed_dockets(client):
    response = client.get("/rules/NO-SUCH-DOCKET/sections")
    assert response.status_code == 404
    assert DEV_DOCKET in response.json()["detail"]
