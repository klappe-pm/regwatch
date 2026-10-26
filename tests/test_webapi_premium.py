"""The web interface's newsletter, document, design and language model routes.

They call the same functions as `regwatch newsletter`, `regwatch document` and
`regwatch llm`, and answer 403 while premium is off.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from conftest import FakeSystem
from test_design import SAFE_SVG
from test_newsletter import FakePoster, make_png
from test_webapi_workspace import get, make, post

from regwatch.config import load_config
from regwatch.webapi import Api, ApiError, Download

KEY = "fake" + "-web-" + "key-2280"
PASSAGES = [{"section": "opening", "text": "Four sources moved.", "cites": ["change:nl-notices"]}]


def refused(
    api: Api, method: str, path: str, body: dict[str, Any] | None = None, **query: str
) -> ApiError:
    with pytest.raises(ApiError) as caught:
        api.handle(method, path, query, body or {})
    return caught.value


ROUTES = [
    ("GET", "/api/newsletter", None),
    ("POST", "/api/newsletter/generate", {"since": 7}),
    ("GET", "/api/newsletter/export", None),
    ("GET", "/api/document", None),
    ("POST", "/api/document/generate", {"kind": "briefing"}),
    ("GET", "/api/document/export", None),
    ("POST", "/api/settings/design", {"design": {"font": "Georgia"}}),
    ("POST", "/api/settings/llm", {"enabled": True}),
]


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_premium_routes_answer_403_while_premium_is_off(
    project: Path, method: str, path: str, body: dict[str, Any] | None
) -> None:
    error = refused(make(project), method, path, body)
    assert error.status == 403 and "regwatch premium on" in error.message
    assert load_config(project).document.font == "system"
    assert load_config(project).llm.enabled is False


@pytest.fixture
def premium(project: Path) -> Path:
    project.write_text(
        project.read_text(encoding="utf-8") + "\n[premium]\nenabled = true\n", encoding="utf-8"
    )
    return project


def test_the_newsletter_preview_and_its_downloads(premium: Path) -> None:
    api = make(premium)
    data = get(api, "/api/newsletter", since="30")
    assert data["since"] == 30 and data["periods"] == [7, 14, 30, 90]
    assert data["subject"] == "Example Pantry Co. regulatory newsletter"
    assert "<table" in data["html"] and "IN THIS ISSUE" in data["text"]
    assert data["generated"] is False and data["dropped"] == []
    for fmt, content_type, start in (
        ("eml", "message/rfc822", b"Subject:"),
        ("html", "text/html; charset=utf-8", b"<!doctype html>"),
        ("txt", "text/plain; charset=utf-8", b"Example Pantry"),
    ):
        status, download = api.handle(
            "GET", "/api/newsletter/export", {"since": "30", "format": fmt}, {}
        )
        assert status == 200 and isinstance(download, Download)
        assert download.content_type == content_type and download.data.startswith(start)
        assert download.filename == f"regwatch-newsletter-2026-10-19.{fmt}"
    for bad in ({"since": "0"}, {"since": "x"}, {"since": "400"}):
        assert refused(api, "GET", "/api/newsletter", **bad).status == 400
    assert refused(api, "GET", "/api/newsletter/export", format="pdf").status == 400


def test_generated_newsletter_copy_is_written_once_and_reused(premium: Path) -> None:
    fake = FakeSystem("linux")
    fake.environ["REGWATCH_KEY_ANTHROPIC"] = KEY
    poster = FakePoster(PASSAGES)
    api = make(premium, fake, poster=poster)
    error = refused(api, "POST", "/api/newsletter/generate", {"since": 30})
    assert error.status == 409 and "Settings" in error.message
    post(api, "/api/settings/llm", {"enabled": True})
    assert refused(api, "GET", "/api/newsletter", since="30", generated="1").status == 409
    data = post(api, "/api/newsletter/generate", {"since": 30})
    assert data["generated"] is True and ">Generated</span>Four sources moved." in data["html"]
    again = get(api, "/api/newsletter", since="30", generated="1")
    _status, download = api.handle(
        "GET", "/api/newsletter/export", {"since": "30", "format": "txt", "generated": "1"}, {}
    )
    assert again["html"] == data["html"] and b"[Generated] Four sources moved." in download.data
    assert len(poster.payloads) == 1
    assert get(api, "/api/newsletter", since="30")["generated"] is False


def test_a_failed_generation_is_502_without_the_key(premium: Path) -> None:
    from regwatch.fetch import FetchError

    class Failing(FakePoster):
        def post_json(self, url: str, payload: Any, **kwargs: Any) -> str:
            raise FetchError(f"HTTP status 401 {KEY}", redact=kwargs["credential"].redact)

    fake = FakeSystem("linux")
    fake.environ["REGWATCH_KEY_ANTHROPIC"] = KEY
    api = make(premium, fake, poster=Failing([]))
    post(api, "/api/settings/llm", {"enabled": True})
    error = refused(api, "POST", "/api/newsletter/generate", {"since": 7})
    assert error.status == 502 and "HTTP status 401" in error.message and KEY not in error.message


def test_the_document_preview_and_downloads(premium: Path) -> None:
    api = make(premium)
    data = get(api, "/api/document", kind="report")
    assert data["title"] == "Example Pantry Co. change and due alert"
    assert data["formats"] == ["html", "docx", "md"]
    assert "<style>" in data["html"] and "Not legal advice." in data["html"]
    _status, download = api.handle(
        "GET", "/api/document/export", {"kind": "digest", "format": "docx"}, {}
    )
    assert download.data.startswith(b"PK") and download.filename.endswith("digest-2026-10-19.docx")
    assert refused(api, "GET", "/api/document", kind="memo").status == 400
    assert refused(api, "GET", "/api/document", tier="v9").status == 400
    assert refused(api, "GET", "/api/document/export", format="pdf").status == 400
    assert refused(api, "GET", "/api/document", generated="1").status == 409


def test_a_generated_document_summary(premium: Path) -> None:
    fake = FakeSystem("linux")
    fake.environ["REGWATCH_KEY_ANTHROPIC"] = KEY
    poster = FakePoster(
        [{"section": "opening", "text": "Dates are close.", "cites": ["event:2026-10-01-1"]}]
    )
    api = make(premium, fake, poster=poster)
    post(api, "/api/settings/llm", {"enabled": True})
    data = post(api, "/api/document/generate", {"kind": "briefing", "tier": "v2"})
    assert data["generated"] is True and "<h2>Summary</h2>" in data["html"]
    _status, download = api.handle(
        "GET",
        "/api/document/export",
        {"kind": "briefing", "tier": "v2", "format": "md", "generated": "1"},
        {},
    )
    assert b"Generated: Dates are close." in download.data and len(poster.payloads) == 1


def test_a_refused_logo_is_422_with_the_reason(premium: Path) -> None:
    (premium.parent / "logo.svg").write_text("<svg><script/></svg>", encoding="utf-8")
    premium.write_text(
        premium.read_text(encoding="utf-8") + '\n[document]\nlogo = "logo.svg"\n', encoding="utf-8"
    )
    api = make(premium)
    for path in ("/api/newsletter", "/api/document"):
        error = refused(api, "GET", path)
        assert error.status == 422 and "<script> element" in error.message


def test_settings_show_the_design_and_the_provider_keys_never_a_key(premium: Path) -> None:
    fake = FakeSystem("linux")
    fake.keychain["REGWATCH_KEY_OPENAI"] = KEY
    data = get(make(premium, fake), "/api/settings")
    design, llm = data["design"], data["llm"]
    assert design["primary_color"] == "#1d5a92" and "Georgia" in design["fonts"]
    assert design["page_sizes"] == ["a4", "letter"] and "Reply" in design["newsletter_footer"]
    assert (
        llm["provider"] == "anthropic" and llm["default_models"]["anthropic"] == "claude-opus-5-5"
    )
    keys = {row["id"]: row for row in llm["keys"]}
    assert keys["llm-openai"]["present"] is True and keys["llm-anthropic"]["present"] is False
    assert keys["llm-openai"]["where"] == "Stored in the keychain"
    assert KEY not in repr(data)


def test_the_design_is_saved_after_every_check(premium: Path) -> None:
    (premium.parent / "logo.png").write_bytes(make_png())
    api = make(premium)
    data = post(
        api,
        "/api/settings/design",
        {
            "design": {
                "organisation": "Pantry Co",
                "primary_color": "#0b3d2e",
                "font": "Georgia",
                "logo": "logo.png",
                "page_size": "letter",
                "newsletter_footer": "Reply STOP to stop.",
            }
        },
    )
    assert data["design"]["logo"] == "logo.png" and data["design"]["font"] == "Georgia"
    config = load_config(premium)
    assert (
        config.document.primary_color == "#0b3d2e"
        and config.newsletter.footer == "Reply STOP to stop."
    )
    before = premium.read_text(encoding="utf-8")
    for design, words in (
        ({"primary_color": "#ffee00"}, "contrast"),
        ({"font": "Papyrus"}, "font must be one of"),
        ({"title_format": "{secret}"}, "may use only"),
        ({"logo": "missing.png"}, "not found"),
        ({"colour": "#000000"}, "unknown keys"),
        ({"newsletter_footer": "a\x07b"}, "control characters"),
    ):
        error = refused(api, "POST", "/api/settings/design", {"design": design})
        assert error.status == 400 and words in error.message
    (premium.parent / "bad.svg").write_text("<svg onload='x'/>", encoding="utf-8")
    assert (
        refused(api, "POST", "/api/settings/design", {"design": {"logo": "bad.svg"}}).status == 400
    )
    assert premium.read_text(encoding="utf-8") == before
    assert refused(api, "POST", "/api/settings/design", {"design": {"font": 3}}).status == 400
    (premium.parent / "good.svg").write_text(SAFE_SVG, encoding="utf-8")
    assert (
        post(api, "/api/settings/design", {"design": {"logo": "good.svg"}})["design"]["logo"]
        == "good.svg"
    )


def test_the_llm_settings_and_the_provider_key_routes(premium: Path) -> None:
    fake = FakeSystem("linux")
    api = make(premium, fake)
    data = post(
        api, "/api/settings/llm", {"provider": "openai", "model": "gpt-test", "enabled": True}
    )
    assert (data["llm"]["provider"], data["llm"]["model"], data["llm"]["enabled"]) == (
        "openai",
        "gpt-test",
        True,
    )
    for body in ({"provider": "other"}, {"enabled": "yes"}, {"model": 3}, {"model": "bad model"}):
        assert refused(api, "POST", "/api/settings/llm", body).status == 400
    stored = post(api, "/api/keys/set", {"source_id": "llm-openai", "key": KEY})
    assert stored == {"available": True, "source_id": "llm-openai", "present": True}
    assert fake.keychain == {"REGWATCH_KEY_OPENAI": KEY}
    assert post(api, "/api/keys/remove", {"source_id": "llm-openai"})["removed"] is True
