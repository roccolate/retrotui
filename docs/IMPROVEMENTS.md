# RetroTUI — Improvement Plan

Auditoría técnica viva. Solo se listan los items abiertos; los cerrados viven en
`ROADMAP.md` (hitos v0.9.4 / v0.9.5) y en `git log`.

**Estado:** v0.9.4 hardening cerrado. v0.9.5 (Terminal 2D buffer + mouse
pass-through) cerrado. **v0.9.5.1 (pre-v0.9.6 audit + perf sweep, 116
fixes) cerrado.** Los items abiertos son v0.9.6 (certificación
cross-terminal) y v0.9.7 (session restore), que viven en `ROADMAP.md`.

**Última revisión:** 2026-06-30.

---

## Cerrados en este ciclo de auditoría (v0.9.5.1)

Pre-v0.9.6: pasada completa de auditoría + perf sobre `core/`, `apps/`
y `ui/`. Resultado: 4 commits, ~150 archivos tocados, 116 fixes.

### `core/` — 36 fixes (HIGH + MEDIUM + LOW)
- **Event loop**: inner `try` ahora captura `Exception` (log + continue)
  para que un hook de ventana bugueado no pueda eludir
  `app.cleanup()`. Re-validación no-fatal de resize. Los 3 walks de
  `app.windows` por iteración (`tick`, live, animated) consolidados
  en uno solo vía `_tick_and_probe_windows`.
- **IPC**: `IPCRouter.send` / `broadcast` capturan la familia `Exception`
  más amplia — un handler de plugin bugueado ya no mata el main
  thread.
- **Lifecycle**: `WindowManager.close_window` idempotente (re-entry
  safe). `get_active_window` O(1) vía puntero `_active_window`
  cacheado (antes era O(n)). `_active_window_menu_owner` se limpia
  defensivamente cuando la ventana desaparece.
- **ANSI state machine**: ya no fabrica `[0]`; los consumers aplican
  per-command defaults. OSC maneja `ESC` en el body (antes podía
  quedar atrapado en OSC state).
- **Mouse**: title-bar buttons (close/min/max) gatean en
  `_is_button1_click_event` (release) en vez de `_is_click_like` —
  press-then-drag-away cancela limpio.
- **Mouse wire**: `getmouse()` length-tolerant (`*_rest`,
  `bstate = _rest[-1]`). `ValueError`/`TypeError` capturados junto
  con `curses.error`.
- **Persistencia**: `app.shutdown_signal` → `128+signum` exit codes
  en `__main__.run()`. `show_welcome` propagado vía
  `apply_preferences`. Strings TOML por `toml_basic_string`; el
  icon-manager key quoting usa el helper compartido (antes faltaba
  `\n`/`\r`/`\t`).
- **Rendering**: `get_screen_pos(frame_size=...)`, `frame_size`
  threaded por todo `draw()` / `draw_frame` / `draw_body` /
  `draw_bar` / `draw_dropdown` / `draw_box` → `_bounds=` en
  `safe_addstr`. `draw_icons` ya no llama `getmaxyx()` por icono
  uncached.
- **Utils**: nuevos helpers `atomic_write_text`,
  `toml_basic_string`, `decode_toml_basic_string` (usados en
  toda la codebase).
- **24 LOW items**: per-row blank hoists, micro-cache para
  `_preview_symbol`, cancel-event para renders, etc.

### `apps/` + `ui/` — 65 fixes (HIGH + MEDIUM + LOW)
- **Notepad**: `open_path` pregunta antes de descartar cambios sin
  guardar (`REQUEST_SAVE_CONFIRM`). Todos los user-data writes
  (notepad, FM bookmarks, FM trash metadata, view-source temp
  files, game scores) ahora vía `atomic_write_text`. Undo stack ya
  no double-push en selection-replace.
- **Filemanager**: `FileEntry` cachea executable bit (no `os.access`
  por fila por draw). Drag wired en pane secundario. Split
  boundary unificado. `NPAGE`/`End` scroll math correcto. Rename
  preserva cursor en pane activo. `perform_delete_entry` ya no
  descarta el override. `create_file`/`create_directory` usan
  `FileExistsError` en vez de TOCTOU.
- **Terminal**: DCH caps row growth. Word-wrap scrolls alimentan
  el scrollback vía `set_scroll_sink`. `_alt_lines` resize
  O(rows²) → `O(1)`. `_max_scrollback_offset` O(n) → O(1).
- **RetroNet**: SSL warning muestra razón subyacente. Tab-bar click
  usa mismo chip layout que draw. `<a>` no cerrado ya no traga el
  resto de la página.
- **App manager / Settings / Control Panel**: `IconsWindow` save
  envuelto en try/except. `show_welcome` propagado correctamente.
  Toggles live aplican a ventanas abiertas.
- **Wifi manager**: `_finish_connect` usa SSID almacenado. `--ask`
  OSError ya no degrada a `password=` argv. `_scan_thread`/
  `_connect_thread` muertos eliminados.
- **Image viewer**: cancel-event para renders concurrentes. Cache
  sin stat en hit. Backend re-detect en invalidate.
- **Logviewer**: severity highlight bracket-only. `lines_lc`
  precomputado. `query_lc` / `basename` cacheados. `draw` ya no
  llama `_poll_for_updates` (antes reabría el log por redraw).
- **Hexviewer**: LRU 2-slot para tick/draw.
- **Process manager**: `ProcessLookupError` → `REFRESH` con
  mensaje.
- **Calculator**: layout defensivo cuando `bh < 12`.
- **`draw_box()` con `_bounds=`**: threaded por window/dialog/menu/
  app_manager. **ContextMenu** usa `try/finally` para el attr
  stack. **4 game `draw()` overrides** aceptan `frame_size=None`.
- **22 LOW items** en apps/ui.

### Perf — 12 fixes
- `WindowManager._active_window` pointer (get_active O(1)).
- `PaneState` name index (select_by_name O(1)).
- FM preview stat cache (mtime_ns+size keyed).
- Per-row " " * bw hoists across multiple apps.
- Module-level compiled regexes (markdown viewer, retronet).
- `inspect.signature` cacheado en app tras primer call.
- Sysmon graph: snapshot slice + list+join.
- `/proc/meminfo` abierto una sola vez.
- 3× `app.windows` walks consolidados en 1.
- **Notepad per-line wrap cache (M15)**: `_wrap_line_cache[i]`
  paralelo a `self.buffer`; `_invalidate_wrap(line_idx=None)`;
  `_sync_wrap_cache_to_buffer()`. Single-char edit: O(stale_lines)
  en vez de O(buffer_length). **Micro-benchmark (2000-line file,
  1-char + draw): 30.5ms → 0.27ms (~113× speedup).**
- **Hidden-CSV parser cache (M11)**: `@lru_cache(maxsize=32)` sobre
  la raw string. **Micro-benchmark (50-token CSV, 5000 lookups):
  4.5ms → 0.1ms (~45× speedup).**

### Added
- `tests/test_perf_cache_stress.py` — 7 stress tests para los caches
  M15 y M11: large buffer + 200 single-char edits + 200 draws;
  5000-line buffer + many insert/delete; cache invalidation on
  string change; large CSV perf.

---

## Cerrados en este ciclo de auditoría

### Limpieza final — 2026-06-19

- **Pasada archivo por archivo**: inventario de 276 archivos versionados,
  scans mecánicos de rutas locales, versiones viejas, parsing inseguro de
  entorno, subprocess, excepciones amplias y lecturas de sistema; revisión
  manual de los focos señalados.
- **Complejidad accidental reducida**: se corrigieron fallos concretos sin
  refactors masivos: version sync en QA/release, rutas absolutas en tests,
  variables de entorno inválidas que podían romper imports/runtime, lecturas
  `/proc` con encoding tolerante y fixtures de smoke desfasadas.
- **QA de cierre**: `python3 tools/qa.py` pasa con 1084 tests, `git diff
  --check` queda limpio y `python3 tools/check_release_tag.py --tag v0.9.5`
  valida todas las fuentes de versión.

### Terminal — v0.9.5 cerrado

- **2D buffer wiring (HIGH)**: `TerminalWindow` ahora delega en
  `TerminalScreen` (que posee dos `TerminalScreenBuffer`, normal + alt) en
  vez de mantener `_scroll_lines + _line_cells + _alt_lines` propios. El
  state machine ANSI escribe vía `screen.put_char` / `line_feed` /
  `clear_screen`; la posición del cursor la lee el renderer del buffer;
  el scrollback se captura en cada newline vía un wrapper
  `_ScrollbackBuffer`. Properties `_line_cells`/`_scroll_lines`/
  `_cursor_col`/etc. mantienen el contrato legacy para callers externos.
  13 tests en `tests/test_terminal_buffer_wiring.py`.
- **Cursor real + atributos por celda (HIGH)**: la API del buffer ya
  expone `cursor_row/cursor_col` y los atributos por celda que el
  `_draw_live_cursor` lee directamente. La selección/copy ya tenía
  roundtrip con `_line_cells` rstrípeado, así que el wiring no requirió
  cambios adicionales en el sistema de selección.
- **Mouse pass-through (MED)**: `TerminalWindow` trackea los DEC private
  modes (`?1000h`, `?1002h`, `?1003h`, `?1005h`, `?1006h`, `?1015h`) en
  `_mouse_modes`. Cuando el hijo activa alguno, clicks/drags/scroll se
  codifican como secuencias SGR (`\e[<Cb;Cx;CyM`/`m`) y se reenvían al
  PTY vía `_forward_payload`. Press/release en cualquier modo,
  motion-with-button sólo con `?1002h`/`?1003h`, motion-without-button
  sólo con `?1003h`. 14 tests en `tests/test_terminal_mouse_passthrough.py`.
- **Compatibilidad GPM (MED)**: implícita en la rama "no mouse modes" del
  mismo handler. Cuando el hijo no activa mouse, RetroTUI conserva el
  mouse para selección/scrollback/menus (sea GPM en Linux console o SGR
  en xterm). Cubierto por `test_scroll_wheel_stays_in_retrotui_when_mouse_mode_off`
  y `test_click_without_mouse_mode_kept_by_retrotui`.

### RetroNet

- **HTML parser (MED)**: el regex en cascada de `apps/retronet.py` fue
  reemplazado por `_RetroNetHTMLParser` (basado en `html.parser.HTMLParser`).
  Tags anidados (`<b><i>x</i></b>`), entidades HTML (`&amp;`),
  `<script>`/`<style>`, `<input type="hidden">` y `<!DOCTYPE>`/comentarios
  ahora se manejan correctamente. 9 tests en `tests/test_retronet.py`.
- **Modernización del navegador**: tabs por ventana (Ctrl+T/W/I,
  Shift+Tab), bookmarks persistentes en `~/.config/retrotui/bookmarks.toml`
  (Ctrl+B/D), view source via temp file con path derivado del URL
  (Ctrl+U). 27 tests nuevos en `test_retronet.py`,
  `test_bookmarks_core.py`, `test_bookmarks_window.py`.

---

## Items abiertos (v0.9.6+)

Los items vivos están ahora en `ROADMAP.md` bajo los hitos
**v0.9.6 (Cross-terminal certification)** y **v0.9.7 (Session restore)**.
Esta auditoría queda cerrada para v0.9.4 y v0.9.5; las próximas
iteraciones comienzan un nuevo ciclo contra esos hitos.
