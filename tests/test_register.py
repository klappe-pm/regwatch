from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from regwatch.config import Config, load_config
from regwatch.register import (
    RegisterError,
    ancestors,
    load_register,
    load_schema,
    parse_date,
    split_list,
    validate_register,
)

EditJson = Callable[[Path, Callable[[Any], None]], None]


def reg_file(config: Config, name: str) -> Path:
    return config.register.obligations.parent / name


def rewrite_csv(config: Config, mutate: Callable[[str], str]) -> None:
    path = config.register.obligations
    path.write_text(mutate(path.read_text(encoding="utf-8")), encoding="utf-8")


def test_example_register_is_valid_and_loads(config: Config) -> None:
    assert validate_register(config) == []
    register = load_register(config)
    assert len(register.obligations) == 7
    assert len(register.sources) == 5
    assert len(register.categories) == 5
    assert len(register.jurisdictions) == 6
    assert register.portfolio.name == "Example Pantry Co."
    assert len(register.portfolio.products) == 3
    assert set(register.detail) == {
        "nl-allergen-order",
        "nl-colorant-guidance",
        "sv-origin-labeling",
    }
    assert len(register.changelog) == 3
    assert register.enforcement is not None
    assert len(register.enforcement.themes) == 2
    assert len(register.themes) == 2


def test_obligation_fields_are_parsed(config: Config) -> None:
    register = load_register(config)
    order = next(o for o in register.obligations if o.obligation_id == "nl-allergen-order")
    assert order.categories == ("allergens",)
    assert order.terms == ("peanut", "sesame", "milk")
    assert order.claims == ()
    assert order.scope == ("all",)
    assert order.effective_date == "2027-03-01"
    assert register.delimiter == ";"


def test_optional_sidecars_may_be_absent(project: Path) -> None:
    text = project.read_text(encoding="utf-8")
    for line in ("detail", "changelog", "enforcement", "themes"):
        text = "\n".join(row for row in text.splitlines() if not row.startswith(f"{line} ="))
    project.write_text(text, encoding="utf-8")
    register = load_register(load_config(project))
    assert register.detail == {}
    assert register.changelog == ()
    assert register.enforcement is None
    assert register.themes == ()


def test_schema_is_packaged_data() -> None:
    schema = load_schema()
    assert schema["list_delimiter"] == ";"
    assert "obligation_id" in schema["obligation_fields"]
    assert "country" not in schema["obligation_fields"]


def test_helpers() -> None:
    assert split_list(" a ; b;;c ", ";") == ["a", "b", "c"]
    assert split_list("", ";") == []
    assert parse_date("2026-02-30") is None
    assert parse_date("2026-02-28") is not None
    assert parse_date("") is None
    parents = {"c": "b", "b": "a", "a": ""}
    assert ancestors("c", parents) == ["b", "a"]
    assert ancestors("a", parents) == []
    assert ancestors("x", parents) == []
    assert ancestors("p", {"p": "q", "q": "p"}) == ["q"]


def test_csv_unknown_reference_enum_and_dates(config: Config) -> None:
    rewrite_csv(
        config,
        lambda t: (
            t.replace("nl-allergen-order,nl,final-rule", "nl-allergen-order,zz,guidance-x", 1)
            .replace("2026-09-01,high,Invented", "2026-13-01,certain,Invented", 1)
            .replace(",allergens,peanut", ",nothing,peanut", 1)
        ),
    )
    errors = validate_register(config)
    joined = "\n".join(errors)
    assert "references unknown jurisdictions 'zz'" in joined
    assert "field 'instrument' value 'guidance-x' not in" in joined
    assert "field 'last_reviewed' value '2026-13-01' is not an ISO date" in joined
    assert "field 'confidence' value 'certain' not in" in joined
    assert "references unknown categories 'nothing'" in joined
    with pytest.raises(RegisterError) as caught:
        load_register(config)
    assert caught.value.errors == errors


def test_csv_duplicate_and_bad_id(config: Config) -> None:
    rewrite_csv(config, lambda t: t.replace("nl-colorant-guidance,", "nl-allergen-order,", 1))
    assert any("duplicate obligation_id" in e for e in validate_register(config))
    rewrite_csv(config, lambda t: t.replace("nl-east-sweetener-bill,", "Bad_ID,", 1))
    assert any("does not match pattern" in e for e in validate_register(config))


def test_csv_required_empty_and_https_url(config: Config) -> None:
    rewrite_csv(
        config,
        lambda t: t.replace("Allergen Declaration Order,allergens", ",allergens", 1).replace(
            "https://regulator.nl.example/orders/allergen,2026-09-01",
            "http://insecure.example/x,2026-09-01",
            1,
        ),
    )
    joined = "\n".join(validate_register(config))
    assert "field 'title' is required but empty" in joined
    assert "is not an https URL" in joined


def test_csv_header_problems(config: Config) -> None:
    rewrite_csv(config, lambda t: t.replace("citation,title", "extra,title", 1))
    joined = "\n".join(validate_register(config))
    assert "missing columns ['citation']" in joined
    assert "unexpected columns ['extra']" in joined


def test_csv_wrong_cell_count(config: Config) -> None:
    rewrite_csv(config, lambda t: t.rstrip("\n") + "\nshort-row,nl,statute\n")
    assert any("more or fewer cells" in e for e in validate_register(config))
    rewrite_csv(config, lambda t: t.rstrip("\n") + ",unexpected,cells,here\n")
    assert any("more or fewer cells" in e for e in validate_register(config))


def test_csv_with_byte_order_mark_loads(config: Config) -> None:
    path = config.register.obligations
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert validate_register(config) == []


def test_csv_quoted_newline_is_one_row(config: Config) -> None:
    rewrite_csv(config, lambda t: t.replace("Invented example row", '"Invented\nexample row"', 1))
    assert validate_register(config) == []
    assert len(load_register(config).obligations) == 7


def test_csv_oversized_field_is_a_register_error(config: Config) -> None:
    rewrite_csv(config, lambda t: t.rstrip("\n") + "\n" + "x" * 200_000 + "\n")
    with pytest.raises(RegisterError, match="not valid CSV"):
        validate_register(config)


def test_missing_file_is_a_register_error(config: Config) -> None:
    config.register.sources.unlink()
    with pytest.raises(RegisterError, match="cannot read sources file"):
        validate_register(config)


def test_invalid_json_and_wrong_shape(config: Config) -> None:
    config.register.categories.write_text("{not json", encoding="utf-8")
    with pytest.raises(RegisterError, match="not valid JSON"):
        validate_register(config)
    config.register.categories.write_text("[]", encoding="utf-8")
    with pytest.raises(RegisterError, match="JSON object at the top level"):
        validate_register(config)
    config.register.categories.write_text('{"categories": {}}', encoding="utf-8")
    with pytest.raises(RegisterError, match="'categories' list of objects"):
        validate_register(config)


def test_register_file_over_the_size_limit(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("regwatch.register.MAX_REGISTER_FILE_BYTES", 10)
    with pytest.raises(RegisterError, match="larger than"):
        validate_register(config)


def test_non_utf8_file(config: Config) -> None:
    config.register.categories.write_bytes(b"\xff\xfe\x00")
    with pytest.raises(RegisterError, match="cannot read categories file"):
        validate_register(config)


def test_catalog_errors(config: Config, edit_json: EditJson) -> None:
    def mutate_sources(data: Any) -> None:
        data["sources"][0]["mechanism"] = "carrier-pigeon"
        data["sources"][1]["url"] = "http://insecure.example/"
        data["sources"][2]["surprise"] = "field"

    edit_json(config.register.sources, mutate_sources)
    joined = "\n".join(validate_register(config))
    assert "field 'mechanism' value 'carrier-pigeon' not in" in joined
    assert "is not an https or file URL" in joined
    assert "unexpected fields ['surprise']" in joined


def test_file_urls_are_valid_sources(config: Config, edit_json: EditJson) -> None:
    edit_json(config.register.sources, lambda d: d["sources"][0].update(url="file:///tmp/feed.xml"))
    assert validate_register(config) == []


def test_product_errors(config: Config, edit_json: EditJson) -> None:
    def mutate(data: Any) -> None:
        data["products"][0]["markets"] = []
        data["products"][1]["categories"] = ["ghost"]
        data["products"][2]["terms"] = "not a list; but delimited"

    edit_json(config.register.portfolio, mutate)
    joined = "\n".join(validate_register(config))
    assert "field 'markets' is required but empty" in joined
    assert "references unknown categories 'ghost'" in joined
    assert "terms" not in joined


def test_scalar_field_given_a_list(config: Config, edit_json: EditJson) -> None:
    edit_json(config.register.portfolio, lambda d: d["products"][0].update(name=["a", "b"]))
    assert any("must be a single value" in e for e in validate_register(config))


def test_missing_portfolio_products(config: Config, edit_json: EditJson) -> None:
    edit_json(config.register.portfolio, lambda d: d.pop("products"))
    with pytest.raises(RegisterError, match="'products' list"):
        validate_register(config)


def test_jurisdiction_parent_rules(config: Config, edit_json: EditJson) -> None:
    def cycle(data: Any) -> None:
        data["jurisdictions"][0]["parent"] = "nl-east"

    edit_json(config.register.jurisdictions, cycle)
    assert any("contains a cycle" in e for e in validate_register(config))

    def selfish(data: Any) -> None:
        data["jurisdictions"][0]["parent"] = "nl"

    edit_json(config.register.jurisdictions, selfish)
    assert any("must not be the jurisdiction itself" in e for e in validate_register(config))

    def unknown(data: Any) -> None:
        data["jurisdictions"][0]["parent"] = "atlantis"

    edit_json(config.register.jurisdictions, unknown)
    assert any(
        "references unknown jurisdictions 'atlantis'" in e for e in validate_register(config)
    )


def test_detail_errors(config: Config, edit_json: EditJson) -> None:
    assert config.register.detail is not None

    def mutate(data: Any) -> None:
        data["detail"]["ghost-id"] = dict(data["detail"]["nl-allergen-order"])
        data["detail"]["nl-allergen-order"]["summary"] = ""
        data["detail"]["nl-allergen-order"]["topics"] = ["unlisted"]
        data["detail"]["nl-colorant-guidance"]["citations"] = [
            {"citation": "", "url": "http://x.example"}
        ]
        data["detail"]["sv-origin-labeling"]["topics"] = "oops"

    edit_json(config.register.detail, mutate)
    joined = "\n".join(validate_register(config))
    assert "detail 'ghost-id': not a known obligation_id" in joined
    assert "field 'summary' is required but empty" in joined
    assert "topic 'unlisted' not in topics_vocabulary" in joined
    assert "each entry in 'citations' needs a 'citation'" in joined
    assert "'citations' url 'http://x.example' is not an https URL" in joined
    assert "field 'topics' must be a list" in joined


def test_detail_wrong_shape(config: Config, edit_json: EditJson) -> None:
    assert config.register.detail is not None
    edit_json(config.register.detail, lambda d: d.update(detail=[]))
    assert any("'detail' object keyed by obligation_id" in e for e in validate_register(config))


def test_citation_lists_must_be_lists_of_objects(config: Config, edit_json: EditJson) -> None:
    assert config.register.detail is not None
    edit_json(
        config.register.detail, lambda d: d["detail"]["nl-allergen-order"].update(backlinks="x")
    )
    assert any("'backlinks' must be a list of objects" in e for e in validate_register(config))


def test_changelog_errors(config: Config, edit_json: EditJson) -> None:
    assert config.register.changelog is not None

    def mutate(data: Any) -> None:
        data["events"][0]["date"] = "yesterday"
        data["events"][0]["headline"] = ""
        data["events"][1]["jurisdiction"] = "atlantis"
        data["events"][2]["obligation_id"] = "ghost"

    edit_json(config.register.changelog, mutate)
    joined = "\n".join(validate_register(config))
    assert "date 'yesterday' is not an ISO date" in joined
    assert "field 'headline' is required but empty" in joined
    assert "jurisdiction 'atlantis' is not a known jurisdiction" in joined
    assert "obligation_id 'ghost' is not a known obligation" in joined


def test_enforcement_and_theme_errors(config: Config, edit_json: EditJson) -> None:
    assert config.register.enforcement is not None
    assert config.register.themes is not None
    edit_json(config.register.enforcement, lambda d: d["themes"][0].update(theme=""))
    edit_json(
        config.register.themes,
        lambda d: (
            d["themes"][0].update(categories=["ghost"]),
            d["themes"][1].update(key="sweeteners", categories=[]),
        ),
    )
    joined = "\n".join(validate_register(config))
    assert "enforcement theme 1: field 'theme' is required but empty" in joined
    assert "references unknown categories 'ghost'" in joined
    assert "duplicate key 'sweeteners'" in joined
    assert "'categories' must be a non-empty list" in joined


def test_sidecar_wrong_shapes(config: Config, edit_json: EditJson) -> None:
    assert config.register.enforcement is not None
    edit_json(config.register.enforcement, lambda d: d.update(themes="x"))
    assert any("'themes' list of objects" in e for e in validate_register(config))


def test_loaded_register_is_never_written(config: Config) -> None:
    before = {p: p.read_bytes() for p in config.register.all_paths()}
    load_register(config)
    assert {p: p.read_bytes() for p in config.register.all_paths()} == before


def test_unparseable_url_is_a_validation_error_not_a_crash(config: Config) -> None:
    rewrite_csv(
        config,
        lambda t: t.replace("https://regulator.nl.example/orders/allergen", "https://[::1", 1),
    )
    assert any("is not an https URL" in e for e in validate_register(config))
