"""Child environment and terminfo installation for the embedded terminal."""

from __future__ import annotations

import os
import shutil
import subprocess
from importlib import resources
from pathlib import Path
from typing import Mapping

from .. import __version__

TERMINFO_NAME = "retrotui"
TERMINFO_FALLBACK = "ansi"
TERM_PROGRAM = "RetroTUI"
_TERMINFO_RESOURCE = ("terminfo", "retrotui.src")
_SYSTEM_TERMINFO_DIRS = (
    Path("/etc/terminfo"),
    Path("/lib/terminfo"),
    Path("/usr/share/terminfo"),
    Path("/usr/lib/terminfo"),
    Path("/usr/local/share/terminfo"),
)


class TerminfoInstallError(RuntimeError):
    """Raised when the bundled terminfo profile cannot be installed."""


def default_terminfo_dir(home: str | os.PathLike[str] | None = None) -> Path:
    """Return the user-local ncurses terminfo directory."""
    root = Path(home).expanduser() if home is not None else Path.home()
    return root / ".terminfo"


def _split_terminfo_dirs(value: str) -> list[Path]:
    """Decode a colon-separated TERMINFO_DIRS value, ignoring empty entries."""
    return [Path(item).expanduser() for item in value.split(os.pathsep) if item]


def candidate_terminfo_dirs(
    env: Mapping[str, str] | None = None,
    *,
    home: str | os.PathLike[str] | None = None,
) -> tuple[Path, ...]:
    """Return terminfo roots in the order RetroTUI should inspect them."""
    source = os.environ if env is None else env
    candidates: list[Path] = []

    explicit = source.get("TERMINFO")
    if explicit:
        candidates.append(Path(explicit).expanduser())

    candidates.extend(_split_terminfo_dirs(source.get("TERMINFO_DIRS", "")))
    candidates.append(default_terminfo_dir(home))

    xdg_data_home = source.get("XDG_DATA_HOME")
    if xdg_data_home:
        candidates.append(Path(xdg_data_home).expanduser() / "terminfo")

    candidates.extend(_SYSTEM_TERMINFO_DIRS)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(os.fspath(candidate)))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return tuple(unique)


def _compiled_entry_candidates(root: Path, name: str) -> tuple[Path, Path]:
    first = name[0]
    return root / first / name, root / f"{ord(first):x}" / name


def terminfo_is_installed(
    name: str = TERMINFO_NAME,
    *,
    env: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
) -> bool:
    """Return whether a compiled terminfo entry is visible in known roots."""
    if not name:
        return False
    for root in candidate_terminfo_dirs(env, home=home):
        if any(path.is_file() for path in _compiled_entry_candidates(root, name)):
            return True
    return False


def resolve_child_term(
    *,
    env: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
) -> str:
    """Choose the advertised TERM without promising unsupported capabilities."""
    source = os.environ if env is None else env
    explicit = source.get("RETROTUI_CHILD_TERM")
    if explicit:
        return explicit
    if terminfo_is_installed(env=source, home=home):
        return TERMINFO_NAME
    return TERMINFO_FALLBACK


def build_child_environment(
    overrides: Mapping[str, object] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    home: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    """Build the explicit environment overlay passed to TerminalSession.

    ``TerminalSession`` already copies the host environment before applying this
    mapping. RetroTUI therefore returns only the values it owns. ``COLORTERM`` is
    intentionally blank until the renderer implements and certifies true color.
    """
    child_env = {
        "TERM": resolve_child_term(env=env, home=home),
        "TERM_PROGRAM": TERM_PROGRAM,
        "TERM_PROGRAM_VERSION": __version__,
        "COLORTERM": "",
        "RETROTUI_EMBEDDED_TERMINAL": "1",
    }
    if overrides:
        child_env.update({str(key): str(value) for key, value in overrides.items()})
    return child_env


def terminfo_source_text() -> str:
    """Return the bundled terminfo source for diagnostics and tests."""
    resource = resources.files("retrotui").joinpath(*_TERMINFO_RESOURCE)
    return resource.read_text(encoding="utf-8")


def install_terminfo(
    output_dir: str | os.PathLike[str] | None = None,
    *,
    tic_path: str | None = None,
) -> Path:
    """Compile the bundled terminfo source into a user-visible database."""
    compiler = tic_path or shutil.which("tic")
    if not compiler:
        raise TerminfoInstallError(
            "Could not find 'tic'. Install the ncurses terminfo compiler first."
        )

    target = (
        Path(output_dir).expanduser()
        if output_dir is not None
        else default_terminfo_dir()
    )
    try:
        target.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TerminfoInstallError(f"Cannot create terminfo directory: {target}") from exc

    resource = resources.files("retrotui").joinpath(*_TERMINFO_RESOURCE)
    try:
        with resources.as_file(resource) as source_path:
            completed = subprocess.run(
                [compiler, "-x", "-o", os.fspath(target), os.fspath(source_path)],
                check=False,
                capture_output=True,
                text=True,
            )
    except OSError as exc:
        raise TerminfoInstallError(f"Failed to execute {compiler!r}: {exc}") from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "unknown tic error").strip()
        raise TerminfoInstallError(f"tic failed: {detail}")

    probe_env = {"TERMINFO": os.fspath(target)}
    if not terminfo_is_installed(env=probe_env, home=target.parent):
        raise TerminfoInstallError(
            f"tic completed but the {TERMINFO_NAME!r} entry was not found in {target}"
        )
    return target
