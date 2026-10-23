"""The built web app ships in the package, has every page, and loads nothing from elsewhere.

The pages are built from web/ with scripts/build-web.sh and committed under
regwatch/web/, so a pip install needs no Node. Comparing the folder with a fresh
build would need Node in the test run, so these tests check what the folder must
hold instead: an index page, one page per section, and no reference that would
make a browser load anything from another origin.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from conftest import ROOT

WEB = Path(str(resources.files("regwatch").joinpath("web")))
PAGES = (
    "changes",
    "sources",
    "obligations",
    "briefings",
    "newsletters",
    "documents",
    "automations",
    "keys",
    "settings",
)
URL = re.compile(r"https?://[^\s\"'`\\)<>{}\[\]]*")
# Strings in the bundled libraries that name a URL without loading it: XML namespace
# names that the DOM needs, and documentation links inside error messages and licences.
NAMESPACES = {
    "http://www.w3.org/1998/Math/MathML",
    "http://www.w3.org/1999/xlink",
    "http://www.w3.org/2000/svg",
    "http://www.w3.org/XML/1998/namespace",
}
MESSAGE_PREFIXES = (
    "https://react.dev/errors/",
    "https://nextjs.org/docs/",
    "https://github.com/zloirock/core-js",
    "https://tailwindcss.com",
)


def built_files() -> list[Path]:
    return sorted(p for p in WEB.rglob("*") if p.is_file())


def test_the_build_exists_with_every_page() -> None:
    assert (WEB / "index.html").is_file()
    assert (WEB / "404.html").is_file()
    for page in PAGES:
        assert (WEB / page / "index.html").is_file(), page


def test_the_build_holds_no_link_or_hidden_file() -> None:
    for path in WEB.rglob("*"):
        assert not path.is_symlink(), path
        assert not path.name.startswith("."), path


def allowed(url: str) -> bool:
    if url in NAMESPACES or url.startswith(MESSAGE_PREFIXES):
        return True
    # A one-label host such as http://n is a base for parsing relative addresses
    # or a polyfill's self-test; it cannot name a server on the internet.
    host = urlsplit(url).hostname or ""
    return "." not in host


def test_no_built_file_refers_to_another_origin() -> None:
    found = {
        url: path.relative_to(WEB).as_posix()
        for path in built_files()
        for url in URL.findall(path.read_bytes().decode("utf-8", errors="replace"))
    }
    assert found, "the scan found nothing at all, so it is not reading the files"
    remote = {url: where for url, where in found.items() if not allowed(url)}
    assert remote == {}


@pytest.mark.parametrize("url", ["https://cdn.example.com/x.js", "http://fonts.example/f.woff2"])
def test_the_scan_refuses_a_real_remote_address(url: str) -> None:
    assert not allowed(url)


def test_no_page_or_stylesheet_loads_from_another_origin() -> None:
    for path in built_files():
        text = path.read_bytes().decode("utf-8", errors="replace")
        if path.suffix == ".html":
            assert not re.search(
                r"""(?:src|href|action|poster)\s*=\s*["']?\s*(?:https?:)?//""", text
            ), path
        if path.suffix == ".css":
            assert not re.search(r"""(?:url\(|@import)\s*["']?\s*(?:https?:)?//""", text), path


@pytest.mark.repo_only
def test_the_wheel_and_the_sdist_carry_the_build() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"regwatch/web/**"' in pyproject
    assert '"/regwatch",' in pyproject
    assert (ROOT / "scripts" / "build-web.sh").is_file()
    assert (ROOT / "web" / "package-lock.json").is_file()


@pytest.mark.repo_only
def test_every_web_dependency_is_pinned_exactly() -> None:
    import json

    package = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    for group in ("dependencies", "devDependencies"):
        for name, version in package[group].items():
            assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"{name} {version}"
    for parent, pins in package.get("overrides", {}).items():
        for name, version in pins.items():
            assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"{parent} > {name} {version}"
    lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))
    packages = lock["packages"]
    for name, entry in packages.items():
        if not name:
            continue
        if entry.get("inBundle"):
            # A bundled package ships inside its parent's tarball, so the parent's
            # hash covers it and it has none of its own.
            parent = name.rpartition("/node_modules/")[0]
            assert packages[parent]["integrity"].startswith("sha512-"), name
            continue
        assert entry.get("integrity", "").startswith("sha512-"), name


# The first release of each package that is clear of the advisories `npm audit` reported:
# GHSA-2464-fhr4-w9xw and GHSA-p3m5-59mp-jv5r for next, and GHSA-qx2v-qp2m-jg93,
# GHSA-6g55-p6wh-862q, GHSA-fxqj-rqcc-2cmp and GHSA-r28c-9q8g-f849 for postcss.
FIXED_IN = {"next": (15, 5, 28), "postcss": (8, 5, 23)}


@pytest.mark.repo_only
def test_no_locked_package_is_older_than_its_security_fix() -> None:
    """Every copy in the lockfile, nested ones included, is at or past its fixed release."""
    import json

    lock = json.loads((ROOT / "web" / "package-lock.json").read_text(encoding="utf-8"))
    seen: dict[str, list[str]] = {}
    for path, entry in lock["packages"].items():
        name = path.rpartition("node_modules/")[2]
        if name in FIXED_IN:
            version = tuple(int(part) for part in entry["version"].split("."))
            seen.setdefault(name, []).append(path)
            assert version >= FIXED_IN[name], f"{path} {entry['version']}"
    assert set(seen) == set(FIXED_IN), seen
    assert "node_modules/next/node_modules/postcss" in seen["postcss"]
