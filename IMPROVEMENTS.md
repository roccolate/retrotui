# RetroTUI — Improvement Plan

Auditoría técnica viva. Solo se listan los items abiertos; los cerrados viven en
`ROADMAP.md` (hitos v0.9.4 / v0.9.5) y en `git log`.

**Estado:** v0.9.4 hardening cerrado. **v0.9.5 (Terminal 2D buffer + mouse
pass-through) cerrado.** Los items abiertos son v0.9.6 (certificación
cross-terminal) y v0.9.7 (session restore), que viven en `ROADMAP.md`.

**Última revisión:** 2026-06-19.

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
