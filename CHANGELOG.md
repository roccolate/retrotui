# Changelog

Todas las versiones notables de RetroTUI están documentadas aquí.

---

## [Unreleased] - 2026-07-22

Hardening and visible-shell work completed after the original pre-v0.9.6 stabilization gate. The published package remains `0.9.5`; these changes are present on `main` and still require real-terminal certification before a v0.9.6 release.

### Core, workers and file operations

- Externalized circuit-breaker ownership from application windows while preserving legacy compatibility mirrors.
- Added typed payloads for destructive confirmations, transfers, process signals and configuration updates.
- Added configuration `schema_version = 1`, legacy migration and protection against overwriting unknown future schemas.
- Added `WorkerScope` ownership, cooperative cancellation, bounded shutdown and stale-result rejection for window and global workers.
- Added cooperative copy/move transfers with deterministic progress, block-level cancellation, transactional destination publication and no-clobber semantics.
- Added crash-recoverable Trash move, restore, permanent-delete and empty-trash journals with startup reconciliation.
- Hardened idle redraw behavior and Wi-Fi worker executable capture.

### Embedded terminal

- Gave focused terminal windows ownership of terminal-oriented keys and introduced `F12` as the explicit host-command prefix.
- Added DEC cursor visibility, application cursor keys, bracketed paste and effective autowrap state.
- Added a conservative child `TERM` contract, bundled `retrotui` terminfo source and installer command.
- Added Unicode-aware physical cells for CJK, emoji and combining sequences while preserving the legacy two-item cell tuple contract.
- Added DEC scrolling margins, origin mode, screen editing operations, alternate-screen cursor restoration and Unicode-safe wide-cell edits.
- Added IND, NEL, RI, tab stops, TBC/CHT/CBT, device-status reports and cursor-position reports.
- Hardened OSC termination, window close-hook isolation and the live-tail scrollback hot path.

### Shell and Unicode UI

- Added physical-column clipping and hitboxes for window titles and taskbar labels.
- Extended physical-column geometry to global/window menus, dialogs, progress dialogs and multiselect controls.
- Fixed Control Panel checkbox click ranges and immediate preference persistence.
- Moved the global shell to a classic bottom taskbar with `[ Inicio ]`, upward global dropdowns, minimized-window buttons and clock.
- Made desktop icons share one Unicode-aware geometry between rendering and mouse hit testing.
- Extended physical-column fitting to File Manager, Process Manager and App Manager rows, tabs and buttons.

### Validation and maintenance

- Every implementation cut passed the permanent Ubuntu/Windows matrix on Python 3.10, 3.12 and 3.14, including QA, Ruff F821, `unittest`, pytest and the module coverage floor.
- Implementation PRs were squash-merged after exact-head validation.
- Fully absorbed remote branches and temporary maintenance refs were removed; `main` is the only long-lived remote branch.

---

## [pre-v0.9.6] - 2026-07-21 (stabilization complete)

Gate técnico completado antes de comenzar la certificación cross-terminal de v0.9.6.

### Core y lifecycle

- `WindowManager` quedó como autoridad única de spawn, focus, z-order y close.
- `Window.request_close()` implementa cierre transaccional; Notepad protege buffers dirty en todas las rutas.
- EventBus se crea y consume de forma determinística.
- `tick()`, `wants_periodic_tick` y `tick_when_hidden` tienen responsabilidades separadas.
- El event loop aísla fallos repetidos de `tick()` y `draw()` mediante circuit breaker.
- Los pares de color se negocian contra `curses.COLOR_PAIRS` sin perder los IDs lógicos históricos.

### Diálogos, input y apps

- Los workflows de diálogo usan IDs estables, callbacks tipados y ventana fuente capturada.
- Drag-and-drop prioriza `accept_dropped_path()` y usa `open_path()` solo como fallback.
- RetroNet comparte geometría entre render y click de tabs.
- El scrollback de Terminal conserva una sola fuente de verdad y no duplica filas visibles.

### Terminal PTY

- Terminal continúa dando servicio al PTY mientras está minimizado.
- Las lecturas admiten un presupuesto agregado de 8 KiB por tick.
- Las escrituras usan una cola FIFO y preservan sufijos ante partial write, retorno cero o `EAGAIN`.
- ConPTY recibe `cwd` y entorno heredado/extendido cuando la API lo permite.
- Se soportan variantes actuales, posicionales y legacy de `pywinpty.spawn()`.
- El cierre Windows es explícito y verificable; si el hijo sigue vivo no se declara éxito ni se descarta la cola pendiente.

### CI y compatibilidad

- `pytest` forma parte de las dependencias de test.
- CI ejecuta QA, `unittest` y pytest por separado.
- Matriz permanente: Ubuntu y Windows con Python 3.10, 3.12 y 3.14.
- Las seis combinaciones terminaron verdes al cerrar el gate.
- `windows-curses` y `pywinpty` se declaran como dependencias de runtime marcadas para Windows.

### Documentation

- README, arquitectura, roadmap, release policy y handoff operativo fueron alineados con el estado real.
- `docs/STABILIZATION_PRE_0.9.6.md` registra contratos, regresiones y límites del gate.
- Las auditorías de julio se conservan como documentos históricos; v0.9.6 continúa con pruebas reales en `docs/TTY_TEST_MATRIX.md`.

---

## [v0.9.5.1] - 2026-06-30 (unreleased hardening)

Pre-v0.9.6 pass: full audit + perf sweep over `core/`, `apps/` and `ui/`
that landed as 4 commits between v0.9.5 and this entry. No public API
changes. 116 fixes in total.

### Fixed (audit — core/, 36 fixes)
- **Event loop hardening**: inner `try` catches `Exception` (log + continue) so a buggy per-window hook can no longer bypass `app.cleanup()`. Non-fatal resize re-validation. Single combined `tick + live + animated` walk instead of three separate `app.windows` passes per loop iteration.
- **IPC**: `IPCRouter.send` / `broadcast` now catch the broadest `Exception` family (not just `_IPC_ERRORS`) so a buggy plugin handler can no longer crash the main thread. The `app.notify`-style `socket`-protocol callbacks are no longer leaked.
- **Lifecycle**: `WindowManager.close_window` is idempotent (guards the `self.windows.remove` on re-entry / duplicate calls). `WindowManager.get_active_window` is O(1) via a cached `_active_window` pointer instead of an O(n) `next()` scan. `set_active_window` only deactivates the previous active window. `_active_window_menu_owner` is defensively cleared when the window has gone away.
- **ANSI state machine**: `parse_chunk` no longer fabricates `[0]` defaults — the parser leaves `self.params` empty and consumers apply per-command defaults (e.g. CUP defaults to row=1, col=1).
- **Mouse**: `is_click_like` for the title-bar buttons (close / min / max) now gates on `_is_button1_click_event` (release) so press-then-drag-away cancels cleanly instead of closing the window.
- **ANSI**: `getmouse()` is unpacked with `*_rest` (length-tolerant) and `ValueError` / `TypeError` are caught alongside `curses.error` so a malformed tuple can no longer bypass `app.cleanup()` and leave SGR mouse modes stuck.
- **OSC state machine**: handles `ESC` inside the OSC body (opens the ST terminator) instead of looping forever inside OSC state when a stray `ESC` arrives.
- **Config / persistence**: `app.shutdown_signal` is captured in `__main__.main` and mapped to `128+signum` exit codes for SIGTERM/SIGHUP. `parse_preferences` no longer publishes a stale `show_welcome` value (the new value is now passed through `apply_preferences`).
- **Config TOML strings** now go through `toml_basic_string`; `icon_manager._quote_toml_key` uses the shared helper (was missing `\n`/`\r`/`\t` handling, which corrupted configs when an icon label contained a newline).
- **Rendering**: `get_screen_pos` accepts `frame_size`; `draw_icons` threads it through so the desktop icon path no longer calls `getmaxyx()` per uncached icon.
- **draw() / draw_frame() / draw_body() / draw_bar() / draw_dropdown()** now accept `frame_size=None` and pass `_bounds=frame_size` to every `safe_addstr` in the hot path. `draw_box()` got the same treatment.
- **Window rect invalidation**: `WindowManager.set_active_window` only emits the `window.focused` event after the layer reorder; `get_active_window` and `cycle_focus` validate the cached pointer.
- **Imports / startup**: pre-v0.9.6 round of `utils.toml_basic_string` / `utils.atomic_write_text` / `utils.decode_toml_basic_string` / `draw_box` helper, used everywhere downstream.
- **24 LOW items** in `core/`: per-row blank hoists, micro-cache for `_preview_symbol`, `_render_image` cancel-event, etc.

### Fixed (audit — apps/ + ui/, 65 fixes)
- **Notepad**: `open_path` now asks before discarding unsaved work (`REQUEST_SAVE_CONFIRM` dialog). `_save_file`, FM bookmarks, FM trash metadata, view-source temp files, and game score files (minesweeper, snake, solitaire) all use `atomic_write_text` so a SIGKILL mid-write can no longer truncate user data.
- **Trash metadata** is written *before* the move (and removed on move failure) so a crash between the two can no longer leave undo broken.
- **App manager**: `IconsWindow._activate_button` persists visibility checkboxes before applying the new style (the override was dropping the base-class contract).
- **Charmap**: typo `status_message` → `_status_message`; the block name now actually shows in the footer.
- **Markdown viewer**: precomputed `_fence_parity` table replaces the per-frame `O(scroll_offset)` re-scan.
- **Filemanager**: `FileEntry` caches the executable bit at listing time (no `os.access` syscall per visible row per draw). Drag is now wired on the secondary pane. Split boundary uses a single formula in both click handlers. `NPAGE` / `End` scroll math uses the real display height. Rename preserves the cursor in the active pane. `perform_delete_entry` no longer drops the per-trash override. `create_file` / `create_directory` use `FileExistsError` instead of TOCTOU `os.path.exists`.
- **Terminal**: CSI `P` (DCH) caps row growth so the buffer invariant holds. Word-wrap scrolls feed the shared scrollback via the new `TerminalScreenBuffer.set_scroll_sink` hook (was lost). `_alt_lines` property-based resize loop replaced with a single `alt.resize` when the size changes (was `O(rows²)` per frame). `_max_scrollback_offset` uses `_all_lines_count()` (no list allocation).
- **Notepad undo**: selection-replace operations no longer double-push onto the undo stack.
- **RetroNet**: SSL warning now includes the underlying reason and only fires on the actual fallback path. Tab-bar click uses the same chip layout as draw via a shared `_tab_chip_label` / `_tab_chip_width` helper. Malformed HTML that never emits `</a>` no longer swallows the rest of the page.
- **App manager / Settings / Control Panel**: `IconsWindow` save wraps in `try/except OSError`. `show_welcome` is now passed to `apply_preferences` instead of being mutated after the publish. Live toggles use `apply_to_open_windows=True`.
- **Wifi manager**: `_finish_connect` uses the stored SSID instead of substring-slicing the previous status. `--ask` OSError no longer falls back to the insecure `password=` argv form. Dead `_scan_thread` / `_connect_thread` attribute writes removed (the daemon thread leaked live `nmcli` subprocesses).
- **Image viewer**: previous render thread is cancelled via a `threading.Event` before a new one starts. Cache look-up skips `os.stat` on the fast path. `get_screen_pos` accepts `frame_size`.
- **Logviewer**: severity highlight restricted to leading bracketed / prefix formats to avoid false positives on substring matches. Precomputed `self.lines_lc` lowercase mirror avoids `line.lower()` per row per draw. `query_lc` and `basename` cached on the instance and only re-derived when the underlying value changes. `draw` no longer calls `_poll_for_updates` (was reopening the log file per redraw when the ticker was overdue).
- **Hexviewer**: 2-slot LRU cache so the `tick()` warm-up survives the `draw()` read.
- **Process manager**: `ProcessLookupError` now surfaces a `REFRESH` with a message instead of a silent no-op.
- **Calculator**: `_button_rect` returns `None` when `bh` is too small to fit the button grid (so the body fill is not overwritten by buttons).
- **draw_box()** with `_bounds=`: threaded through window / dialog / menu / app_manager. **ContextMenu** uses `try/finally` for the attr stack and caches the clamped draw coordinates for hit testing. **4 game `draw()` overrides** (minesweeper / snake / solitaire / tetris) accept `frame_size=None` and forward it.
- **22 LOW items** in apps/ui: process_manager kill no longer silent, `os.path.basename` cached, terminal scrollback reset on alt-screen, retro tab close neighbour, snake speed scale, etc.

### Performance (10 + 2 structural fixes)
- **WindowManager.active_window pointer** — `get_active_window` is O(1) instead of O(n). `set_active_window` only deactivates the previous active window.
- **PaneState name index** — `select_by_name` is O(1) via a `{name: idx}` dict rebuilt in `_rebuild_pane`; subsequent linear scan only as a fallback.
- **File manager preview stat cached** — `get_entry_info_lines` returns a cached `(mtime_ns, size)`-keyed result.
- **Per-row " " * bw** hoists across multiple apps; module-level compiled regexes in markdown viewer and retronet; `inspect.signature` cached on app after first call.
- **Sysmon** graph: snapshot `cpu_history` slice once per draw (was re-`list`ing on every row), `list+join` instead of `line +=`.
- **Process manager**: `/proc/meminfo` opened once via `_read_meminfo()`.
- **Event loop**: 3× `app.windows` walks per iteration combined into 1 (`_tick_and_probe_windows`).
- **Game score files** are now `atomic_write_text`-backed (M-from-L).
- **Notepad per-line wrap cache (M15)** — `_wrap_line_cache[i]` holds the wrapped chunks for `self.buffer[i]`. `_invalidate_wrap(line_idx=None)` marks a single line dirty (cheap) or all (for width changes). `_sync_wrap_cache_to_buffer()` re-aligns the cache list after insert/delete (re-baking the baked-in `line_idx` for surviving lines). Single-character insert is now O(stale_lines) per draw instead of O(buffer_length); micro-benchmark on a 2000-line file: 30.5ms → 0.27ms (~113× speedup).
- **Hidden-CSV parser cache (M11)** — module-level `@functools.lru_cache(maxsize=32)` on the CSV split; cache key is the raw string. `get_hidden_icon_labels` and `get_hidden_menu_keys` reuse the same cached parser. Micro-benchmark: 1000 lookups on a 50-token CSV dropped from 4.5ms to 0.1ms (~45× speedup).

### Added
- `tests/test_perf_cache_stress.py` — 7 stress tests for the M15 (wrap cache) and M11 (hidden-CSV) caches: large buffer + 200 single-char edits + 200 draws, 5000-line buffer + many insert/delete, cache invalidation on string change, large CSV perf.

---

## [v0.9.5] - 2026-06-19

### Added
- **Terminal 2D buffer wiring**: `TerminalWindow` ahora delega en `TerminalScreen` (dos `TerminalScreenBuffer`, normal + alt). El state machine ANSI escribe vía `put_char` / `line_feed` / `clear_screen`; la posición del cursor y los atributos por celda los lee el renderer directamente del buffer. Scrollback capturado en cada newline vía un wrapper `_ScrollbackBuffer`. 13 tests nuevos en `tests/test_terminal_buffer_wiring.py`.
- **Mouse pass-through en Terminal**: tracking de DEC private mouse modes (`?1000h` / `?1002h` / `?1003h` / `?1005h` / `?1006h` / `?1015h`). Cuando el hijo activa alguno, clicks/drags/scroll se codifican como secuencias SGR (`\e[<Cb;Cx;CyM`/`m`) y se reenvían al PTY. Motion-with-button sólo con `?1002h`/`?1003h`; motion-without-button sólo con `?1003h`. 14 tests nuevos en `tests/test_terminal_mouse_passthrough.py`.
- **Compatibilidad GPM preservada**: cuando el hijo no activa mouse reporting, RetroTUI retiene el mouse para selección/scrollback/menus (sea GPM en Linux console o SGR en xterm). Cubierto por tests en `test_terminal_mouse_passthrough.py`.
- **RetroNet HTML parser**: regex en cascada reemplazado por `_RetroNetHTMLParser` (basado en `html.parser.HTMLParser`). Tags anidados, entidades HTML, `<script>`/`<style>`, `<input type="hidden">` y `<!DOCTYPE>`/comentarios ahora se manejan correctamente. 9 tests nuevos en `tests/test_retronet.py`.
- **RetroNet tabs por ventana**: `Ctrl+T` nueva tab, `Ctrl+W` cierra (cierra ventana si es la última), `Ctrl+I` siguiente, `Shift+Tab` anterior. Click en chip activa; click en `×` cierra. Tab bar visible solo con 2+ tabs.
- **RetroNet bookmarks persistentes**: en `~/.config/retrotui/bookmarks.toml` (formato flat sections, compatible con el toml fallback de `core/config.py`). `Ctrl+B` abre la lista, `Ctrl+D` agrega la URL actual. Nueva `BookmarksWindow` con navegación ↑/↓/j/k, Enter navega y cierra, `d` borra, `r` recarga. 16 tests nuevos entre `test_bookmarks_core.py` y `test_bookmarks_window.py`.
- **RetroNet view source**: `Ctrl+U` abre el HTML crudo en una NotepadWindow via temp file con path derivado del hash de la URL. 6 tests nuevos.

### Changed
- **Audit refactor**: `TerminalScreen.__init__` ahora acepta `normal_cls`/`alt_cls` para inyectar buffers custom (usado por el wiring).
- **IMPROVEMENTS.md archivado**: la auditoría v0.9.4 + v0.9.5 queda cerrada; los items abiertos viven ahora en `ROADMAP.md` (v0.9.6 cert + v0.9.7 session restore).
- **ROADMAP.md actualizado**: v0.9.5 marcado como cerrado.
- **Release gates sincronizados**: `tools/qa.py` y `tools/check_release_tag.py` validan la versión en `pyproject.toml`, `retrotui/__init__.py`, `retrotui/core/app.py` y `setup.sh`.

### Fixed
- **v0.9.4 hardening carry-overs**: 14 MED/LOW remanentes del pass anterior (File Manager trash override, Notepad title caching, Hex Viewer mixin, Snake difficulty lookup, Calculator `-0`/`0` normalize, Minesweeper chrome, Settings toggle count, etc.).
- **Post-hardening cleanup**: módulo huérfano `core/win_termios.py` eliminado; `/proc/uptime` solo se lee desde `_update_stats` en System Monitor; tests de regresión para `_max_scroll()` del Markdown Viewer.
- **Limpieza archivo por archivo**: pasada sistemática sobre 276 archivos versionados. Se cerraron rutas locales hardcodeadas en tests, parsing frágil de variables de entorno (`RETROTUI_PROFILE_INTERVAL`, `RETROTUI_MOUSE_TRACE_MIN_INTERVAL`), lecturas `/proc` sin `errors='replace'`, fixtures con versión vieja y validaciones de release incompletas.
- **QA ampliado**: suite automatizada en 1084 tests; nuevos casos para plugins de ejemplo, QA/version sync, System Monitor, release tag, event loop y mouse router.

---

## [v0.9.4] - 2026-03-15

### Added
- **Terminal hardening**: PTY start/read/resize fuera de `draw()` (movido a `tick()`); resize cacheado por tamaño del body de la terminal; errores de sesión visibles sin spam; tabs de 8 columnas; CSI `H`/`f`/`J` con clamping; wrap en alt-screen; PageUp/PageDown para apps full-screen; F1-F12 básico; fallback de interrupción simplificado.
- **File Manager**: `Path.touch()` para archivos nuevos; copia de directorios a destino exacto (no se duplica); bloqueo de operaciones sobre `..`; preview de imagen async; cache de preview por stat del archivo; teclas normalizadas; tamaños GB/TB.
- **Notepad**: wrap por ancho de celda (CJK/wide chars); cache de wrap visible; título cacheado por filepath/modified state; presupuesto de undo para archivos grandes; Ctrl+W persistente; context menu real.
- **Base profile mínimo**: solo File Manager, Terminal y Notepad visibles por defecto. Apps secundarias y plugins quedan instalados pero deshabilitados por configuración.
- **Game logic fuera de `draw()`**: Snake, Tetris, Process Manager, Hex Viewer, Clipboard Viewer, Image Viewer y WiFi Manager corren sus updates desde `tick()`. `step()` preservado para tests pero ya no invocado desde el renderer.
- **I/O bloqueante a background threads**: WiFi Manager scan/connect, Image Viewer render, Hex Viewer cache warming. Indicadores de progreso (`_status_msg`, `[rendering...]`).
- **Thread safety RetroNet**: lock en `url`, `back_stack`, `forward_stack`, `title`, `content`, `is_loading`. Read paths en draw/handle_click usan el mismo lock.
- **Trash**: nuevo action type `REQUEST_EMPTY_TRASH_CONFIRM` con diálogo dedicado; `perform_delete` escribe `.trashinfo` sidecar; `perform_restore` lo consume; menú "Restore" + shortcut `R`.
- **Bundled plugins**: los 9 wrappers aplican el `title` del manifest a la ventana en lugar de descartarlo silenciosamente.
- **Input handling**: `normalize_key_code` usado por Minesweeper, Tetris, Solitaire, WiFi Manager y Clipboard Viewer. Reemplazo de `getattr(key, '__int__', None)` por `isinstance(key, int)` + `normalize_key_code` en Clipboard Viewer.
- **Markdown viewer**: `*italic*`, `` `inline code` ``, `[label](url)` link rendering, preserva `in_code_block` a través de scroll, soporta mouse wheel.
- **Control Panel**: expone `word_wrap_default` via cycle de 4 estados; selección de tema con Left/Right o click.
- **App Manager**: `IconsWindow` reusa la clase base via `super()` y cachea el catálogo de iconos.
- **Process Manager**: `cmd` sort implementado; `scroll_offset` inicializado; lee `/proc/meminfo` en una sola pasada; sin kill en doble-click.
- **Solitaire**: bloquea foundation-to-column moves; ventana de doble-click 500 ms.
- **Tetris**: restart usa `reset_game()`; pieza I con centro de rotación dinámico.
- **Clock**: `TextCalendar` cacheado por `(year, month, first_weekday)`; toggle `always_on_top` deduplicado.
- **System Monitor**: platform guard para no-Linux; CPU history reescalado al redimensionar.
- **CharMap**: ancho de detail pane unificado en `DETAIL_PANE_WIDTH = 22`; `about_map` wired via `_set_status`.
- **Calculator**: normaliza `-0` a `0`; trim dead `body_rect` locals.
- **Minesweeper**: chrome de bomb/timer usa `menubar` theme tone.
- **Settings**: `_controls_count` derivado de `_TOGGLE_COUNT`.
- **Hex Viewer**: `SelectableTextMixin`; row spans como tuplas `(row, 0)`.
- **Snake**: `_DIFFICULTY_NAMES` class mapping para lookup del action.
- **WiFi Manager**: `nmcli -t` líneas split con `_split_nmcli_fields` para preservar `\:`; Ctrl+1 documentado como legacy shortcut; password vía `nmcli --ask` con fallback para versiones antiguas.
- **RetroNet**: `_create_unverified_context()` SSL bypass eliminado; opt-in `check_hostname=False` solo tras `ssl.SSLError`. Scroll bound usa `body_rect()`. Fetch-error tuple restringido. `_load_url` deduplica entrada previa en back_stack.

### Fixed
- **Post-hardening cleanup**: módulo huérfano `core/win_termios.py` eliminado (no importers desde que el `try/except` termios import fue adoptado en `d519870`); `/proc/uptime` se lee solo desde `_update_stats`; Markdown `_max_scroll()` corregido.

---

## [v0.9.3] - 2026-02-27

### Added
- **Animated plugin auto-refresh**: `needs_redraw` mechanism in `Window` base class. Animated plugins (aquarium, matrix, starwars, game-of-life, pomodoro, system-monitor, network-monitor) and LogViewer now refresh automatically without user interaction.
- **Adaptive input timeout**: 100ms timeout for animated windows, cascading back to 500ms idle when no animations are active.
- **Per-plugin icons**: `[plugin.icon]` section in `plugin.toml` with `emoji` and `token` fields. All 21 example plugins have custom icons.
- **Braille pixel art icons**: 8x12 pixel grids rendered as 4x3 Unicode braille characters for all 39 icons (18 built-in + 21 plugins).

### Changed
- **Core modularization**: `core/app.py` decomposed into 5 modules (window_manager, action_runner, dialog_dispatch, drag_drop, file_operations).
- **Bundled plugins**: 9 apps migrated from `apps/` to `bundled_plugins/` (charmap, clock, image-viewer, minesweeper, retronet, snake, solitaire, tetris, wifi-manager).
- **Notepad**: dispatch table (`_KEY_DISPATCH`) replaces 217-line if/elif chain.
- **File Manager**: pane state unified with `PaneState` + compatibility properties.
- **Terminal**: dead code cleanup (`_dirty_lines`), session error visibility fix.
- **Windows support**: dual PTY backend (POSIX `pty.fork()` + Windows `pywinpty` ConPTY), conditional deps, cross-platform flow control shim.
- Icon style system reduced to 3 styles: default, mini, braille (removed codex).
- Test suite expanded to 970 tests.

---

## [v0.9.2] - 2026-02-24

### Added
- Baseline profiling guide in `docs/BASELINE_PROFILING.md`.
- Baseline artifacts directory scaffold in `docs/baseline/`.

### Fixed
- Mouse routing now preserves left-button pressed state on inferred motion paths, restoring drag text selection in apps like Notepad/Terminal.
- Added regression coverage for inferred drag behavior in `tests/test_mouse_router.py`.

---

## [v0.9.1] - 2026-02-18

### Added
- **Core Engine**:
    - Modular architecture: `core/`, `ui/`, `apps/` split from monolito.
    - `EventLoop` & `Bootstrap` modules for robust main loop and terminal setup.
    - `InputRouter` (Mouse/Key) to decouple event handling from main app logic.
    - `Rendering` module to centralize desktop/taskbar drawing.
- **Terminal Emulation**:
    - Embedded `TerminalWindow` with PTY support, ANSI parsing, and scrollback.
    - Theme integration: ANSI colors 0-7 now respect the active theme's background.
- **User Experience**:
    - **Context Menus**: Right-click support in Desktop, Notepad, File Manager, and Terminal.
    - **Movable Icons**: Drag & Drop desktop icons with persistence in `config.toml`.
    - **Global Clipboard**: Internal clipboard with sync to system (`wl-copy`/`xclip`).
    - **Drag & Drop**: Files to Notepad (open) or Terminal (paste path).
- **New Apps**:
    - `Settings`: Theme selector (Win3.1, Dos, Win95, Hacker, Amiga), live preview.
    - `Calculator`: Safe evaluator with history.
    - `Process Manager`: Live process list (htop-lite) with kill and sort.
    - `Log Viewer`: Tail-f mode, highlighting, vim-style search.
    - `Clock`: Digital clock + ASCII calendar with toggle.
    - `Hex Viewer`: Binary file inspection.
- **Quality & Dev**:
    - CI/CD pipeline with GitHub Actions (Linux/Windows).
    - 100% Module Coverage policy.
    - Type-safe action system (`AppAction` enum).

### Changed
- **Performance**:
    - Rendering optimizations (only draw dirty regions/windows).
    - Reduced input latency via normalized key handling.
- **Consistency**:
    - Unified menu system (`MenuBar`) for global and window-local menus.
    - Standardized keyboard shortcuts across all apps.

---

## [v0.6.0] - 2026-02-16

### Changed
- Bump de version del proyecto a `0.6.0` (`pyproject.toml`, runtime y script `setup.sh`).
- Sincronizacion de version en tests/documentacion de runtime (`README.md`, `ROADMAP.md`, `RELEASE.md`).
- Roadmap actualizado para reflejar estado actual: v0.4 completada, v0.5/v0.6 en progreso.

---

## [v0.3.6] - 2026-02-16

### Changed
- Bump de version del proyecto a `0.3.6` (`pyproject.toml`, runtime y script `setup.sh`).
- Sincronizacion de tests/documentacion para reflejar `v0.3.6`.

---

## [v0.3.5] - 2026-02-16

### Changed
- Bump de version del proyecto a `0.3.5` (`pyproject.toml`, runtime y script `setup.sh`).
- Elevacion del gate gradual de cobertura por modulo en CI a `--module-coverage-fail-under 50.0`.
- Cobertura por modulo elevada de 44.1% a 52.7% con nuevos tests de `retrotui.__main__`, `retrotui/core/content.py` y file I/O en apps.
- Sincronizacion de README/ROADMAP/PROJECT/RELEASE con el nuevo baseline de release y calidad.

---

## [v0.3.4] - 2026-02-16

### Changed
- Bump de version del proyecto a `0.3.4` (`pyproject.toml`, runtime y scripts de setup).
- Sincronizacion de cadenas de version en UI (`status bar`, dialogo About y welcome).
- Actualizacion de documentacion y preview para reflejar `v0.3.4`.
- Pipeline de input migrado a `get_wch()` con normalizacion comun de teclas (`normalize_key_code`).
- Manejo de teclado unificado para `Dialog`, `InputDialog`, `NotepadWindow` y `FileManagerWindow` con entradas `str`/`int`.

### Improved
- Ajustes editoriales de release notes para separar claramente `v0.3.4` (mantenimiento) de `v0.3.3` (refactor/hardening).
- I/O de Notepad fijado en UTF-8 para carga y guardado de archivos.
- Cobertura de tests ampliada para flujo de teclado Unicode y atajos Ctrl en ruta `get_wch()` (suite actual: 23 tests).

---

## [v0.3.3] — 2026-02-15

### Added
- **Estructura modular del paquete**: `retrotui/core`, `retrotui/ui`, `retrotui/apps`

### Fixed
- **Save As / Save Error**: flujo de guardado consistente con señales tipadas
- Corrección de import faltante en `InputDialog` (`C_WIN_BODY`)
- Eliminada doble instanciación de Notepad al abrir archivos

### Changed
- Refactor de enrutamiento de input: `handle_mouse()` y `handle_key()` divididos en helpers
- Contrato interno de acciones tipado (`ActionResult` / `ActionType`)
- Reemplazo de magic strings de acciones por enum `AppAction` en menus, apps e iconos
- Limpieza de artefactos Python (`.pyc`/`__pycache__`) del versionado
- Unificación de menús en `MenuBar` (global y ventana) con wrappers de compatibilidad
- Navegación del menú global delegada a `MenuBar.handle_key()`
- Documentación sincronizada a `v0.3.3` y normalización de encoding UTF-8 en docs clave

### Improved
- Reemplazo de `except Exception` genéricos en rutas internas por excepciones concretas
- Tests unitarios para navegación de `MenuBar` (separadores, ESC, LEFT/RIGHT, Enter)
- Smoke tests de integración de `MenuBar` para click global/ventana por coordenadas
- Logging básico de acciones (`execute_action`/dispatcher) con activación por `RETROTUI_DEBUG=1`

---

## [v0.3.2] — 2026-02-14

### Added
- **ASCII Video Player** — reproduce videos en terminal vía mpv (color) o mplayer (fallback)
- Icono "ASCII Vid" en escritorio y opción "ASCII Video" en menú File
- Detección automática de archivos de video desde File Manager (`.mp4`, `.mkv`, `.webm`, etc.)
- Método `play_ascii_video()` con manejo de errores y restauración de curses
- Helper `is_video_file()` con `VIDEO_EXTENSIONS` set

---

## [v0.3.1] — 2026-02-14

### Added
- **Barras de menú por ventana** estilo Windows 3.1 (File, View)
- Clase `WindowMenu` con dropdown, navegación por teclado y hover tracking
- FileManager: menú File (Open, Parent Dir, Close) + View (Hidden Files, Refresh)
- Notepad: menú File (New, Close) + View (Word Wrap)
- Indicador `≡` en title bar de ventanas con menú
- F10 abre menú de ventana activa (prioridad sobre menú global)
- Escape cierra menú de ventana primero, luego menú global
- Click fuera del dropdown lo cierra automáticamente

### Changed
- `body_rect()` se ajusta automáticamente cuando existe `window_menu`
- Resize mínimo dinámico (7 filas con menú, 6 sin menú)

---

## [v0.3] — 2026-02-14

### Added
- **Editor de texto (NotepadWindow)** con cursor, edición multilínea
- Word wrap toggle (Ctrl+W) con cache de líneas envueltas
- Abrir archivos desde File Manager en el editor (reemplaza visor read-only)
- **Resize de ventanas** — drag bordes inferior, derecho y esquinas
- **Maximize/Minimize** — botones `[─][□][×]` en title bar
- **Taskbar** para ventanas minimizadas (fila h-2)
- Doble-click en título = toggle maximize
- Notepad en menú File
- Status bar muestra ventanas visibles/total

### Changed
- Refactorización: `Window.draw()` → `draw_frame()` + `draw_body()`
- Tab cycling salta ventanas minimizadas

---

## [v0.2.2] — 2026-02-14

### Fixed
- Iconos rediseñados: ASCII art 3×4 con mejor contraste (negro sobre teal)
- Scroll wheel mueve selección en File Manager (antes solo scrolleaba viewport)
- Ventanas se reposicionan al redimensionar terminal
- Fix crash en Dialog antes del primer draw
- Fix scroll negativo en ventanas con poco contenido
- Limpieza de dead code y corrección de docs

---

## [v0.2.1] — 2026-02-14

### Fixed
- Fix double-click en iconos (ya no dispara dos acciones)
- Fix hover de menú dropdown (highlight sigue al mouse)
- Fix Ctrl+Q (deshabilitado XON/XOFF flow control)
- Fix drag de ventanas (release correcto con button-event tracking)

---

## [v0.2] — 2026-02-13

### Added
- **File Manager interactivo** con navegación de directorios
- Clase `FileManagerWindow` con estado de directorio y `FileEntry`
- Click en carpetas para navegar, ".." para subir
- **Visor de archivos** — abre archivos de texto en ventana read-only
- Selección con highlight (blanco sobre azul, estilo Win3.1)
- Teclado: ↑↓ selección, Enter abrir, Backspace padre, PgUp/PgDn, Home/End
- Toggle de archivos ocultos (tecla H)
- Detección de archivos binarios
- Auto-scroll para mantener selección visible
- Re-selección del directorio previo al navegar hacia arriba
- Delegación de eventos mouse/teclado por ventana (`handle_click`/`handle_key`)

---

## [v0.1] — 2026-02-13

### Added
- **Escritorio** con patrón de fondo estilo Windows 3.1
- **Barra de menú** superior con reloj en tiempo real
- **Ventanas** con bordes dobles Unicode (╔═╗║╚═╝) y botón cerrar [×]
- **Soporte de mouse** sin X11: GPM para TTY, xterm protocol para emuladores
- Click para seleccionar, arrastrar ventanas, scroll wheel
- **Diálogos modales** (About, Exit confirmation)
- **Menú desplegable** con navegación por teclado (F10, ←→↑↓, Enter, Escape)
- **Iconos de escritorio** clickeables (doble-click para abrir)
- **ThemeEngine** — colores Win3.1 con soporte 256-color
- Navegación completa por teclado (Tab, Enter, Escape, Ctrl+Q)
- Archivo único (`retrotui.py`) — sin dependencias externas
