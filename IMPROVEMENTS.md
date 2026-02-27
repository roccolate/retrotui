# RetroTUI — Improvement Plan

Analysis of every app and bundled plugin. Issues are categorized by severity and grouped by cross-cutting pattern when applicable.

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
| HIGH | `window.py:791-796` | `entry.size & 0o111` tests executable bit on **file size** instead of **file mode** — wrong attribute |
| HIGH | `operations.py:122` | `open(path, 'a').close()` — unclosed file handle, use `pathlib.Path.touch()` |
| MED | `window.py:1053-1056` | `handle_key` passes raw `key` to `_handle_pane_navigation` instead of normalized `norm_key` |
| MED | `window.py:563` | Directory preview cache key uses constant `0` for size — stale previews after directory changes |
| MED | `window.py:674-686` | `_dual_copy_move_between_panes` drops the error `ActionResult` from `perform_copy`/`perform_move` |
| MED | `core.py:103-104` | `clamp()` uses `len(self.content) - 1` — off-by-one scroll bound |
| MED | `operations.py:13` | `_trash_base_dir` creates `.local/share/Trash/files` on Windows — nonsense path |
| MED | `operations.py:97` | `perform_undo` returns `None` instead of `ActionResult` — inconsistent API |
| MED | `bookmarks.py` | Bookmarks are not persisted across sessions |
| MED | `preview.py:75-81` | `_detect_image_preview_backend` calls `shutil.which()` on every preview render — never cached |
| LOW | `window.py:724-726` | Dead code: `border_attr` assigned then overwritten with identical value in `if self.active` |
| LOW | `window.py:611` | Directory drag silently ignored — no user feedback |
| LOW | `core.py:46-53` | `FileEntry.use_unicode` stored but never consulted — dead slot |
| LOW | `core.py:56-61` | `_format_size` doesn't handle GB-scale files |
| LOW | `bookmarks.py:12-13` | Default bookmarks `/var/log`, `/etc` don't exist on Windows |

### Notepad (`apps/notepad.py`)

| Sev | Issue |
|---|---|
| MED | `_compute_wrap` (184-188): slices by character count, not terminal cell width — CJK characters overflow columns |
| MED | `_cursor_to_wrap_row` (195-203): fallback returns `0` on cache miss — jumps cursor to top of file |
| MED | `_key_toggle_wrap` (617-620): discards `ActionResult` from `_toggle_wrap()` — Ctrl+W never persists the config change |
| LOW | `draw` (303-310): rebuilds title string with `os.path.basename` on every frame |
| LOW | `handle_right_click` (766-781): builds then discards "Cut Line"/"Copy Line" items when selection exists |
| LOW | `get_context_menu_items` (785-787): deprecated stub, always returns `[]` |

### Terminal (`apps/terminal.py`)

| Sev | Issue |
|---|---|
| HIGH | `_apply_csi` (204-213): `H`/`f` CSI ignores row component — full-screen apps (vim, htop, nano) display garbage |
| MED | `_ensure_session` (398): called from `draw()` — session startup blocks render loop |
| MED | `_session.resize` (400): called unconditionally every frame — unnecessary SIGWINCH ioctl ~30x/sec |
| LOW | `_session_error` (405-407 vs 442): error cleared before status bar reads it — status never shows `ERR` |
| LOW | Tab handling (249-253): uses 4-space stops instead of standard 8-column stops |
| LOW | `_send_interrupt` (526-533): fallback `write('\x03')` after callable sender is unreachable |

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

**CRITICAL (1):** RetroNet SSL bypass

**HIGH (30):**
- Game logic in draw: snake (2), tetris (2)
- Blocking I/O: wifi (2), image_viewer (1), hexviewer (1), process_manager (1), terminal (1)
- Thread safety: retronet (2)
- Broken input: minesweeper (2), tetris (1)
- Wrong attribute: filemanager executable bit check
- Unclosed file: filemanager operations
- No confirmation: trash empty
- Code duplication: app_manager (3)
- Other: sysmon platform, logviewer race, control_panel unreachable toggle, retronet scroll, markdown color pair, solitaire case sensitivity, tetris __init__ restart

**MEDIUM (48):** Scattered across all files — scroll bounds, cache misses, API inconsistencies, missing features.

**LOW (28):** Dead code, naming issues, minor UX gaps.
