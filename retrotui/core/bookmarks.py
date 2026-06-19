"""Persistent bookmark storage for RetroNet Explorer Ultra.

Bookmarks are stored in ``~/.config/retrotui/bookmarks.toml`` using a flat
schema where each section name is the bookmark title and ``url`` is the only
field. The format stays compatible with the project's existing toml fallback
parser (no array-of-tables) so it works on Python 3.10+.

Example file::

    # RetroTUI bookmarks

    ["NPR"]
    url = "http://text.npr.org"

    ["DuckDuckGo"]
    url = "https://duckduckgo.com/html/"
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import _decode_basic_string, _parse_toml


@dataclass(frozen=True)
class Bookmark:
    """A named URL the user wants to revisit from RetroNet."""

    title: str
    url: str


def default_bookmarks_path() -> Path:
    """Return default bookmarks path (``~/.config/retrotui/bookmarks.toml``)."""
    return Path.home() / ".config" / "retrotui" / "bookmarks.toml"


_BOOKMARK_SECTION_ERRORS = (AttributeError, TypeError, ValueError)


def _strip_section_quotes(name: str) -> str:
    """TOML section names may be quoted if they contain spaces or dots."""
    name = name.strip()
    if len(name) >= 2 and name[0] == name[-1] == '"':
        return _decode_basic_string(name[1:-1])
    if len(name) >= 2 and name[0] == name[-1] == "'":
        return name[1:-1]
    return name


def _toml_basic_string(value: str) -> str:
    """Return a TOML basic string body for values RetroTUI persists."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace('"', '\\"')
    )


def load_bookmarks(path: str | Path | None = None) -> list[Bookmark]:
    """Return the persisted bookmarks. Empty list if the file is missing."""
    cfg_path = Path(path) if path is not None else default_bookmarks_path()
    try:
        text = cfg_path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        raw = _parse_toml(text)
    except _BOOKMARK_SECTION_ERRORS:
        return []
    out: list[Bookmark] = []
    for raw_title, body in raw.items():
        if not isinstance(body, dict):
            continue
        url = body.get("url")
        if not isinstance(url, str) or not url.strip():
            continue
        out.append(
            Bookmark(
                title=_strip_section_quotes(str(raw_title)),
                url=url.strip(),
            )
        )
    return out


def save_bookmarks(
    bookmarks: list[Bookmark], path: str | Path | None = None
) -> Path:
    """Persist the bookmark list. Returns the path written to."""
    cfg_path = Path(path) if path is not None else default_bookmarks_path()
    lines = ["# RetroTUI bookmarks for RetroNet Explorer Ultra", ""]
    for bm in bookmarks:
        title = _toml_basic_string(bm.title or "Untitled")
        url = _toml_basic_string(bm.url or "")
        lines.append(f'["{title}"]')
        lines.append(f'url = "{url}"')
        lines.append("")
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return cfg_path


def add_bookmark(
    title: str, url: str, path: str | Path | None = None
) -> list[Bookmark]:
    """Add a bookmark (or replace one with the same title). Returns updated list."""
    clean_title = (title or "").strip() or "Untitled"
    clean_url = (url or "").strip()
    bookmarks = [bm for bm in load_bookmarks(path) if bm.title != clean_title]
    if clean_url:
        bookmarks.append(Bookmark(title=clean_title, url=clean_url))
    save_bookmarks(bookmarks, path)
    return bookmarks


def remove_bookmark(title: str, path: str | Path | None = None) -> list[Bookmark]:
    """Remove a bookmark by title. Returns updated list."""
    bookmarks = [bm for bm in load_bookmarks(path) if bm.title != title]
    save_bookmarks(bookmarks, path)
    return bookmarks
