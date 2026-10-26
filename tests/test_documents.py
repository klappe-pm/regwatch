"""`regwatch document`: a briefing, digest or report that follows the design specification."""

from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
from conftest import TODAY
from test_design import SAFE_SVG
from test_newsletter import FakePoster, Runner, append, make_png

from regwatch.config import DocumentDesign, load_config
from regwatch.document import Document, GeneratedPassage, Section
from regwatch.llm import GenerationResult
from regwatch.render import docx_bytes, render_document_html, render_styles_xml
from regwatch.workspace import WorkspaceError, document_bytes, document_plan, with_summary

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
KEY = "fake" + "-doc-" + "key-7701"
DESIGN = (
    '[document]\ntitle_format = "{organisation}: {title} ({date})"\norganisation = "Pantry <Co>"\n'
    'primary_color = "#0b3d2e"\naccent_color = "#7a2e0b"\nfont = "Georgia"\nlogo = "logo.png"\n'
    'header = "Internal & draft"\nfooter = "1 Example Road"\npage_size = "letter"\n'
)


@pytest.fixture
def run(project: Path, capsys: pytest.CaptureFixture[str]) -> Runner:
    return Runner(project, capsys)


def designed(project: Path) -> None:
    (project.parent / "logo.png").write_bytes(make_png(240, 80))
    append(project, DESIGN)


def test_documents_need_premium(run: Runner, tmp_path: Path) -> None:
    code, _out, err = run("document", "--out", str(tmp_path / "d"))
    assert code == 2 and "Documents is a premium feature" in err and "regwatch premium on" in err
    assert not list(tmp_path.glob("d.*"))


@pytest.mark.parametrize("kind", ["briefing", "digest", "report"])
@pytest.mark.parametrize("fmt", ["html", "docx", "md"])
def test_every_kind_in_every_format(run: Runner, tmp_path: Path, kind: str, fmt: str) -> None:
    run("premium", "on")
    code, out, _err = run("document", "--kind", kind, "--format", fmt, "--out", str(tmp_path / "d"))
    assert code == 0 and f"wrote {tmp_path / ('d.' + fmt)}" in out
    data = (tmp_path / f"d.{fmt}").read_bytes()
    if fmt == "docx":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                ET.fromstring(archive.read(name))
    else:
        assert b"Not legal advice." in data


def test_the_html_follows_the_design_and_prints(run: Runner, project: Path, tmp_path: Path) -> None:
    designed(project)
    run("premium", "on")
    assert run("document", "--out", str(tmp_path / "d.html"))[0] == 0
    page = (tmp_path / "d.html").read_text(encoding="utf-8")
    assert "<h1>Pantry &lt;Co&gt;: Example Pantry Co. regulatory briefing (2026-10-19)</h1>" in page
    assert "color: #0b3d2e" in page and "border-bottom: 2px solid #7a2e0b" in page
    assert "font-family: Georgia, 'Times New Roman', serif" in page
    assert "@page { size: letter;" in page and "@media print" in page
    assert '<img class="logo" src="data:image/png;base64,' in page
    assert "Internal &amp; draft" in page and "1 Example Road" in page
    assert "<script" not in page and "http://" not in page


def test_word_carries_the_styles_header_footer_page_and_logo(
    run: Runner, project: Path, tmp_path: Path
) -> None:
    designed(project)
    run("premium", "on")
    assert run("document", "--format", "docx", "--out", str(tmp_path / "d"))[0] == 0
    with zipfile.ZipFile(tmp_path / "d.docx") as archive:
        names = set(archive.namelist())
        styles = archive.read("word/styles.xml").decode()
        body = archive.read("word/document.xml").decode()
        header = archive.read("word/header1.xml").decode()
        types = archive.read("[Content_Types].xml").decode()
        assert archive.read("word/media/logo.png") == make_png(240, 80)
    assert {"word/header1.xml", "word/footer1.xml", "word/media/logo.png"} <= names
    assert 'w:ascii="Georgia"' in styles and 'w:color w:val="0B3D2E"' in styles
    assert 'w:color="7A2E0B"' in styles
    assert '<w:pgSz w:w="12240" w:h="15840"/>' in body and 'r:embed="rIdLogo"' in body
    assert '<w:pStyle w:val="Title"/>' in body and "Pantry &lt;Co&gt;" in body
    assert "Internal &amp; draft" in header and 'Extension="png"' in types


def test_an_svg_logo_is_in_the_html_but_not_in_word(
    run: Runner, project: Path, tmp_path: Path
) -> None:
    (project.parent / "logo.svg").write_text(SAFE_SVG, encoding="utf-8")
    append(project, '[document]\nlogo = "logo.svg"\n')
    run("premium", "on")
    run("document", "--format", "html", "--out", str(tmp_path / "d"))
    run("document", "--format", "docx", "--out", str(tmp_path / "d"))
    assert "data:image/svg+xml;base64," in (tmp_path / "d.html").read_text(encoding="utf-8")
    with zipfile.ZipFile(tmp_path / "d.docx") as archive:
        assert not any(name.startswith("word/media/") for name in archive.namelist())
        assert "w:drawing" not in archive.read("word/document.xml").decode()


def test_markdown_takes_the_title_format(run: Runner, project: Path, tmp_path: Path) -> None:
    append(project, '[document]\ntitle_format = "{title}, {date}"\n')
    run("premium", "on")
    run("document", "--kind", "digest", "--format", "md", "--out", str(tmp_path / "d"))
    assert (
        (tmp_path / "d.md")
        .read_text(encoding="utf-8")
        .startswith("# Example Pantry Co. register digest, 2026")
    )


def test_a_refused_logo_writes_nothing(run: Runner, project: Path, tmp_path: Path) -> None:
    (project.parent / "logo.svg").write_text("<svg><script/></svg>", encoding="utf-8")
    append(project, '[document]\nlogo = "logo.svg"\n')
    run("premium", "on")
    code, _out, err = run("document", "--out", str(tmp_path / "d"))
    assert code == 2 and "<script> element" in err and not (tmp_path / "d.html").exists()


def test_generate_opens_with_a_labelled_summary(run: Runner, project: Path, tmp_path: Path) -> None:
    run("premium", "on")
    code, _out, err = run("document", "--generate", "--out", str(tmp_path / "d"))
    assert code == 2 and "regwatch llm on" in err
    run("llm", "on")
    run.fake.environ["REGWATCH_KEY_ANTHROPIC"] = KEY
    poster = FakePoster(
        [
            {
                "section": "opening",
                "text": "Three dates are close.",
                "cites": ["event:2026-10-01-1"],
            },
            {"section": "impacts", "text": "Invented.", "cites": ["impact:none/none"]},
        ]
    )
    code, _out, err = run(
        "document", "--generate", "--format", "html", "--out", str(tmp_path / "d"), poster=poster
    )
    assert code == 0 and "impact:none/none" in err
    page = (tmp_path / "d.html").read_text(encoding="utf-8")
    summary = page.index("<h2>Summary</h2>")
    assert summary < page.index("<h2>Scope</h2>")
    assert '<span class="tag">Generated</span>Three dates are close.' in page
    assert "event:2026-10-01-1: 2026-10-01, sv: Nutrition Claims Regulation" in page
    assert "Invented." not in page
    prompt = json.dumps(poster.payloads[0])
    assert "a regulatory briefing" in prompt and KEY not in prompt


def test_the_plan_and_the_formats_refuse_unknown_values(project: Path) -> None:
    config = load_config(project)
    with pytest.raises(WorkspaceError, match="kind"):
        document_plan(config, TODAY, "memo")
    with pytest.raises(WorkspaceError, match="tier"):
        document_plan(config, TODAY, "briefing", "v9")
    doc, facts = document_plan(config, TODAY, "report")
    assert doc.title == "Example Pantry Co. change and due alert"
    assert any(f.fact_id.startswith("change:") for f in facts)
    with pytest.raises(WorkspaceError, match="format"):
        document_bytes(config, doc, "pdf")
    assert with_summary(doc, GenerationResult()) is doc and doc.sections[0].heading != "Summary"


def test_the_renderers_escape_hostile_text() -> None:
    hostile = "<script>x</script>"
    doc = Document(
        hostile,
        "2026-10-19",
        sections=[Section(hostile, paragraphs=[hostile], generated=[GeneratedPassage(hostile)])],
    )
    page = render_document_html(doc, DocumentDesign(header=hostile, footer=hostile))
    assert "<script>" not in page and page.count("&lt;script&gt;") >= 6
    body = docx_bytes(doc, DocumentDesign(header=hostile))
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        for name in archive.namelist():
            ET.fromstring(archive.read(name))
    assert 'w:ascii="Arial"' in render_styles_xml()
