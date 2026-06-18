# RetroTUI — Improvement Plan

Analysis of every app and bundled plugin. Issues are categorized by severity and grouped by cross-cutting pattern when applicable.

**Status:** v0.9.4 hardening in progress over v0.9.3. The retroaudit backlog tracked here is now feeding directly into the v0.9.4 milestone in `ROADMAP.md`.

**Last reviewed:** 2026-06-18.

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
- Other: Markdown viewer adds `*italic*`, `` `inline code` ``, `[label](url)` link rendering, preserves `in_code_block` across scroll and supports the mouse wheel; Control Panel exposes `word_wrap_default` via a 4-state cycle and lets the user pick a specific theme with Left/Right or by clicking the theme row; Settings applies preferences consistently for all toggles; App Manager `IconsWindow` reuses the base class via `super()` and caches the icon catalog; Process Manager implements `cmd` sort, initializes `scroll_offset`, reads `/proc/meminfo` in a single pass, and no longer kills on double-click; Solitaire blocks foundation-to-column moves and uses a 500 ms double-click window; Tetris restarts through a new `reset_game()` helper and now computes the I-piece rotation center dynamically; Clock caches `TextCalendar` per `(year, month, first-weekday)` and dedupes the `always_on_top` toggle path; System Monitor adds a platform guard and rescales the CPU history when the window is resized; CharMap fixes the `22` / `20` detail-pane width mismatch, wires up the `about_map` action and dedupes the copy helpers; Calculator normalizes `-0` to `0` and trims dead `body_rect` locals; Minesweeper uses a non-error color for the bomb/timer chrome; Settings derives `_controls_count` from a `_TOGGLE_COUNT` constant; Clipboard Viewer `c` key now also clears the system clipboard.

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
| INFO | - | No remaining Terminal items tracked from the current audit pass. |

### Calculator (`apps/calculator.py`)

| Sev | Issue |
|---|---|
| MED | `evaluate_expression`: `RecursionError` not in `_CALCULATOR_EVAL_ERRORS` — deeply nested expressions crash the app |
| LOW | `normalize_negative_zero` (65-67): assigns `0.0 = 0.0` — no-op, never actually normalizes `-0.0` |
| LOW | `handle_key` (334-337): unused `bx` and `by` assignments |

### Hex Viewer (`apps/hexviewer.py`)

| Sev | Issue |
|---|---|
| HIGH | `draw` (383-391): reads file on every render frame — open/seek/read/close per tick |
| MED | `_rows_visible` (93) vs `draw` (379): different visible row counts — scroll allows cursor off-screen |
| MED | `_parse_search_query` (177-181): text with short words misinterpreted as hex — `int(token, 16)` raises uncaught `ValueError` |
| LOW | `has_selection`/`clear_selection`: reimplements `SelectableTextMixin` independently instead of using it |

### Process Manager (`apps/process_manager.py`)

| Sev | Issue |
|---|---|
| HIGH | `refresh_processes` (343): reads `/proc` inside `draw()` — blocks render loop every second |
| HIGH | `handle_click` (429-430): double-click fires `REQUEST_KILL_CONFIRM` — misclick risk on destructive action |
| MED | `_read_mem_total_kb` + `_read_mem_available_kb` (75-97): open `/proc/meminfo` twice — should be one pass |
| MED | `_sort_rows` (204-211): `cmd` sort key partially implemented (header renders arrow but sort falls through to CPU) |
| MED | `handle_click` (411-420): column sort boundaries hardcoded as magic numbers (7, 14, 21) |
| MED | `scroll_offset`: never initialized in `__init__` — relies on implicit base class attribute |

---

## Secondary Apps

### System Monitor (`apps/sysmon.py`)

| Sev | Issue |
|---|---|
| HIGH | Linux-only: reads `/proc/stat`, `/proc/meminfo`, `/proc/uptime` — silently broken on Windows/macOS |
| HIGH | CPU graph not re-scaled on window resize — `cpu_history` deque keeps values from old width |
| MED | `draw()` opens `/proc/uptime` every frame — should move to `_update_stats()` |
| MED | `mem_info['free']` initialized but never written or read — dead state |

### Log Viewer (`apps/logviewer.py`)

| Sev | Issue |
|---|---|
| HIGH | `_LOG_COLOR_INIT_ERRORS` and `_LOG_COLOR_APPLY_ERRORS` (14-29): identical tuples maintained separately |
| HIGH | `_reload_file` (243): `os.path.getsize()` after file close — TOCTOU race on busy log files |
| MED | `_reload_file` uses binary mode, `_poll_for_updates` uses text mode — inconsistent line-ending handling |
| MED | Search highlight + severity color conflict — no visual priority between `A_REVERSE` and color pair |
| LOW | `_append_lines` (206-208): rebuilds all search matches O(n) instead of incremental O(k) |

### Trash (`apps/trash.py`)

| Sev | Issue |
|---|---|
| HIGH | `empty_trash()` (110-127): no confirmation dialog — immediate permanent `shutil.rmtree` on all files |
| HIGH | `empty_trash()`: bails on first per-item error — leaves trash in partial state |
| MED | `_build_listing` (58-61): removes `..` entry by hardcoded index 2 — fragile if parent format changes |
| MED | No "Restore" / "Put Back" functionality — trash without restore is half-implemented |

### Clipboard Viewer (`apps/clipboard_viewer.py`)

| Sev | Issue |
|---|---|
| HIGH | `handle_key` (129, 134, 141): `getattr(key, '__int__', None)` — wrong duck-type check, should be `isinstance(key, int)` |
| HIGH | `handle_key` (144-150): `import curses as _c` inside method on every keypress — redundant with top-level import |
| MED | `_refresh_from_clipboard` (95): called on every `draw()` frame — polls system clipboard at render rate |
| MED | `handle_key` 'c': clears internal clipboard but not system clipboard |

### Control Panel (`apps/control_panel.py`)

| Sev | Issue |
|---|---|
| HIGH | Desktop category (103-121): only toggles `show_hidden` — `word_wrap_default` is unreachable from keyboard |
| HIGH | System category (118): sets `app.show_welcome` directly without calling `apply_preferences` |
| MED | Theme selection: only cycles forward — no way to select a specific theme |
| MED | `_theme_scroll` (34): initialized but never used — dead code |
| MED | Duplication with `SettingsWindow` — both manage same settings, no sync between them |

### Settings (`apps/settings.py`)

| Sev | Issue |
|---|---|
| HIGH | `handle_key` Left/Right: `apply_preferences` called inconsistently across toggles — live preview broken for some |
| MED | `_controls_count` (41): hardcodes `+ 6` — must be manually updated when adding toggles |
| LOW | `_committed = True` set on Cancel — misleading flag name |

### Image Viewer (`apps/image_viewer.py`)

| Sev | Issue |
|---|---|
| HIGH | `_render_image` (142-151): `subprocess.run(timeout=3.0)` blocks main thread |
| HIGH | `status_message` cleared inside `draw()` — state side effect in render |
| MED | `_detect_backend()`: called multiple times per frame before cache is set |
| MED | Zoom index `2` hardcoded — should be `ZOOM_LEVELS.index(100)` |
| MED | PageUp/PageDown for zoom is undocumented and conflicts with expected scroll behavior |

### Markdown Viewer (`apps/markdown_viewer.py`)

| Sev | Issue |
|---|---|
| HIGH | `curses.color_pair(4)` (103): used without initialization — may raise curses error or conflict with theme |
| HIGH | `in_code_block` (86-104): not preserved across scroll — mid-block viewport renders wrong formatting |
| MED | Only handles `**bold**` — no italic, inline code, or links |
| MED | `_max_scroll` (69): uses `raw_content` length, not rendered line count |
| MED | `handle_click`: no scroll wheel support — unlike every other scrollable viewer |

### RetroNet (`apps/retronet.py`)

| Sev | Issue |
|---|---|
| CRIT | `ssl._create_unverified_context()` (141) — SSL disabled globally |
| HIGH | `self.content` (155) and `self.title` (171) written from background thread — no lock |
| HIGH | `handle_key` scroll bound (377): uses `self.h - 6` instead of `body_rect()` height |
| MED | HTML regex parsing (174): fails on nested/malformed tags |
| MED | `_RETRONET_FETCH_ERRORS` (27-39): catches `SyntaxError`, `AssertionError` — hides bugs |
| MED | History deduplication (119): linear scan O(n), prevents correct Back navigation |

### App Manager (`apps/app_manager.py`)

| Sev | Issue |
|---|---|
| HIGH | `IconsWindow.draw()` (377-464): duplicates 60+ lines from base class without calling `super()` |
| HIGH | `IconsWindow.handle_key()` (466-506): copy-paste from base class with only F2 added |
| HIGH | `IconsWindow.handle_click()` (508-534): duplicated, silently removes checkbox toggle |
| MED | `_iter_catalog_entries` (432): rebuilds dict from full catalog on every frame |

---

## Bundled Plugins

### Character Map (`charmap.py`)

| Sev | Issue |
|---|---|
| HIGH | Action `"copy_hex"` (65) actually copies the character, not hex — naming inversion |
| MED | Copy logic duplicated in 3 places (handle_key, execute_action x2) |
| MED | Grid width magic constant `22` (80) doesn't match detail pane drawn at `bw - 20` (118) |
| LOW | `"about_map"` menu action registered but never handled |

### Clock (`clock.py`)

| Sev | Issue |
|---|---|
| MED | `always_on_top` toggled in two separate paths (handle_key + execute_action) — not deduplicated |
| LOW | `_month_lines` (75): creates new `TextCalendar` on every frame |
| LOW | Separator string `"-------------"` instead of standard `"-"` |

### Minesweeper (`minesweeper.py`)

| Sev | Issue |
|---|---|
| HIGH | `bstate.right` (284): checks `.right` attribute on an integer — right-click flagging is completely broken |
| HIGH | `handle_key` (316-318): bypasses `normalize_key_code` — keyboard input broken on `get_wch()` terminals |
| MED | `curses.color_pair(1)` (202, 207): uses `C_DESKTOP` color pair for timer/bomb count — wrong colors |
| LOW | 'f' key handler (318-321): explicit no-op — dead code |

### Snake (`snake.py`)

| Sev | Issue |
|---|---|
| HIGH | `step()` called from `draw()` with `now=None` (282) — forces move every frame, speed system bypassed |
| HIGH | `_save_high_scores()` in draw (297-299) — writes JSON to disk ~30x/sec after game-over |
| MED | `obs_attr` (313): ORs two color pair attributes — undefined curses behavior |
| MED | `_update_menu_checks` (219-221): label prefix corrupts difficulty comparison on second call |

### Solitaire (`solitaire.py`)

| Sev | Issue |
|---|---|
| HIGH | `handle_key` (403-407): only responds to lowercase 'q'/'r' — uppercase ignored |
| MED | Double-click detection (299-307): no timing — any two clicks at same position count as double-click |
| MED | Foundation-to-column moves allowed — violates Klondike rules |
| MED | `_draw_card` (163): imports `C_ANSI_START` inside method (called 52x/frame) |

### Tetris (`tetris.py`)

| Sev | Issue |
|---|---|
| HIGH | Restart calls `self.__init__()` (181) — dangerous re-initialization of constructed object |
| HIGH | Game logic in `draw()` (116-125) — speed depends on frame rate |
| HIGH | `handle_key` (178-212): doesn't use `normalize_key_code` — broken on `get_wch()` terminals |
| MED | `curses.color_pair(50 + cell)` (149, 154, 168): hardcodes `50` instead of importing `C_ANSI_START` |
| MED | `_rotate_piece` (65-66): uses `int()` truncation on float centers — incorrect I-piece rotation |
| MED | No window menu — can't start new game or pause from menu |

### WiFi Manager (`wifi_manager.py`)

| Sev | Issue |
|---|---|
| HIGH | `refresh()` (62): `time.sleep(1)` blocks entire TUI |
| HIGH | `_execute_nmcli_connect` (193): blocks main thread 10-30 seconds |
| HIGH | `_fetch_error` (120): attribute never set — dead branch, error never shown |
| MED | nmcli output parser (71): splits on `:` without handling `\:` escapes — SSIDs with `:` break |
| MED | Ctrl+1 keybinding (247): actually triggers on Ctrl+A — collision with standard shortcut |
| MED | Password passed as CLI argument (187-189) — visible in `ps aux` |

---

## Priority Summary

**CRITICAL (0):** RetroNet SSL bypass closed (uses `create_default_context` with an explicit opt-in fallback).

**HIGH remaining (1):** WiFi Manager still falls back to passing the password as a CLI argument on older `nmcli` releases that lack `--ask`. The first attempt always uses `--ask`; only the fallback path leaks the secret. Documented in code.

**MEDIUM remaining:**
- RetroNet HTML regex parser does not handle nested or malformed tags (returns best-effort text).

**LOW remaining:** Cosmetic polish (Clock separator string, Snake obs_attr theme_attr alignment).

**Closed in this iteration:**
- WiFi Manager: `nmcli -t` output is now split on unescaped colons so SSIDs containing `:` (encoded as `\: ` by `nmcli -t`) are preserved.
- WiFi Manager: password is always sent via stdin (nmcli `--ask`) on the first attempt; the CLI-arg fallback only runs on releases that lack `--ask`.
- Snake: back-to-back difficulty changes keep the menu checkmark in sync (new unit test covers the sequence); `_update_menu_checks` now looks up the difficulty name via the action instead of parsing the previous label.
- Settings: renamed `_committed` to `_finalized` so the flag is no longer misleading when the user chooses Cancel.
- Control Panel: removed the unused `_committed` attribute.
- Hex Viewer: now mixes in `SelectableTextMixin` for `clear_selection`/`has_selection` and stores row spans as `(row, 0)` tuples so the mixin's bounds/span helpers apply.
- Terminal: introduced a `TerminalScreenBuffer` 2D rows x cols class (22 unit tests) and a `TerminalScreen` wrapper that holds the normal and alt screens separately. Both landed in `core/terminal_session.py`.
- Hex Viewer: now mixes in `SelectableTextMixin` for `clear_selection`/`has_selection` and stores row spans as `(row, 0)` tuples so the mixin's bounds/span helpers apply.
