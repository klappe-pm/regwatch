"""API keys for the sources that need one, kept in the operating system keychain.

On macOS a key is a generic password in the login keychain, read and written with
the ``security`` command under the service ``regwatch`` and an account named by the
source's ``key_env``. On Linux it is a Secret Service item, written with
``secret-tool`` under the attributes ``service regwatch`` and ``account <key_env>``.
An environment variable named by ``key_env`` overrides the keychain, so a scheduled
job or a container can supply a key without one.

A key never appears on a command line, where other users of the machine could see
it in the process list. ``secret-tool store`` reads the secret from standard input.
``security add-generic-password`` only takes the secret as an argument or from a
terminal prompt, so regwatch runs ``security -i``, its documented interactive
mode, and writes the one ``add-generic-password`` command, with the key in it, to
the program's standard input. Reading a key back prints it on the program's
standard output, which regwatch reads and never shows. No message, exception or
log line written here holds a key.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

from regwatch.system import CommandResult, System

__all__ = [
    "KEY_ENV_RE",
    "KEY_ENV_RULE",
    "MAX_KEY_LENGTH",
    "SECURITY_LINE_BYTES",
    "SERVICE",
    "KeyStatus",
    "KeyStore",
    "KeyStoreError",
    "check_key",
    "shared_key_errors",
]

SERVICE = "regwatch"
MAX_KEY_LENGTH = 4096
# A key variable must be in regwatch's own namespace, so a source cannot name an
# unrelated variable (a cloud credential, a deploy token) and have its value sent.
KEY_ENV_RE = re.compile(r"^REGWATCH_KEY_[A-Z0-9_]{1,51}$")
KEY_ENV_RULE = "REGWATCH_KEY_ followed by 1 to 51 upper case letters, digits and underscores"
# Quotes and the backslash would need escaping inside the `security -i` command line.
_REFUSED = frozenset("\"'\\")
# security(1) reads each interactive line with fgets into a 4096 byte buffer, so a
# line of more than 4095 bytes, its line feed included, is split and its tail is
# read as a second command. The whole line must fit.
SECURITY_LINE_BYTES = 4095


def _security_command(key_env: str, value: str) -> str:
    """The one line written to ``security -i`` to store ``value``, line feed included."""
    return (
        f'add-generic-password -U -s {SERVICE} -a {key_env} -l "{SERVICE} {key_env}" -w "{value}"\n'
    )


class KeyStoreError(Exception):
    """A key could not be stored, read or removed. The message never holds the key."""


def _host(url: str) -> str:
    """The lower case host and port of ``url``, as the key would be sent to it."""
    try:
        parts = urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return url.strip().lower()
    host = (parts.hostname or "").lower()
    return f"{host}:{port}" if port is not None else host


def shared_key_errors(sources: Iterable[tuple[str, str, str]]) -> list[str]:
    """Messages for key variables that sources at different hosts share.

    ``sources`` holds ``(source_id, key_env, url)`` for every keyed source. One key
    variable names one key, and a key is meant for one service, so two sources that
    name the same variable must send it to the same host and port. Otherwise a
    source could borrow a key the user stored for another service.
    """
    hosts: dict[str, dict[str, str]] = {}
    for source_id, key_env, url in sources:
        if key_env:
            hosts.setdefault(key_env, {}).setdefault(_host(url), source_id)
    return [
        f"the key variable {key_env} is shared by sources at different hosts "
        f"({', '.join(sorted(by_host.values()))}); each key variable may serve one host"
        for key_env, by_host in sorted(hosts.items())
        if len(by_host) > 1
    ]


@dataclass(frozen=True)
class KeyStatus:
    """Where a key for one ``key_env`` comes from: environment, keychain or nowhere."""

    key_env: str
    source: str

    @property
    def present(self) -> bool:
        """True when a key is available."""
        return self.source in ("environment", "keychain")


def check_key(value: str) -> str:
    """Return ``value`` if it can be a key, or raise KeyStoreError saying why, without it.

    A key is 1 to 4096 printable ASCII characters with no space, quote or
    backslash, which covers the keys API providers issue and keeps a key from
    breaking a request header or the keychain command.
    """
    if not value:
        raise KeyStoreError("the key is empty")
    if len(value) > MAX_KEY_LENGTH:
        raise KeyStoreError(f"the key is longer than {MAX_KEY_LENGTH} characters")
    if any(not 0x21 <= ord(ch) <= 0x7E or ch in _REFUSED for ch in value):
        raise KeyStoreError(
            "the key may hold only printable ASCII characters without spaces, quotes or backslashes"
        )
    return value


class KeyStore:
    """Store, read and remove keys through the system keychain of ``system``."""

    def __init__(self, system: System | None = None) -> None:
        self.system = system or System()

    # --- which tool -----------------------------------------------------------

    @property
    def backend(self) -> str | None:
        """``macos``, ``linux`` or None when this machine has no supported keychain tool."""
        if self.system.is_macos and self._tool("security"):
            return "macos"
        if self.system.is_linux and self._tool("secret-tool"):
            return "linux"
        return None

    @property
    def backend_label(self) -> str:
        """Where keys are kept, in words."""
        return {
            "macos": "the macOS login keychain",
            "linux": "the Secret Service keyring",
        }.get(self.backend or "", "no keychain")

    def _tool(self, name: str) -> str | None:
        return self.system.which(name)

    def _require(self, key_env: str) -> str:
        backend = self.backend
        if backend is None:
            raise KeyStoreError(
                "no keychain tool was found (security on macOS, secret-tool from libsecret "
                f"on Linux); set the environment variable {key_env} to supply the key instead"
            )
        return backend

    @staticmethod
    def _check_env(key_env: str) -> str:
        if not KEY_ENV_RE.fullmatch(key_env):
            raise KeyStoreError(f"'{key_env}' is not a key variable name: {KEY_ENV_RULE}")
        return key_env

    def _run(self, args: list[str], stdin: str | None = None) -> CommandResult:
        return self.system.runner(args, stdin)

    # --- operations -------------------------------------------------------------

    def set(self, key_env: str, value: str) -> None:
        """Store ``value`` as the key for ``key_env``, replacing any key stored before.

        The key is read back and compared, so a store that silently failed is reported.
        """
        self._check_env(key_env)
        check_key(value)
        backend = self._require(key_env)
        if backend == "macos":
            command = _security_command(key_env, value)
            if len(command.encode("utf-8")) > SECURITY_LINE_BYTES:
                room = SECURITY_LINE_BYTES - len(_security_command(key_env, "").encode("utf-8"))
                raise KeyStoreError(
                    f"the key is too long for the macOS keychain command: with the name "
                    f"{key_env} it may be at most {room} characters; set the environment "
                    f"variable {key_env} to supply it instead"
                )
            result = self._run([str(self._tool("security")), "-i"], command)
            tool = "security"
        else:
            result = self._run(
                [
                    str(self._tool("secret-tool")),
                    "store",
                    "--label",
                    f"{SERVICE} {key_env}",
                    "service",
                    SERVICE,
                    "account",
                    key_env,
                ],
                value,
            )
            tool = "secret-tool"
        if result.returncode != 0:
            raise KeyStoreError(
                f"{tool} could not store the key for {key_env} (status {result.returncode})"
            )
        if self.stored(key_env) != value:
            raise KeyStoreError(f"{tool} did not keep the key for {key_env}; nothing was stored")

    def stored(self, key_env: str) -> str | None:
        """The key in the keychain for ``key_env``, ignoring the environment; None when absent."""
        self._check_env(key_env)
        backend = self.backend
        if backend is None:
            return None
        if backend == "macos":
            args = [
                str(self._tool("security")),
                "find-generic-password",
                "-s",
                SERVICE,
                "-a",
                key_env,
                "-w",
            ]
        else:
            args = [
                str(self._tool("secret-tool")),
                "lookup",
                "service",
                SERVICE,
                "account",
                key_env,
            ]
        result = self._run(args)
        if result.returncode != 0:
            return None
        value = result.stdout.rstrip("\r\n")
        return value or None

    def get(self, key_env: str) -> str | None:
        """The key for ``key_env``: the environment variable first, then the keychain."""
        self._check_env(key_env)
        from_env = self.system.environ.get(key_env, "")
        if from_env:
            return from_env
        return self.stored(key_env)

    def status(self, key_env: str) -> KeyStatus:
        """Where the key for ``key_env`` would come from. The key itself is not returned."""
        self._check_env(key_env)
        if self.system.environ.get(key_env, ""):
            return KeyStatus(key_env, "environment")
        if self.backend is None:
            return KeyStatus(key_env, "unavailable")
        return KeyStatus(key_env, "keychain" if self.stored(key_env) else "missing")

    def delete(self, key_env: str) -> bool:
        """Remove the stored key for ``key_env``. True when one was removed."""
        self._check_env(key_env)
        backend = self._require(key_env)
        if self.stored(key_env) is None:
            return False
        if backend == "macos":
            args = [
                str(self._tool("security")),
                "delete-generic-password",
                "-s",
                SERVICE,
                "-a",
                key_env,
            ]
            tool = "security"
        else:
            args = [
                str(self._tool("secret-tool")),
                "clear",
                "service",
                SERVICE,
                "account",
                key_env,
            ]
            tool = "secret-tool"
        result = self._run(args)
        if result.returncode != 0 or self.stored(key_env) is not None:
            raise KeyStoreError(
                f"{tool} could not remove the key for {key_env} (status {result.returncode})"
            )
        return True
