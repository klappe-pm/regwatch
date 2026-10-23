"""Change one setting in ``regwatch.toml`` without disturbing the rest of the file.

The configuration file is the user's, so an edit keeps every comment, every other
setting and the order of the file. The edit replaces one ``key = value`` line in
one table, or adds it, and is then checked: the new text is parsed and must equal
the old settings with exactly that one value changed. A file written in a form
this module cannot edit safely (a dotted key, an inline table, an unusual layout)
is left alone with an error that says which setting to change by hand. The file
is written through ``regwatch.state.safe_write_text``, like every other write.
"""

from __future__ import annotations

import copy
import json
import re
import tomllib
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from regwatch.config import FOCUS_ID_RE, LLM_PROVIDERS, MODEL_RE, load_config
from regwatch.state import safe_write_text

__all__ = [
    "SettingsError",
    "edit_setting",
    "set_focus_areas",
    "set_llm",
    "set_premium",
    "set_setting",
]

SettingValue = bool | int | str | list[str]
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


class SettingsError(ValueError):
    """The setting could not be changed. The configuration file was left as it was."""


def _literal(value: SettingValue) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        # A JSON string is a valid TOML basic string, with ASCII escapes for the rest.
        return json.dumps(value)
    # JSON strings are valid TOML basic strings: both escape quotes, backslashes and controls.
    return "[" + ", ".join(json.dumps(item) for item in value) + "]"


def _header(line: str) -> str | None:
    """The table name a ``[name]`` header line opens, or None for any other line."""
    match = re.match(r"^\s*\[\s*([A-Za-z0-9_.-]+)\s*\]\s*(?:#.*)?$", line)
    return match.group(1) if match else None


def _value_end(lines: list[str], start: int) -> int:
    """The index of the last line of the value that begins on ``lines[start]``."""
    depth = 0
    for index in range(start, len(lines)):
        text = lines[index].split("=", 1)[1] if index == start else lines[index]
        # Strings and comments may hold brackets that do not count.
        text = re.sub(r'"(?:[^"\\]|\\.)*"|\'[^\']*\'', '""', text).split("#", 1)[0]
        depth += text.count("[") - text.count("]")
        if depth <= 0:
            return index
    return len(lines) - 1


def edit_setting(text: str, table: str, key: str, value: SettingValue) -> str:
    """Return ``text`` with ``[table] key`` set to ``value``.

    Raises SettingsError when the result would differ from the original in any
    other way, or when the original is not valid TOML.
    """
    if not (_NAME_RE.fullmatch(table) and _NAME_RE.fullmatch(key)):
        raise SettingsError("a setting name may hold only lowercase letters, digits and _")
    try:
        before = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise SettingsError(f"the configuration file is not valid TOML: {exc}") from exc
    line = f"{key} = {_literal(value)}"
    lines = text.splitlines()
    start = next((i for i, item in enumerate(lines) if _header(item) == table), None)
    if start is None:
        body = text if not text or text.endswith("\n") else text + "\n"
        edited = f"{body}\n[{table}]\n{line}\n"
    else:
        end = next(
            (i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")),
            len(lines),
        )
        found = next(
            (i for i in range(start + 1, end) if re.match(rf"^\s*{key}\s*=", lines[i])), None
        )
        if found is None:
            last = max((i for i in range(start, end) if lines[i].strip()), default=start)
            lines.insert(last + 1, line)
        else:
            lines[found : _value_end(lines, found) + 1] = [line]
        edited = "\n".join(lines) + "\n"
    expected = copy.deepcopy(before)
    section = expected.setdefault(table, {})
    if not isinstance(section, dict):
        raise SettingsError(f"[{table}] is not a table; change {key} by hand")
    section[key] = value
    try:
        after: dict[str, Any] = tomllib.loads(edited)
    except tomllib.TOMLDecodeError:
        after = {}
    if after != expected:
        raise SettingsError(
            f"the configuration file is written in a form regwatch cannot edit safely; "
            f"set [{table}] {key} by hand"
        )
    return edited


def set_setting(config_path: Path, table: str, key: str, value: SettingValue) -> None:
    """Set ``[table] key`` in the configuration file at ``config_path``.

    The file is read and validated as ``load_config`` reads it, edited, validated
    again in memory, and written atomically. The register files stay protected.
    """
    config = load_config(config_path)
    edited = edit_setting(config_path.read_text(encoding="utf-8"), table, key, value)
    safe_write_text(config_path, edited, config.register.all_paths())


def set_premium(config_path: Path, enabled: bool) -> None:
    """Turn the premium features on or off: ``[premium] enabled``."""
    set_setting(config_path, "premium", "enabled", enabled)


def set_focus_areas(config_path: Path, focus_areas: Iterable[str], known: Iterable[str]) -> None:
    """Set ``[profile] focus_areas`` to ids that are in ``known``, in the order given."""
    allowed = set(known)
    chosen = list(dict.fromkeys(focus_areas))
    bad = [area for area in chosen if not FOCUS_ID_RE.fullmatch(area) or area not in allowed]
    if bad:
        raise SettingsError("unknown focus areas: " + ", ".join(sorted(bad))[:200])
    set_setting(config_path, "profile", "focus_areas", chosen)


def set_llm(
    config_path: Path,
    *,
    enabled: bool | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> None:
    """Change ``[llm] enabled``, ``provider`` and ``model``; each one left as None is kept.

    A provider must be one regwatch knows and a model a plain model name (empty means
    the provider's default). Each setting is changed and checked on its own.
    """
    if provider is not None and provider not in LLM_PROVIDERS:
        raise SettingsError(f"the provider must be one of {', '.join(LLM_PROVIDERS)}")
    if model is not None and model and not MODEL_RE.fullmatch(model):
        raise SettingsError(
            "a model name holds letters, digits and . _ : / - only, at most 100 characters"
        )
    if provider is not None:
        set_setting(config_path, "llm", "provider", provider)
    if model is not None:
        set_setting(config_path, "llm", "model", model)
    if enabled is not None:
        set_setting(config_path, "llm", "enabled", enabled)
