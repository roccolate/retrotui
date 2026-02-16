# Changelog

Todas las versiones notables de RetroTUI están documentadas aquí.

---

## [Unreleased]

### Added
- Script `tools/qa.py` para chequeos locales de UTF-8, compilacion y tests.
- Workflow `.github/workflows/ci.yml` para ejecutar QA en push/pull request.
- Hook local `.githooks/pre-commit` para correr QA antes de commitear.
- Tests `tests/test_core_app.py` para rutas criticas del dispatcher y hotkeys en `retrotui/core/app.py`.
- Archivos `.editorconfig` y `.gitattributes` para fijar UTF-8 y EOL consistentes.
- Módulos `retrotui/core/action_runner.py` y `retrotui/core/content.py` para separar responsabilidades de `retrotui/core/app.py`.
- Modulos `retrotui/core/mouse_router.py` y `retrotui/core/key_router.py` para desacoplar routing de input del core principal.
- Modulo `retrotui/core/rendering.py` para concentrar render del desktop/taskbar/statusbar/iconos.
- Modulo `retrotui/core/event_loop.py` para encapsular ciclo principal de draw/input/resize.
- Modulo `retrotui/core/bootstrap.py` para centralizar setup/cleanup de terminal y mouse.
- Tests unitarios `tests/test_bootstrap.py` y `tests/test_event_loop.py` para validar modulos extraidos del core.
- Tests unitarios `tests/test_key_router.py`, `tests/test_mouse_router.py` y `tests/test_rendering.py` para cobertura directa de routing/render modular.
- Tests unitarios `tests/test_action_runner.py` para validar ejecucion de `AppAction` en `core/action_runner.py`.
- Tests de file I/O edge cases en `tests/test_windows_logic.py` para `NotepadWindow._load_file()` y `FileManagerWindow._rebuild_content()`.
- Documento `RELEASE.md` con politica de versionado, checklist y tagging.
- Workflow `.github/workflows/release.yml` para automatizar release por tag/dispatch con build de artifacts.
- Script `tools/check_release_tag.py` para validar coherencia tag/version en release.
- Tests `tests/test_release_tag_tool.py` para validar el checker de tag de release.
- Script `tools/report_module_coverage.py` para reporte de cobertura por modulo (stdlib `trace` + AST).
- Tests `tests/test_module_coverage_tool.py` para validar utilidades del reporte de cobertura.
- Tests `tests/test_notepad_component.py` para cubrir rutas internas de wrap/cursor/draw/menu en Notepad.
- Modulo `retrotui/core/terminal_session.py` con base PTY (spawn, lectura no bloqueante, resize y cierre) para iniciar v0.4.
- Tests `tests/test_terminal_session.py` para validar el contrato de `TerminalSession` en rutas exito/error.
- Modulo `retrotui/apps/terminal.py` con `TerminalWindow` embebida (sesion PTY, parser ANSI/VT100 basico, forwarding de teclas y scrollback).
- Tests `tests/test_terminal_component.py` para validar render/input/scroll/menu/ciclo de vida de la terminal embebida.
- Modulo `retrotui/core/clipboard.py` con clipboard interno y sync opcional con `wl-copy/wl-paste`, `xclip` y `xsel`.
- Tests `tests/test_clipboard_core.py` para cubrir el contrato del clipboard (deteccion backend, copy/paste y fallbacks).
- Modulo `retrotui/theme.py` con `Theme` dataclass, roles semanticos y 5 temas built-in (`win31`, `dos_cga`, `win95`, `hacker`, `amiga`).
- Modulo `retrotui/core/config.py` para cargar/guardar `~/.config/retrotui/config.toml`.
- Modulo `retrotui/apps/settings.py` con ventana de Settings funcional (radio de tema, toggles, preview live, Save/Cancel).
- Tests `tests/test_theme_and_config.py` y `tests/test_settings_component.py` para cubrir v0.5.
- Drag and drop base entre apps: File Manager -> Notepad (abrir archivo) y File Manager -> Terminal (pegar ruta).
- Highlight visual de ventanas target durante operaciones de drag and drop.
- File Manager v0.8 base: panel lateral de preview/info, bookmarks por slots (1..4) con defaults y asignacion rapida.
- Undo de borrado en File Manager moviendo elementos a trash local (`~/.local/share/Trash/files`).
- Modo dual-pane en File Manager (dos paneles, `Tab` para foco interno y `F5/F4` para copiar/mover entre paneles).
- Preview de imagen en File Manager usando backend externo (`chafa` o `timg`) cuando disponible.
- Dialogo modal de progreso para operaciones largas de File Manager (copy/move/delete) con ejecucion en background y spinner de estado.
- Modulo `retrotui/apps/calculator.py` con evaluador seguro (`ast`), historial de expresiones, copy/paste de resultados y modo always-on-top.
- Tests `tests/test_calculator_component.py` para validar evaluacion, historial, input/cursor, clipboard y rendering de calculadora.
- Modulo `retrotui/apps/logviewer.py` con tail mode, highlighting por severidad, busqueda estilo vim y freeze/reanudar scroll.
- Modulo `retrotui/apps/process_manager.py` con monitoreo live de `/proc`, sort por CPU/MEM/PID y kill con confirmacion.
- Modulo `retrotui/apps/clock.py` con reloj, calendario ASCII, always-on-top y chime opcional.
- Tests `tests/test_logviewer_component.py`, `tests/test_process_manager_component.py` y `tests/test_clock_component.py`.

### Changed
- README actualizado con comandos de QA y activacion de hooks locales.
- ROADMAP/PROJECT_ANALYSIS actualizados para reflejar automatizacion de calidad.
- CI extendido a matriz Linux + Windows (Python 3.9/3.12).
- `RetroTUI.execute_action()` ahora delega en `execute_app_action()` para reducir acoplamiento del core.
- `RetroTUI.handle_mouse()` y `RetroTUI.handle_key()` ahora delegan en routers dedicados, reduciendo tamano y complejidad de `retrotui/core/app.py`.
- `RetroTUI.draw_desktop()`, `draw_icons()`, `draw_taskbar()` y `draw_statusbar()` delegan en funciones de render dedicadas.
- `RetroTUI.run()` ahora delega en `run_app_loop()` para separar loop principal del core.
- `RetroTUI.__init__()`/`cleanup()` ahora delegan setup y restauracion de terminal a `core/bootstrap.py`.
- `tools/qa.py` incluye verificacion de version sincronizada (`pyproject.toml` vs `retrotui/core/app.py`).
- `tools/qa.py` agrega modo opcional de cobertura por modulo (`--module-coverage`, `--module-coverage-top`, `--module-coverage-fail-under`).
- `tools/report_module_coverage.py` ahora normaliza rutas y mapea sufijos de paquete para reducir falsos negativos de cobertura en entornos Windows.
- CI eleva el gate gradual de cobertura por modulo a `--module-coverage-fail-under 100.0` (solo `ubuntu-latest` + Python `3.12`).
- Cobertura ampliada en rutas de core modularizado, menu/action runner/notepad/terminal/calculadora/apps utilitarias; suite actual en QA: 484 tests.
- Cobertura total por modulo actualizada a 100.0% (trace + AST).
- `AppAction.TERMINAL` deja de abrir placeholder y ahora instancia `TerminalWindow` real.
- `RetroTUI.set_active_window()` y `core/event_loop.py` ahora respetan `always_on_top` para mantener ventanas fijadas por encima del resto.
- `init_colors()` ahora consume el tema activo y aplica colores por roles semanticos.
- Todo el render de UI ahora consume keys de tema via helper (`desktop`, `window_title`, `status`, etc.) en lugar de color pairs crudos.
- `FileManagerWindow` y `NotepadWindow` ahora respetan defaults persistidos (`show_hidden`, `word_wrap_default`).
- Atajos de clipboard ajustados para evitar conflicto con `Ctrl+C`: copy en Notepad/File Manager via `F6`/`Insert`, paste en Notepad/Terminal via `Ctrl+V`.
- Notepad ahora soporta pegado multilinea en cursor y File Manager copia ruta completa de la entrada seleccionada.
- `retrotui/constants.py` fue normalizado para eliminar mojibake en bordes/iconos Unicode y estabilizar rendering de layout.
- `AppAction` y `ActionType` se ampliaron para incluir utilitarias v0.7 y confirmacion de kill (`REQUEST_KILL_CONFIRM`).
- `open_file_viewer()` ahora enruta archivos `.log/.out/.err` a `LogViewerWindow`.
- Mouse router/bootstrap ajustados para mejorar comportamiento en TTY (drag/resize y doble-click en iconos).

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
- Sincronizacion de README/ROADMAP/PROJECT/PROJECT_ANALYSIS/RELEASE con el nuevo baseline de release y calidad.

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
