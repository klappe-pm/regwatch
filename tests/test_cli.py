from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from conftest import EXAMPLES, NOW, TODAY, FakeFetcher, snapshot_responses

from regwatch import __version__
from regwatch.cli import main
from regwatch.config import Config, load_config
from regwatch.fetch import FetchError


class Result:
    def __init__(self, code: int, out: str, err: str) -> None:
        self.code = code
        self.out = out
        self.err = err


@pytest.fixture
def run(project: Path, capsys: pytest.CaptureFixture[str]):  # type: ignore[no-untyped-def]
    def invoke(
        *args: str, fetcher: FakeFetcher | None = None, config: Path | None = None
    ) -> Result:
        code = main(
            ["--config", str(config or project), *args], fetcher=fetcher, today=TODAY, now=NOW
        )
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return invoke


def digest_of(paths: list[Path]) -> dict[Path, str]:
    return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["--version"])
    assert caught.value.code == 0
    assert capsys.readouterr().out.strip() == f"regwatch {__version__}"


def test_a_command_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main([])
    assert caught.value.code == 2
    assert "required" in capsys.readouterr().err


def test_help_carries_the_disclaimer(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "Not legal advice" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        main(["impact", "--help"])
    assert "Not legal advice" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("action", "phrase"),
    [
        ("set", "prompt for it without echoing it"),
        ("list", "whether its key is stored"),
        ("remove", "Delete the stored key"),
    ],
)
def test_each_keys_action_has_a_help_description(
    action: str, phrase: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(["keys", action, "--help"])
    assert phrase in " ".join(capsys.readouterr().out.split())


def test_missing_configuration(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    result = run("validate", config=tmp_path / "nothing.toml")
    assert result.code == 2
    assert "cannot read configuration file" in result.err


def test_validate_ok(run) -> None:  # type: ignore[no-untyped-def]
    result = run("validate")
    assert result.code == 0
    assert result.out.strip() == (
        "regwatch validate: 7 obligations, 5 sources, 5 categories, 6 jurisdictions, "
        "3 products; errors=0"
    )


def test_validate_reports_every_error(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    text = config.register.obligations.read_text(encoding="utf-8")
    config.register.obligations.write_text(
        text.replace(",nl,final-rule", ",zz,final-rule"), encoding="utf-8"
    )
    result = run("validate")
    assert result.code == 1
    assert (
        "ERROR obligations entry 2 (nl-allergen-order): field 'jurisdiction' references unknown"
        in result.out
    )
    assert result.out.strip().endswith("errors=1")


def test_other_commands_refuse_an_invalid_register(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    config.register.obligations.write_text("garbage\n", encoding="utf-8")
    for command in (["impact"], ["check"], ["brief"], ["coverage"], ["list"], ["digest"]):
        result = run(*command)
        assert result.code == 1, command
        assert "ERROR " in result.err
        assert "regwatch validate" in result.err


def test_unreadable_register_file(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    config.register.portfolio.unlink()
    result = run("validate")
    assert result.code == 1
    assert "cannot read portfolio file" in result.err


def test_coverage(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    result = run("coverage")
    assert result.code == 0
    assert "regwatch coverage: 6 jurisdictions; aggregate=1, confirmed=4, tracked=1" in result.out
    assert "WARN" not in result.out
    data = json.loads(config.register.jurisdictions.read_text(encoding="utf-8"))
    data["jurisdictions"][3]["coverage"] = "confirmed"
    config.register.jurisdictions.write_text(json.dumps(data), encoding="utf-8")
    assert "WARN  nl-north is marked confirmed but has no obligation rows" in run("coverage").out


def test_list_filters(run) -> None:  # type: ignore[no-untyped-def]
    assert "regwatch list: 7 obligations" in run("list").out
    assert "regwatch list: 2 obligations" in run("list", "--jurisdiction", "sv").out
    assert "regwatch list: 3 obligations" in run("list", "--category", "sweeteners").out
    assert "regwatch list: 2 obligations" in run("list", "--status", "proposed").out
    upcoming = run("list", "--upcoming", "60")
    assert "regwatch list: 1 obligations" in upcoming.out
    assert "2026-11-15" in upcoming.out
    assert "(no date)" in run("list", "--status", "monitoring").out


def test_portfolio(run) -> None:  # type: ignore[no-untyped-def]
    result = run("portfolio")
    assert "berry-spread" in result.out
    assert "regwatch portfolio: Example Pantry Co., 3 products" in result.out


def test_capture(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    responses: dict[str, str | Exception] = dict(snapshot_responses(config))
    shutil.rmtree(config.snapshots_dir)
    fetcher = FakeFetcher(responses)
    result = run("capture", fetcher=fetcher)
    assert result.code == 0
    assert "regwatch capture: 4/5 sources" in result.out
    assert "skipped    sv-newsroom" in result.out
    assert (config.snapshots_dir / "nl-notices.txt").read_text(encoding="utf-8") == responses[
        "https://regulator.nl.example/notices.xml"
    ]


def test_capture_one_source_and_failures(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    fetcher = FakeFetcher({"https://api.sv.example/documents.json": FetchError("HTTP status 500")})
    result = run("capture", "--source", "sv-register-api", fetcher=fetcher)
    assert result.code == 1
    assert "fetch failed: HTTP status 500" in result.out
    assert run("capture", "--source", "nope", fetcher=fetcher).code == 2


def test_check_offline_then_accept_then_unchanged(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    first = run("check")
    assert first.code == 0
    assert "NEW        nl-notices" in first.out
    assert "MANUAL     sv-newsroom" in first.out
    assert "regwatch check: 5 sources; manual=1, new=4" in first.out
    assert "run again with --accept" in first.out
    assert "Not legal advice" in first.out or "not legal advice" in first.out
    assert not config.seen_path.exists()

    assert run("check", "--exit-code").code == 3

    accepted = run("check", "--accept")
    assert accepted.code == 0
    assert config.seen_path.exists()
    seen = json.loads(config.seen_path.read_text(encoding="utf-8"))
    assert set(seen) == {"nl-notices", "nl-east-gazette", "sv-register-api", "sv-subscription"}
    assert seen["nl-notices"]["checked"] == "2026-10-19T12:00:00+00:00"

    again = run("check", "--exit-code")
    assert again.code == 0
    assert "unchanged=4" in again.out

    path = config.snapshots_dir / "sv-subscription.txt"
    path.write_text(
        path.read_text(encoding="utf-8") + "\n2026-10-19  New item.\n", encoding="utf-8"
    )
    changed = run("check", "--exit-code")
    assert changed.code == 3
    assert "CHANGED    sv-subscription" in changed.out


def test_check_fetch_mode_and_source_filter(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    fetcher = FakeFetcher(snapshot_responses(config))
    result = run("check", "--fetch", "--source", "nl-notices", fetcher=fetcher)
    assert result.code == 0
    assert "live" in result.out
    assert fetcher.requested == ["https://regulator.nl.example/notices.xml"]
    failing = run("check", "--fetch", "--source", "nl-notices", fetcher=FakeFetcher())
    assert "ERROR      nl-notices" in failing.out
    assert failing.code == 0


def test_check_unknown_source(run) -> None:  # type: ignore[no-untyped-def]
    result = run("check", "--source", "nope")
    assert result.code == 2
    assert "no source 'nope'" in result.err


def test_ingest_from_file(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    result = run("ingest", "--from-file", str(EXAMPLES / "ingest-response.json"))
    assert result.code == 0
    assert "2 candidate events from file (since 2025-10-19)" in result.out
    document = json.loads(config.candidates_path.read_text(encoding="utf-8"))
    assert document["origin"] == "file"
    assert all(c["needs_review"] for c in document["candidates"])


def test_ingest_fetch(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    body = (EXAMPLES / "ingest-response.json").read_text(encoding="utf-8")

    class Echo(FakeFetcher):
        def fetch(self, url: str) -> str:
            self.requested.append(url)
            return body

    fetcher = Echo()
    result = run("ingest", "--fetch", "--since", "30", fetcher=fetcher)
    assert result.code == 0
    assert "from live (since 2026-09-19)" in result.out
    assert "conditions%5Bpublication_date%5D%5Bgte%5D=2026-09-19" in fetcher.requested[0]


def test_ingest_needs_a_source_and_reports_bad_input(run, tmp_path: Path, config: Config) -> None:  # type: ignore[no-untyped-def]
    assert run("ingest").code == 2
    assert not config.candidates_path.exists()
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    result = run("ingest", "--from-file", str(bad))
    assert result.code == 2
    assert "not valid JSON" in result.err
    assert run("ingest", "--from-file", str(tmp_path / "absent.json")).code == 2
    assert run("ingest", "--fetch", fetcher=FakeFetcher()).code == 2
    assert not config.candidates_path.exists()


def test_ingest_file_size_limit(run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("regwatch.cli.MAX_INPUT_BYTES", 5)
    big = tmp_path / "big.json"
    big.write_text('{"results": []}', encoding="utf-8")
    result = run("ingest", "--from-file", str(big))
    assert result.code == 2
    assert "larger than" in result.err


def test_impact(run) -> None:  # type: ignore[no-untyped-def]
    result = run("impact")
    assert result.code == 0
    assert "regwatch impact: 7 candidate impacts across 3 products" in result.out
    assert result.out.index("act-now") < result.out.index("watch")
    assert "category: sweeteners; term: sucralose" in result.out
    assert "not legal advice" in result.out.lower()
    only = run("impact", "--product", "oat-bar", "--severity", "act-now")
    assert "regwatch impact: 1 candidate impacts" in only.out
    assert "Allergen Declaration Order" in only.out


def test_impact_rejects_unknown_severity(run) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(SystemExit):
        run("impact", "--severity", "panic")


def test_themes(run) -> None:  # type: ignore[no-untyped-def]
    result = run("themes")
    assert "## Sweeteners and added sugar" in result.out
    assert "Affected products: Berry Fruit Spread, Cinnamon Breakfast Cereal" in result.out
    assert "regwatch themes: 2 findings" in result.out


def test_brief_prints_markdown_by_default(run) -> None:  # type: ignore[no-untyped-def]
    result = run("brief", "--tier", "v1")
    assert result.code == 0
    assert result.out.startswith("# Example Pantry Co. regulatory briefing")
    assert "## Key Items" in result.out
    assert "Not legal advice" in result.out


def test_brief_writes_markdown_and_model(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "out"
    result = run("brief", "--kind", "weekly", "--out-dir", str(out))
    assert result.code == 0
    assert (
        (out / "regwatch-weekly-brief.md")
        .read_text(encoding="utf-8")
        .startswith("# Example Pantry Co.")
    )
    model = json.loads((out / "regwatch-weekly-brief.json").read_text(encoding="utf-8"))
    assert model["title"] == "Example Pantry Co. regulatory weekly synthesis"
    run("brief", "--kind", "daily", "--out-dir", str(out), "--name", "today")
    assert (out / "today.md").exists()
    assert "Flagged For Review" in (out / "today.md").read_text(encoding="utf-8")
    run("brief", "--tier", "v2", "--since-days", "60", "--out-dir", str(out))
    assert (out / "regwatch-briefing-v2.md").exists()


def test_daily_brief_fetch_mode(run) -> None:  # type: ignore[no-untyped-def]
    result = run("brief", "--kind", "daily", "--fetch", fetcher=FakeFetcher())
    assert result.code == 0
    assert "Northland regulator notices feed: could not be read" in result.out


def test_brief_includes_ingest_candidates_in_v3(run) -> None:  # type: ignore[no-untyped-def]
    run("ingest", "--from-file", str(EXAMPLES / "ingest-response.json"))
    result = run("brief", "--tier", "v3")
    assert "## Newly Detected, Unconfirmed" in result.out
    assert "What happened (unconfirmed)." in result.out


def test_brief_survives_a_corrupt_candidates_file(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    config.state_dir.mkdir(parents=True)
    config.candidates_path.write_text("{broken", encoding="utf-8")
    result = run("brief", "--tier", "v3")
    assert result.code == 2
    assert "cannot read" in result.err
    config.candidates_path.write_text('{"candidates": "nope"}', encoding="utf-8")
    assert run("brief", "--tier", "v3").code == 0


def test_render_formats(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "out"
    run("brief", "--kind", "weekly", "--out-dir", str(out))
    model = out / "regwatch-weekly-brief.json"
    rendered = tmp_path / "rendered"
    result = run("render", str(model), "--out-dir", str(rendered), "--tags", "regulatory,weekly")
    assert result.code == 0
    names = sorted(p.name for p in rendered.iterdir())
    assert names == [
        "regwatch-weekly-brief-newsletter.html",
        "regwatch-weekly-brief-newsletter.txt",
        "regwatch-weekly-brief-webpost.md",
        "regwatch-weekly-brief.docx",
        "regwatch-weekly-brief.md",
    ]
    assert "regwatch render: 5 files" in result.out
    assert "  - weekly" in (rendered / "regwatch-weekly-brief-webpost.md").read_text(
        encoding="utf-8"
    )
    subset = tmp_path / "subset"
    run("render", str(model), "--formats", "md", "--out-dir", str(subset))
    assert [p.name for p in subset.iterdir()] == ["regwatch-weekly-brief.md"]


def test_render_works_without_a_configuration_file(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    model = tmp_path / "m.json"
    model.write_text(
        json.dumps({"title": "T", "generated": "2026-01-01", "sections": []}), encoding="utf-8"
    )
    result = run(
        "render",
        str(model),
        "--formats",
        "md",
        "--out-dir",
        str(tmp_path / "o"),
        config=tmp_path / "none.toml",
    )
    assert result.code == 0
    assert "Not legal advice" in (tmp_path / "o" / "m.md").read_text(encoding="utf-8")


def test_render_rejects_bad_input(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    model = tmp_path / "m.json"
    model.write_text(json.dumps({"title": "T", "generated": "g", "sections": []}), encoding="utf-8")
    assert run("render", str(model), "--formats", "pdf").code == 2
    assert run("render", str(model), "--formats", ",").code == 2
    assert run("render", str(model), "--tags", "bad tag").code == 2
    model.write_text("[]", encoding="utf-8")
    result = run("render", str(model))
    assert result.code == 2
    assert "not a valid document model" in result.err
    model.write_text("not json", encoding="utf-8")
    assert run("render", str(model)).code == 2
    assert run("render", str(tmp_path / "absent.json")).code == 2


def test_render_refuses_a_float_section_level(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    model = tmp_path / "m.json"
    model.write_text(
        '{"title": "T", "generated": "g", "sections": [{"heading": "H", "level": 2.0}]}',
        encoding="utf-8",
    )
    result = run("render", str(model), "--out-dir", str(tmp_path / "out"))
    assert result.code == 2
    assert result.err.startswith("error:")
    assert "'level' must be 2, 3 or 4" in result.err
    assert "Traceback" not in result.err


def test_render_file_size_limit(run, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("regwatch.cli.MAX_INPUT_BYTES", 5)
    model = tmp_path / "m.json"
    model.write_text('{"title": "T"}', encoding="utf-8")
    assert run("render", str(model)).code == 2


def test_digest(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    result = run("digest", "--window", "60")
    assert "## Effective Within 60 Days" in result.out
    assert "### Northland East Region" in result.out
    out = tmp_path / "digest.md"
    written = run("digest", "--out", str(out))
    assert "wrote" in written.out
    assert out.read_text(encoding="utf-8").startswith("# Example Pantry Co. register digest")


def test_report(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    out, payload = tmp_path / "r.md", tmp_path / "r.json"
    result = run("report", "--out", str(out), "--json", str(payload))
    assert result.code == 0
    assert "four source changes flagged for review" in result.err
    text = out.read_text(encoding="utf-8")
    assert "Northland regulator notices feed: first snapshot taken" in text
    assert "## Obligations Effective Within 365 Days" in text
    data = json.loads(payload.read_text(encoding="utf-8"))
    assert data["window_days"] == 365
    assert len(data["source_changes"]) == 4
    assert data["sources_missing_snapshot"] == []
    assert "Not legal advice" in data["disclaimer"]
    assert data["upcoming"][0]["obligation_id"] == "nl-west-school-food"


def test_report_notes_missing_snapshots_and_errors(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    (config.snapshots_dir / "nl-notices.txt").unlink()
    assert "One source has no snapshot yet" in run("report").out
    fetched = run("report", "--fetch", fetcher=FakeFetcher()).out
    assert "Northland regulator notices feed: could not be read" in fetched


def test_export(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    csv_path, json_path = tmp_path / "e" / "records.csv", tmp_path / "e" / "records.json"
    result = run("export", "--csv", str(csv_path), "--json", str(json_path))
    assert result.code == 0
    assert "(7 records)" in result.out
    assert csv_path.read_text(encoding="utf-8").startswith(
        '"obligation_id","jurisdiction","status"'
    )
    assert len(json.loads(json_path.read_text(encoding="utf-8"))) == 7


def test_no_command_overwrites_a_register_file(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    before = digest_of(config.register.all_paths())
    for path in config.register.all_paths():
        assert run("export", "--csv", str(path)).code == 2
        assert run("digest", "--out", str(path)).code == 2
        assert run("report", "--out", str(path)).code == 2
        assert run("report", "--json", str(path)).code == 2
    assert digest_of(config.register.all_paths()) == before


def test_whole_pipeline_leaves_the_register_untouched(run, config: Config, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    before = digest_of(config.register.all_paths())
    out = tmp_path / "out"
    for command in (
        ["validate"],
        ["coverage"],
        ["list"],
        ["portfolio"],
        ["check", "--accept"],
        ["ingest", "--from-file", str(EXAMPLES / "ingest-response.json")],
        ["impact"],
        ["themes"],
        ["brief", "--out-dir", str(out)],
        ["brief", "--kind", "weekly", "--out-dir", str(out)],
        ["brief", "--kind", "daily", "--out-dir", str(out)],
        ["render", str(out / "regwatch-briefing-v3.json"), "--out-dir", str(out)],
        ["digest"],
        ["report"],
        ["export", "--csv", str(out / "r.csv")],
    ):
        assert run(*command).code == 0, command
    assert digest_of(config.register.all_paths()) == before
    assert load_config(config.base_dir / "regwatch.toml").register.obligations.exists()


def test_error_paths_never_print_a_traceback(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    result = run("export", "--csv", str(tmp_path))
    assert result.code == 2
    assert "Traceback" not in result.err
    assert result.err.startswith("error:")


def test_real_fetcher_is_built_from_the_settings_and_reads_file_urls(
    run,  # type: ignore[no-untyped-def]
    config: Config,
) -> None:
    data = json.loads(config.register.sources.read_text(encoding="utf-8"))
    for source in data["sources"]:
        source["url"] = (config.snapshots_dir / f"{source['source_id']}.txt").as_uri()
    config.register.sources.write_text(json.dumps(data), encoding="utf-8")
    toml = config.config_path
    toml.write_text(
        toml.read_text(encoding="utf-8").replace(
            "[fetch]\n", '[fetch]\nallowed_file_roots = ["snapshots"]\n'
        ),
        encoding="utf-8",
    )
    result = run("check", "--fetch")
    assert result.code == 0
    assert "regwatch check: 5 sources; error=" not in result.out
    assert "NEW        nl-notices                   live" in result.out


# --- findings of the security review ----------------------------------------------------


def test_exit_code_fails_on_a_source_error(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    fetcher = FakeFetcher(
        {"https://regulator.nl.example/notices.xml": FetchError("HTTP status 500")}
    )
    result = run("check", "--fetch", "--source", "nl-notices", "--exit-code", fetcher=fetcher)
    assert "ERROR      nl-notices" in result.out
    assert result.code == 4
    assert run("check", "--fetch", "--source", "nl-notices", fetcher=fetcher).code == 0


def test_exit_code_fails_when_a_source_has_no_content(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    (config.snapshots_dir / "nl-notices.txt").unlink()
    result = run("check", "--source", "nl-notices", "--exit-code")
    assert "MISSING" in result.out
    assert result.code == 4


def test_exit_code_reports_suspicious_content_and_it_is_not_accepted_silently(
    run, config: Config
) -> None:  # type: ignore[no-untyped-def]
    assert run("check", "--accept").code == 0
    (config.snapshots_dir / "sv-register-api.txt").write_text("{}", encoding="utf-8")
    result = run("check", "--exit-code")
    assert "SUSPICIOUS sv-register-api" in result.out
    assert result.code == 3
    before = json.loads(config.seen_path.read_text(encoding="utf-8"))
    refused = run("check", "--accept")
    assert "--accept-suspicious" in refused.out
    assert json.loads(config.seen_path.read_text(encoding="utf-8")) == before
    run("check", "--accept", "--accept-suspicious")
    after = json.loads(config.seen_path.read_text(encoding="utf-8"))
    assert after["sv-register-api"]["sha256"] != before["sv-register-api"]["sha256"]


def test_file_sources_are_refused_unless_a_root_is_configured(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    data = json.loads(config.register.sources.read_text(encoding="utf-8"))
    data["sources"][0]["url"] = (config.snapshots_dir / "nl-notices.txt").as_uri()
    config.register.sources.write_text(json.dumps(data), encoding="utf-8")
    result = run("check", "--fetch", "--source", "nl-notices")
    assert "ERROR      nl-notices" in result.out
    assert "file URLs are disabled" in result.out


def test_outputs_cannot_overwrite_the_configuration_or_state_files(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    run("check", "--accept")
    run("ingest", "--from-file", str(EXAMPLES / "ingest-response.json"))
    targets = [config.config_path, config.seen_path, config.candidates_path]
    before = digest_of(targets)
    for target in targets:
        for command in (
            ["export", "--csv"],
            ["export", "--csv", str(Path(config.base_dir) / "x.csv"), "--json"],
            ["digest", "--out"],
            ["report", "--out"],
            ["report", "--json"],
        ):
            assert run(*command, str(target)).code == 2, (command, target)
    assert digest_of(targets) == before


def test_outputs_cannot_land_inside_the_state_or_snapshots_directories(run, config: Config) -> None:  # type: ignore[no-untyped-def]
    for directory in (config.state_dir, config.snapshots_dir):
        result = run("digest", "--out", str(directory / "extra.md"))
        assert result.code == 2
        assert "state directory" in result.err
        assert not (directory / "extra.md").exists()


def test_a_case_variant_of_a_register_file_is_refused(run, config: Config, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    other = config.register.obligations.parent / "OBLIGATIONS.CSV"
    # On a case insensitive filesystem the variant is the register file itself.
    case_insensitive = other.exists()
    assert run("export", "--csv", str(other)).code == 2
    if not case_insensitive:
        assert not other.exists()


@pytest.mark.parametrize(
    "name", ["../escape", "a/b", "/abs", "..", ".hidden", "", "x" * 101, "a\\b", "with space"]
)
def test_brief_name_cannot_contain_path_separators(
    run, config: Config, tmp_path: Path, name: str
) -> None:  # type: ignore[no-untyped-def]
    out = tmp_path / "out"
    result = run("brief", "--out-dir", str(out), "--name", name)
    assert result.code == 2
    assert "--name" in result.err
    assert not out.exists()
    assert not (tmp_path / "escape.md").exists()


def test_brief_name_accepts_a_plain_name(run, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    assert run("brief", "--out-dir", str(tmp_path / "o"), "--name", "weekly-2026.10_a").code == 0
    assert (tmp_path / "o" / "weekly-2026.10_a.md").exists()


def test_csv_export_neutralises_formulas_from_the_register(
    run, config: Config, tmp_path: Path
) -> None:  # type: ignore[no-untyped-def]
    path = config.register.obligations
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "Allergen Declaration Order,allergens", "=HYPERLINK(1),allergens", 1
        ),
        encoding="utf-8",
    )
    detail = config.register.detail
    assert detail is not None
    data = json.loads(detail.read_text(encoding="utf-8"))
    data["detail"]["nl-allergen-order"]["summary"] = "@SUM(1)"
    detail.write_text(json.dumps(data), encoding="utf-8")
    csv_path = tmp_path / "records.csv"
    assert run("export", "--csv", str(csv_path)).code == 0
    text = csv_path.read_text(encoding="utf-8")
    assert "'@SUM(1)" in text
    assert ",@SUM" not in text and "\n@" not in text
