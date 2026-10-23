"""A source may name only a key variable in regwatch's namespace, and one key serves one host."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from test_catalogue import keyed, raw
from test_fetch import PUBLIC, make, ok, web

from regwatch.catalogue import (
    CatalogueError,
    entry_from_dict,
    load_source_catalogue,
    parse_source_catalogue,
)
from regwatch.check import fetch_source
from regwatch.config import load_config
from regwatch.fetch import FetchError
from regwatch.focus import load_catalogue
from regwatch.keys import KeyStore, KeyStoreError, shared_key_errors
from regwatch.register import Source, validate_register
from regwatch.system import System
from regwatch.workspace import key_lookup

# Assembled from fragments so no file holds a token-shaped value.
UNRELATED = "unrelated" + "-secret-" + "value-1234"
KEY = "fake" + "-key-" + "4567"
FOCUS = [area.focus_id for area in load_catalogue(None)]


def _source(url: str, key_env: str) -> Source:
    return Source("evil", "us", "Evil", url, "poll", "api", "daily", "", "query:api_key", key_env)


@pytest.mark.parametrize(
    "name",
    ["CI_DEPLOY_TOKEN", "AWS_SECRET_ACCESS_KEY", "REGWATCH_KEY_", "REGWATCH_KEY_" + "A" * 52],
)
def test_the_keystore_refuses_a_variable_outside_the_namespace(name: str) -> None:
    system = System(platform="linux", which=lambda tool: None, environ={name: UNRELATED})
    with pytest.raises(KeyStoreError, match="REGWATCH_KEY_"):
        KeyStore(system).get(name)


def test_the_longest_allowed_variable_is_accepted() -> None:
    name = "REGWATCH_KEY_" + "A" * 51
    system = System(platform="linux", which=lambda tool: None, environ={name: KEY})
    assert KeyStore(system).get(name) == KEY


def test_a_source_cannot_read_an_unrelated_environment_variable() -> None:
    system = System(
        platform="linux", which=lambda tool: None, environ={"CI_DEPLOY_TOKEN": UNRELATED}
    )
    network = web(ok(), hosts={"collector.example": [PUBLIC]})
    with pytest.raises(FetchError, match="REGWATCH_KEY_"):
        fetch_source(
            _source("https://collector.example/x", "CI_DEPLOY_TOKEN"),
            make(network),
            key_lookup(KeyStore(system)),
        )
    assert network.requests == []


def test_fetch_source_refuses_the_variable_before_asking_for_a_key() -> None:
    asked: list[str] = []

    def lookup(name: str) -> str | None:
        asked.append(name)
        return UNRELATED

    network = web(ok(), hosts={"collector.example": [PUBLIC]})
    with pytest.raises(FetchError, match="no key was read or sent"):
        fetch_source(_source("https://collector.example/x", "HOME"), make(network), lookup)
    assert asked == [] and network.requests == []


def test_the_catalogue_refuses_a_variable_outside_the_namespace() -> None:
    with pytest.raises(CatalogueError, match="REGWATCH_KEY_"):
        entry_from_dict(keyed(key_env="AWS_SECRET_ACCESS_KEY"), FOCUS)


def test_shared_key_errors_compare_host_and_port() -> None:
    assert (
        shared_key_errors(
            [
                ("a", "REGWATCH_KEY_X", "https://api.example.org/one"),
                ("b", "REGWATCH_KEY_X", "https://API.example.org/two"),
                ("c", "REGWATCH_KEY_Y", "https://other.example/"),
            ]
        )
        == []
    )
    [message] = shared_key_errors(
        [
            ("a", "REGWATCH_KEY_X", "https://api.example.org/one"),
            ("b", "REGWATCH_KEY_X", "https://api.example.org:8443/two"),
        ]
    )
    assert "REGWATCH_KEY_X" in message and "a, b" in message
    # An address whose port cannot be read is compared as written, so it differs.
    assert shared_key_errors(
        [
            ("a", "REGWATCH_KEY_X", "https://h.example/"),
            ("b", "REGWATCH_KEY_X", "https://h.example:99999/"),
        ]
    )


def test_two_catalogue_entries_may_not_share_a_key_variable_across_hosts() -> None:
    first = keyed(source_id="aa-one", url="https://api.example.org/a")
    same_host = keyed(source_id="aa-two", url="https://api.example.org/b")
    assert len(parse_source_catalogue({"version": 1, "sources": [first, same_host]}, FOCUS)) == 2
    other_host = keyed(source_id="aa-three", url="https://collector.example/c")
    with pytest.raises(CatalogueError, match="shared by sources at different hosts"):
        parse_source_catalogue({"version": 1, "sources": [first, other_host]}, FOCUS)


def test_an_extra_file_cannot_borrow_a_shipped_key_for_another_host(tmp_path: Path) -> None:
    extra = tmp_path / "extra.json"
    entry = keyed(
        source_id="my-collector", key_env="REGWATCH_KEY_FRED", url="https://collector.example/x"
    )
    extra.write_text(json.dumps({"version": 1, "sources": [entry]}), encoding="utf-8")
    with pytest.raises(CatalogueError, match="REGWATCH_KEY_FRED is shared"):
        load_source_catalogue(FOCUS, extra)
    entry["url"] = "https://api.stlouisfed.org/fred/series"
    extra.write_text(json.dumps({"version": 1, "sources": [entry]}), encoding="utf-8")
    assert load_source_catalogue(FOCUS, extra)[-1].source_id == "my-collector"


def test_a_free_entry_still_builds() -> None:
    assert entry_from_dict(raw(), FOCUS).key_env is None


def _keyed_source(source_id: str, url: str, key_env: str) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "jurisdiction": "us",
        "name": source_id,
        "url": url,
        "method": "poll",
        "mechanism": "api",
        "cadence": "daily",
        "auth": "query:api_key",
        "key_env": key_env,
    }


def test_the_sources_file_refuses_a_variable_outside_the_namespace(
    project: Path, edit_json: Callable[[Path, Callable[[Any], None]], None]
) -> None:
    def edit(data: Any) -> None:
        data["sources"][0].update({"auth": "query:k", "key_env": "GITHUB_TOKEN"})

    edit_json(project.parent / "register" / "sources.json", edit)
    errors = validate_register(load_config(project))
    assert any("key_env" in e and "REGWATCH_KEY_" in e for e in errors), errors


def test_the_sources_file_refuses_a_key_variable_shared_across_hosts(
    project: Path, edit_json: Callable[[Path, Callable[[Any], None]], None]
) -> None:
    jurisdiction = {}

    def edit(data: Any) -> None:
        jurisdiction["id"] = data["sources"][0]["jurisdiction"]
        data["sources"] += [
            _keyed_source("fred-one", "https://api.stlouisfed.org/a", "REGWATCH_KEY_FRED"),
            _keyed_source("fred-two", "https://collector.example/b", "REGWATCH_KEY_FRED"),
        ]
        for source in data["sources"][-2:]:
            source["jurisdiction"] = jurisdiction["id"]

    edit_json(project.parent / "register" / "sources.json", edit)
    errors = validate_register(load_config(project))
    assert any("REGWATCH_KEY_FRED is shared" in e for e in errors), errors

    def same_host(data: Any) -> None:
        data["sources"][-1]["url"] = "https://api.stlouisfed.org/b"

    edit_json(project.parent / "register" / "sources.json", same_host)
    assert validate_register(load_config(project)) == []
