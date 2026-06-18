# RetroTUI — Improvement Plan

Analysis of every app and bundled plugin. Issues are categorized by severity and grouped by cross-cutting pattern when applicable.

**Status:** v0.9.4 hardening closed. v0.9.5 (Terminal 2D buffer) in progress: `TerminalScreenBuffer` and `TerminalScreen` classes landed in `core/terminal_session.py` with 22 unit tests; the buffer has not yet been wired into `TerminalWindow`. The post-hardening cleanup pass closed the last per-app MED/LOW items and removed an orphan module — see `ROADMAP.md` for the next milestones (v0.9.6 cross-terminal certification, v0.9.7 session restore).

**Last reviewed:** 2026-06-19.

## Resolved in current hardening pass

- Terminal: PTY start/read/resize moved out of `draw()` into `tick()`, resize is cached by terminal body size, session errors remain visible without duplicate spam, tabs now use 8-column stops, CSI `H`/`f` clamps row/column in alternate screen mode, CSI `J` handles partial erase modes, alternate-screen text wraps at the right edge, PageUp/PageDown forward to full-screen programs, F1-F12 input sequences are mapped when available, and interrupt fallback writes `Ctrl+C` through one explicit path.
- File Manager: file creation now uses `Path.touch()`, directory copy targets are no longer duplicated, dual-pane copy/move preserves operation errors, keyboard routing uses normalized key codes for navigation/F-keys, preview cache keys use file/directory stat data, image preview backend detection is cached, image preview rendering runs outside the render path, pane scroll clamping uses entry bounds, undoable delete respects the window trash-dir override, undo now returns `ActionResult`, bookmarks persist across sessions, directory drag reports unsupported instead of failing silently, parent (`..`) entries are blocked from destructive operations, rename validates path separators/collisions, `use_unicode` controls entry icons, redundant border assignment was removed, and file sizes format through GB/TB.
- Notepad: wrapped rows now use terminal cell width for CJK/wide characters, wrap viewport state is based on wrapped rows, visible wrap chunks reuse the wrap cache, undo history has a character budget for large files, wrap cache is invalidated on load/undo/redo, window title updates are cached by filepath/modified state, Ctrl+W returns the config update action, and `get_context_menu_items()` now returns the actual context menu instead of a dead stub.
- Base profile: default config now exposes only File Manager/Explorer, Terminal, and Notepad in desktop icons, global menus, plugin menus, and the desktop context menu; secondary apps and plugins remain installed but disabled by default.
- Game logic and platform polling moved out of `draw()`: Snake, Tetris, Process Manager, System Monitor, Hex Viewer, Clipboard Viewer, Image Viewer and WiFi Manager all run their update/poll steps from a new `tick()` hook wired by the event loop. `step()` is preserved for tests but no longer invoked from the renderer.
- Blocking I/O moved to background threads: WiFi Manager scans and connects in worker threads with a `_status_msg` indicator, Image Viewer renders `chafa`/`timg`/`catimg` off the main thread with a `[rendering...]` placeholder, and Hex Viewer warms the file slice cache from `tick()`.
- Thread safety: RetroNet now takes `_lock` for every mutation of `url`, `_back_stack`, `_forward_stack`, `title`, `_search_*` and `content`/`is_loading`; all read paths in `draw` and `handle_click` use the same lock. WiFi Manager and Image Viewer use dedicated locks for their worker state. The previous `_create_unverified_context()` SSL bypass is gone; an opt-in `check_hostname=False` fallback is only used after a `ssl.SSLError`.
- Trash: a new `REQUEST_EMPTY_TRASH_CONFIRM` action type now routes to a dedicated dialog that lists the items being purged. `perform_delete` writes a `.trashinfo` sidecar with the original path and `perform_restore` consumes it to put items back; the trash window exposes the operation through a "Restore" menu entry and the `R` shortcut.
- Bundled plugins (9): the wrapper classes now apply the manifest `title` to the window instead of silently discarding it.
- Input handling: `normalize_key_code` is now used by Minesweeper, Tetris, Solitaire, WiFi Manager and Clipboard Viewer, and the previous `getattr(key, '__int__', None)` duck-type check in Clipboard Viewer was replaced with `isinstance(key, int)` plus `normalize_key_code`.
- Other: Markdown viewer adds `*italic*`, `` `inline code` ``, `[label](url)` link rendering, preserves `in_code_block` across scroll and supports the mouse wheel; Control Panel exposes `word_wrap_default` via a 4-state cycle and lets the user pick a specific theme with Left/Right or by clicking the theme row; Settings applies preferences consistently for all toggles; App Manager `IconsWindow` reuses the base class via `super()` and caches the icon catalog; Process Manager implements `cmd` sort, initializes `scroll_offset`, reads `/proc/meminfo` in a single pass, and no longer kills on double-click; Solitaire blocks foundation-to-column moves and uses a 500 ms double-click window; Tetris restarts through a new `reset_game()` helper and now computes the I-piece rotation center dynamically; Clock caches `TextCalendar` per `(year, month, first-weekday)` and dedupes the `always_on_top` toggle path; System Monitor adds a platform guard and rescales the CPU history when the window is resized; CharMap fixes the `22` / `20` detail-pane width mismatch, wires up the `about_map` action and dedupes the copy helpers; Calculator normalizes `-0` to `0` and trims dead `body_rect` locals; Minesweeper uses a non-error color for the bomb/timer chrome; Settings derives `_controls_count` from a `_TOGGLE_COUNT` constant; Clipboard Viewer `c` key now also clears the system clipboard; Hex Viewer now mixes in `SelectableTextMixin` and stores row spans as `(row, 0)` tuples; Snake `_update_menu_checks` looks up the difficulty name from the action via a class-level `_DIFFICULTY_NAMES` mapping instead of parsing the previous label.

## Resolved in post-hardening cleanup pass

- **Orphan module removed**: `retrotui/core/win_termios.py` (120 lines, no importers since the `try/except` termios import was adopted in `d519870`) has been deleted. `ARCHITECTURE.md` and `ROADMAP.md` no longer list it as a live component.
- **System Monitor read-free render path**: `/proc/uptime` is now read by `_update_stats()` (which already runs from `tick()` on the 1-second refresh interval) and the formatted `self.uptime_str` is read in `draw()`. The render path no longer opens `/proc` files.
- **Markdown Viewer scroll correctness locked in**: two new regression tests confirm `_max_scroll()` is `len(raw_content) - rows_visible()`. The audit entry was stale — each raw line maps to exactly one visible row, so the raw count is the correct rendered line count.
- **IMPROVEMENTS.md per-app tables refreshed**: the sections below now show "No remaining items" for every app that was fully closed in v0.9.4, leaving only RetroNet's HTML regex as a known MED.

## Resolved in v0.9.5 — Terminal 2D buffer

- `retrotui/core/terminal_session.py` ships two new framework-free primitives:
  - `TerminalScreenBuffer` is a `rows x cols` grid of `(char, attr)` cells with a cursor, `put_char`, `carriage_return`, `line_feed`, `backspace`, `scroll_up`/`scroll_down`, `clear_line`, `clear_screen` (ED modes `all` / `below` / `above`), `insert_line` / `delete_line`, and `resize`. The class is intentionally not wired into the curses/PTY stack so it can be unit-tested in isolation.
  - `TerminalScreen` owns a normal-screen and an alt-screen `TerminalScreenBuffer`, swaps the active one via `set_alt_screen`, and resizes both in lockstep so dimensions stay aligned regardless of which mode is active. This unblocks the v0.9.5 item "Mantener alt-screen separado de normal-screen y scrollback".
- 22 new unit tests in `tests/test_terminal_screen_buffer.py` cover all of the above operations, including the ED-mode semantics (columns before the cursor are preserved on `below`, columns after the cursor are preserved on `above`) and the row-preservation guarantees of `resize`.
- The remaining v0.9.5 work is to route the ANSI state machine writes in `TerminalWindow` through `TerminalScreen.put_char` so the buffer is the single source of truth for normal-screen cells and selection.

---

## Cross-Cutting Issues

These patterns appear in multiple files and should be addressed systematically.

### 1. Game logic inside `draw()` — HIGH

Snake, Tetris, and Process Manager all run tick/update logic inside their `draw()` method. This couples game speed to render frame rate and causes side effects during rendering.

| File | Line | Problem |
|---|---|---|
| `snake.py` | 282 | `self.step()` called with `now=None`, forcing a move every frame — **speed system is completely bypassed** |
| `snake.py` | 297-299 | `_save_high_scores()` writes to disk on every frame after game-over (~30 writes/sec) |
| `tetris.py` | 116-125 | Drop interval check inside `draw()` — piece speed depends on frame rate |
| `process_manager.py` | 343 | `refresh_processes(force=False)` reads `/proc` inside `draw()` |
| `hexviewer.py` | 383-391 | `_read_slice()` opens, seeks, reads, closes file on every render frame |
| `sysmon.py` | 130 | Opens `/proc/uptime` on every frame |

**Fix:** Move all update logic to a `tick()` or `update()` method called from the event loop, not the renderer. Cache expensive I/O results and invalidate on explicit triggers.

### 2. Blocking I/O on main thread — HIGH

Several apps perform synchronous I/O that freezes the entire TUI.

| File | Line | Duration | Operation |
|---|---|---|---|
| `wifi_manager.py` | 62 | 1 second | `time.sleep(1)` after wifi rescan |
| `wifi_manager.py` | 193 | 10-30 seconds | `nmcli connect` (synchronous) |
| `image_viewer.py` | 142-151 | up to 3 seconds | `subprocess.run(chafa/timg, timeout=3.0)` |
| `terminal.py` | 398 | variable | `_ensure_session()` (PTY startup) inside `draw()` |

**Fix:** Background threads with loading indicators, similar to `retronet.py`'s `_fetch_thread` pattern (but with proper locking — see #3).

### 3. Thread safety in RetroNet — CRITICAL + HIGH

| File | Line | Problem |
|---|---|---|
| `retronet.py` | 141 | `ssl._create_unverified_context()` — SSL verification disabled globally |
| `retronet.py` | 155, 159-162 | `self.content` written from background thread without lock |
| `retronet.py` | 171 | `self.title` written from background thread without lock |

**Fix:** Use `ssl.create_default_context()` by default. Add `threading.Lock` for all shared state between fetch thread and main thread.

### 4. `normalize_key_code` not used — HIGH

Minesweeper and Tetris bypass the standard key normalization, breaking input when the terminal uses `get_wch()` (which returns strings, not ints).

| File | Line | Problem |
|---|---|---|
| `minesweeper.py` | 316-318 | Uses `getattr(key, '__int__', None) and int(key)` — fragile duck typing |
| `tetris.py` | 178-212 | Compares `key` against `ord('r')` directly — fails for string keys |
| `solitaire.py` | 391 | Inline import of `normalize_key_code` from `core.key_router` on every keypress |

**Fix:** Module-level `from ..utils import normalize_key_code`, call it at the top of each `handle_key`.

### 5. Repeated in-function imports — MEDIUM

| File | Line | Import |
|---|---|---|
| `minesweeper.py` | 215 | `from ..constants import C_ANSI_START` inside `draw()` |
| `solitaire.py` | 163 | `from ..constants import C_ANSI_START` inside `_draw_card()` (called 52x/frame) |
| `solitaire.py` | 391 | `from ..core.key_router import normalize_key_code` inside `handle_key()` |
| `control_panel.py` | 89 | `from ..core.app import APP_VERSION` inside `draw()` |
| `clipboard_viewer.py` | 144-150 | `import curses as _c` inside `handle_key()` |

**Fix:** Move all to module-level imports.

### 6. Plugin wrapper drops `title` — MEDIUM

All 9 bundled plugin `__init__.py` files silently discard the `title` parameter passed by the plugin host.

**Fix:** Pass `title` through to parent or apply it after `super().__init__()`.

---

## Core Apps

### File Manager (`apps/filemanager/`)

| Sev | File | Issue |
|---|---|---|
| INFO | - | No remaining File Manager items tracked from the current audit pass. |

### Notepad (`apps/notepad.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Notepad items tracked from the current audit pass. |

### Terminal (`apps/terminal.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Terminal items tracked from the current audit pass. The v0.9.5 work to wire `TerminalScreenBuffer`/`TerminalScreen` from `core/terminal_session.py` into the ANSI state machine is tracked at the top of this document and in `ROADMAP.md`. |

### Calculator (`apps/calculator.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Calculator items tracked from the current audit pass. `RecursionError` is in `_CALCULATOR_EVAL_ERRORS`; the float renderer normalizes `-0` to `0`; `handle_key` no longer carries unused `bx`/`by` locals. |

### Hex Viewer (`apps/hexviewer.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Hex Viewer items tracked from the current audit pass. Reads are cached and warmed from `tick()`; `_rows_visible` and `draw` agree on the visible row count; `_parse_search_query` catches `ValueError`; the window now mixes in `SelectableTextMixin` and stores row spans as `(row, 0)` tuples. |

### Process Manager (`apps/process_manager.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Process Manager items tracked from the current audit pass. `refresh_processes` runs from `tick()`; double-click no longer kills (kill is a menu/key action only); `/proc/meminfo` is read in a single pass; the `cmd` sort key is fully implemented; column boundaries are `COL_PID_END`/`COL_CPU_END`/`COL_MEM_END` constants; `scroll_offset` is initialized in `__init__`. |

---

## Secondary Apps

### System Monitor (`apps/sysmon.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining System Monitor items tracked from the current audit pass. The platform guard keeps non-Linux hosts from `/proc` I/O; the CPU history deque is resized on viewport change in `_resize_history_to_viewport`; `/proc/uptime` is read by `_update_stats` and the formatted string is cached in `self.uptime_str`; the dead `mem_info['free']` key was removed. |

### Log Viewer (`apps/logviewer.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Log Viewer items tracked from the current audit pass. Severity colors share a single `_log_colors_ready` guard; `_reload_file` reads size from the open handle so there is no TOCTOU window; line endings are normalized via `_normalize_text`; search highlights use `A_BOLD` so they don't fight the severity color pairs; `_append_lines` runs the incremental `_extend_search_matches` to keep search index O(k). |

### Trash (`apps/trash.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Trash items tracked from the current audit pass. The `REQUEST_EMPTY_TRASH_CONFIRM` action routes through a dedicated dialog; per-item errors are collected and reported; `..` is removed via label lookup instead of a hardcoded index; `perform_restore` + the `R` shortcut put items back. |

### Clipboard Viewer (`apps/clipboard_viewer.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Clipboard Viewer items tracked from the current audit pass. `normalize_key_code` is imported at module level and applied in `handle_key`; `curses` is imported once; the clipboard is polled from `tick()` (the event bus catches internal copies); pressing `c` empties both the internal and system clipboard via `pyperclip`. |

### Control Panel (`apps/control_panel.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Control Panel items tracked from the current audit pass. The Desktop pane cycles through the 4 `(show_hidden, word_wrap_default)` combinations so both are reachable from the keyboard; Left/Right selects a specific theme on the Appearance pane; the unused `_theme_scroll` attribute was removed; toggles flow through `apply_preferences` so the Control Panel and `SettingsWindow` stay in sync. |

### Settings (`apps/settings.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Settings items tracked from the current audit pass. Left/Right calls `apply_preferences` consistently for every toggle; `_controls_count` is derived from `_TOGGLE_COUNT`; the misleading `_committed` flag was renamed `_finalized`. |

### Image Viewer (`apps/image_viewer.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Image Viewer items tracked from the current audit pass. `chafa`/`timg`/`catimg` render on a worker thread with a `[rendering...]` placeholder; `status_message` is cleared by the TTL countdown in `tick()`, not in `draw()`; the backend is cached on the first detection; zoom index is computed via `ZOOM_LEVELS.index(100)`; zoom keys are `+`/`-`/`0`, not PageUp/PageDown. |

### Markdown Viewer (`apps/markdown_viewer.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Markdown Viewer items tracked from the current audit pass. The code color pair is built as `C_ANSI_START + 4` so it stays inside the project's reserved range; `in_code_block` is reconstructed from the content above the viewport on every draw; the inline renderer handles `**bold**`, `*italic*`, `` `inline code` `` and `[label](url)`; `_max_scroll` is `len(raw_content) - rows_visible()` (each raw line maps to exactly one visible row, locked in by regression tests); the `handle_scroll` hook gives the mouse wheel the same behavior as every other viewer. |

### RetroNet (`apps/retronet.py`)

| Sev | Issue |
|---|---|
| MED | HTML regex parsing (224): nested or malformed tags are flattened into best-effort text. Replacing the regex pre-processor with a small HTML parser (e.g. `html.parser.HTMLParser`) is the right next step but not blocking v0.9.5. |

The previously listed CRIT (SSL bypass), HIGH (background-thread writes without a lock, `self.h - 6` scroll bound) and MED (overly broad `_RETRONET_FETCH_ERRORS` and history dedup) items are all closed: `create_default_context` is used with a documented `check_hostname=False` opt-in, the fetch thread takes `_lock` for every shared mutation, the scroll bound now uses `body_rect()`, the fetch-error tuple is restricted to `URLError`/`socket.timeout`/`OSError`/`UnicodeDecodeError`/`ssl.SSLError`/`HTTPException`/`ConnectionError`, and `_load_url` deduplicates the previous entry before pushing onto `_back_stack`.

### App Manager (`apps/app_manager.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining App Manager items tracked from the current audit pass. `IconsWindow` extends `DesktopIconManagerWindow` (which itself extends the new `_BaseSelectionEditorWindow`), `draw` delegates to `super().draw`, `handle_key`/`handle_click` add the F2/tab behaviour on top of `super()`, and the icon catalog is cached in `_catalog_lookup` so the render path stays O(1) lookups. |

---

## Bundled Plugins

### Character Map (`charmap.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining CharMap items tracked from the current audit pass. `copy_char` and `copy_hex` actions are distinct and have correct semantics; copy logic flows through one `_copy_to_clipboards` helper; the detail-pane width is the `DETAIL_PANE_WIDTH = 22` constant; `about_map` writes a transient status via `_set_status`. |

### Clock (`clock.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Clock items tracked from the current audit pass. `always_on_top` toggling is centralised in `_toggle_always_on_top`; `_month_lines` caches the `TextCalendar` output keyed by `(year, month, first_weekday)`; the status separator uses the standard `"|"`. |

### Minesweeper (`minesweeper.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Minesweeper items tracked from the current audit pass. Right-click flagging routes through `BUTTON3_PRESSED`/`BUTTON3_CLICKED` masks; `normalize_key_code` is used in `handle_key`; the bomb/timer chrome uses the `menubar` theme tone; the dead `'f'` key handler was removed. |

### Snake (`snake.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Snake items tracked from the current audit pass. `step()` runs from `tick()`; `_save_high_scores()` is guarded by `_scores_saved` so it fires at most once per game; `obs_attr` is a single `theme_attr("window_inactive")` (no OR'd pairs); the difficulty label is recovered from the action via the `_DIFFICULTY_NAMES` class mapping. |

### Solitaire (`solitaire.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Solitaire items tracked from the current audit pass. `handle_key` accepts both lowercase and uppercase Q/R; the double-click detector uses a 500 ms window via `time.monotonic()`; the "from foundation" branch is rejected under Klondike rules; `C_ANSI_START` is imported once at module level. |

### Tetris (`tetris.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining Tetris items tracked from the current audit pass. Restart calls `reset_game()`; drop logic runs from `tick()`; `normalize_key_code` is used in `handle_key`; piece colors use `C_ANSI_START + cell` (no hardcoded 50); the I-piece rotation center is computed dynamically from the current cells and `round()` is used to keep multi-rotation pivots stable. The "no window menu" item is feature work, not a bug. |

### WiFi Manager (`wifi_manager.py`)

| Sev | Issue |
|---|---|
| INFO | - | No remaining WiFi Manager items tracked from the current audit pass. Background threads own both scan and connect with their own locks; the dedicated `_status_msg` indicator surfaces the in-flight state; `nmcli -t` lines are split with `_split_nmcli_fields` so escaped `\:` characters stay inside SSIDs; Ctrl+1 (the `1` keycode) is documented as a legacy shortcut; the password is fed to `nmcli --ask` over stdin, with a legacy-arg fallback only for older nmcli releases (documented in code). |

---

## Priority Summary

**CRITICAL (0):** RetroNet SSL bypass closed (uses `create_default_context` with an explicit opt-in fallback).

**HIGH remaining (0):** No per-app HIGH items left. The remaining WiFi-Manager concern is the documented legacy-`nmcli` password-argument fallback; the first attempt always uses `--ask` over stdin.

**MEDIUM remaining (1):**
- RetroNet HTML regex parser does not handle nested or malformed tags (returns best-effort text). Replacing the regex pre-processor with `html.parser.HTMLParser` is the right next step but is not blocking v0.9.5.
- v0.9.5 (Terminal 2D buffer) is partially complete: `TerminalScreenBuffer` and `TerminalScreen` exist in `core/terminal_session.py` with 22 unit tests, but the classes are not yet wired into `TerminalWindow` so the ANSI state machine still owns the normal-screen grid. The remaining items ("Cursor real por fila/columna en normal-screen", "Atributos por celda compatibles con seleccion/copy", and the alt-screen routing) are blocked on that wiring.

**LOW remaining (0):** All LOW items closed in the v0.9.4 hardening pass and the post-hardening cleanup pass.
