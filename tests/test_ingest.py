from __future__ import annotations

import dataclasses
import json
from typing import Any
from urllib.parse import parse_qsl, urlsplit

import pytest
from conftest import EXAMPLES, TODAY

from regwatch.config import IngestSettings
from regwatch.ingest import IngestError, build_query_url, candidates_document, parse_candidates

SETTINGS = IngestSettings(
    agencies=("example-food-agency",),
    cfr_title=21,
    cfr_parts=(101, 172),
    terms=("allergen", "label"),
    jurisdiction="nl",
)


def response(*documents: dict[str, Any]) -> str:
    return json.dumps({"results": list(documents)})


def test_query_url_is_built_from_settings() -> None:
    url = build_query_url(SETTINGS, "2026-01-01")
    parts = urlsplit(url)
    assert (
        f"{parts.scheme}://{parts.netloc}{parts.path}"
        == "https://www.federalregister.gov/api/v1/documents.json"
    )
    pairs = parse_qsl(parts.query)
    assert ("conditions[agencies][]", "example-food-agency") in pairs
    assert ("conditions[publication_date][gte]", "2026-01-01") in pairs
    assert [v for k, v in pairs if k == "conditions[type][]"] == ["RULE", "PRORULE", "NOTICE"]
    assert ("per_page", "100") in pairs
    assert "cfr_references" in [v for k, v in pairs if k == "fields[]"]


def test_query_url_rejects_a_bad_date() -> None:
    with pytest.raises(IngestError, match="not an ISO date"):
        build_query_url(SETTINGS, "last week; rm -rf")


def test_example_response_yields_two_relevant_candidates_newest_first() -> None:
    text = (EXAMPLES / "ingest-response.json").read_text(encoding="utf-8")
    candidates = parse_candidates(text, SETTINGS, TODAY)
    assert [c["document_number"] for c in candidates] == ["2026-20001", "2026-20002"]
    first = candidates[0]
    assert first["headline"] == "Proposed Rule: Allergen labeling update for packaged snacks"
    assert first["citations"] == [
        {"citation": "21 CFR 101", "url": "https://www.ecfr.gov/current/title-21/part-101"}
    ]
    assert first["agency"] == "Example Food Agency"
    assert first["jurisdiction"] == "nl"
    assert first["needs_review"] is True
    assert first["confidence"] == "unconfirmed"
    assert first["obligation_id"] is None
    assert first["detected"] == "2026-10-19"
    assert first["source_url"] == "https://www.example.gov/documents/2026-20001"


def test_cfr_part_relevance_requires_the_configured_title() -> None:
    doc = {"title": "Plain", "cfr_references": [{"title": 40, "part": 101}]}
    assert parse_candidates(response(doc), SETTINGS, TODAY) == []
    doc["cfr_references"] = [{"title": 21, "part": 101}]
    assert len(parse_candidates(response(doc), SETTINGS, TODAY)) == 1
    any_title = dataclasses.replace(SETTINGS, cfr_title=None)
    doc["cfr_references"] = [{"title": 40, "part": 101}]
    assert len(parse_candidates(response(doc), any_title, TODAY)) == 1


def test_term_relevance_uses_title_and_abstract_case_insensitively() -> None:
    assert len(parse_candidates(response({"title": "New LABEL rule"}), SETTINGS, TODAY)) == 1
    assert (
        len(
            parse_candidates(
                response({"title": "x", "abstract": "an Allergen note"}), SETTINGS, TODAY
            )
        )
        == 1
    )
    assert parse_candidates(response({"title": "Fees"}), SETTINGS, TODAY) == []


def test_no_filters_means_everything_is_a_candidate() -> None:
    open_settings = IngestSettings()
    assert (
        len(parse_candidates(response({"title": "a"}, {"title": "b"}), open_settings, TODAY)) == 2
    )


def test_untrusted_fields_are_checked_and_truncated() -> None:
    hostile = {
        "title": "label " + "x" * 500,
        "abstract": "y" * 1000,
        "publication_date": "not-a-date",
        "html_url": "javascript:alert(1)",
        "document_number": ["list"],
        "type": {"nested": "object"},
        "agencies": "not a list",
        "cfr_references": [
            {"title": "21", "part": "101"},
            {"title": True, "part": 1},
            {"title": 21, "part": "1; DROP TABLE"},
            "string",
            {"title": 21, "part": 101},
        ],
    }
    [candidate] = parse_candidates(response(hostile), SETTINGS, TODAY)
    assert len(candidate["headline"]) <= len("Document: ") + 200
    assert len(candidate["what_happened"]) <= 320
    assert candidate["date"] == ""
    assert candidate["source_url"] == ""
    assert candidate["document_number"] == ""
    assert candidate["type"] == "Document"
    assert candidate["agency"] == ""
    assert [c["citation"] for c in candidate["citations"]] == ["21 CFR 101"]


def test_non_object_documents_and_bad_cfr_lists_are_skipped() -> None:
    text = json.dumps(
        {"results": ["string", 4, None, {"title": "label ok", "cfr_references": "nope"}]}
    )
    assert [c["headline"] for c in parse_candidates(text, SETTINGS, TODAY)] == [
        "Document: label ok"
    ]


def test_non_https_links_are_dropped_and_https_kept() -> None:
    http_doc = {"title": "label", "html_url": "http://example.org/a"}
    https_doc = {"title": "label", "html_url": "  https://example.org/a "}
    assert parse_candidates(response(http_doc), SETTINGS, TODAY)[0]["source_url"] == ""
    assert (
        parse_candidates(response(https_doc), SETTINGS, TODAY)[0]["source_url"]
        == "https://example.org/a"
    )


@pytest.mark.parametrize(
    "text", ["not json", "[]", '{"count": 1}', '{"results": "x"}', "[" * 100000]
)
def test_malformed_responses_raise_ingest_error(text: str) -> None:
    with pytest.raises(IngestError):
        parse_candidates(text, SETTINGS, TODAY)


def test_document_cap() -> None:
    docs = [{"title": f"label {i}", "publication_date": "2026-01-01"} for i in range(1200)]
    assert len(parse_candidates(response(*docs), SETTINGS, TODAY)) == 1000


def test_candidates_document_wraps_with_provenance() -> None:
    document = candidates_document([{"a": 1}], TODAY, "file")
    assert document["origin"] == "file"
    assert document["generated"] == "2026-10-19"
    assert document["candidates"] == [{"a": 1}]
    assert "never edits the" in document["note"]


def test_non_object_cfr_references_are_ignored_during_relevance() -> None:
    document = {"title": "plain", "cfr_references": ["text", {"title": 21, "part": 101}]}
    assert len(parse_candidates(response(document), SETTINGS, TODAY)) == 1
    assert (
        parse_candidates(response({"title": "plain", "cfr_references": ["text"]}), SETTINGS, TODAY)
        == []
    )
