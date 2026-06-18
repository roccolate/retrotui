# RetroTUI — Roadmap

**Objetivo:** Un entorno de escritorio estilo Windows 3.1 completamente funcional para la terminal. Sin X11. Sin Wayland. Solo curses, una TTY y vibes.

**Estado actual:** v0.9.4 hardening en progreso sobre v0.9.3. Este roadmap prioriza estabilidad antes de nuevas features; la auditoria tecnica viva esta en [IMPROVEMENTS.md](IMPROVEMENTS.md).

---

## Versiones Completadas

### v0.1 — Escritorio y Ventanas

Escritorio con patron Win 3.1, ventanas con bordes Unicode, soporte de mouse (GPM + xterm), dialogos modales, menu desplegable, iconos de escritorio, navegacion completa por teclado.

### v0.2 — File Manager

File Manager interactivo con navegacion de directorios, visor de archivos de texto, deteccion de binarios, delegacion de eventos por ventana, teclado completo (seleccion, PgUp/PgDn, Home/End, toggle ocultos).

### v0.3 — Editor, Resize y Menus

NotepadWindow con cursor y edicion multilinea, word wrap (Ctrl+W), guardado (Ctrl+S). Resize de ventanas por bordes/esquinas, maximize/minimize, taskbar. Menus por ventana (WindowMenu) con hover tracking. ASCII Video Player.

### v0.4 — Terminal Embebida y Refactor

Terminal embebida con PTY (`pty.fork()`), parser ANSI, scrollback, multiples instancias. Refactor mayor: unificacion de menus en `MenuBar`, descomposicion de mouse/keyboard/rendering/event loop en modulos separados, bootstrap de terminal, protocolo formal de ventana. CI con cobertura 100% por modulo.

### v0.5 — Temas y Configuracion

Motor de temas con 5 temas built-in (Windows 3.1, DOS/CGA, Windows 95, Hacker, Amiga). Configuracion persistente en `~/.config/retrotui/config.toml`. Ventana de Settings con preview en vivo.

### v0.6 — Clipboard y Comunicacion Inter-App

Clipboard interno con sync a sistema (xclip/xsel/wl-copy). Drag-and-drop de archivos entre File Manager, Notepad y Terminal. Sistema de acciones tipado (`ActionResult`/`ActionType`/`AppAction`).

### v0.7 — Aplicaciones Utilitarias

Log Viewer (tail -f, highlighting, busqueda vim-style), Process Manager (live, sort, kill), Calculadora (evaluador seguro, historial), Reloj/Calendario (ASCII, always-on-top).

### v0.8 — File Manager Avanzado

Operaciones de archivo completas (copiar/mover/renombrar/eliminar con dialogos, progreso, undo via trash). Modo dual-pane estilo Norton Commander. Previews de archivos (texto, imagen, info). Bookmarks configurables.

### v0.9 — Media y Hex

Image Viewer (chafa/timg/catimg backend, zoom, escalado). Hex Viewer (offset/hex/ASCII, navegacion, busqueda). Video Player mejorado (selector de archivos, subtitulos).

### v0.9.1 — Apps Avanzadas y UX

Character Map, Markdown Viewer, System Monitor, Control Panel, Tetris, RetroNet Explorer. Context menus funcionales, persistencia de iconos de escritorio, optimizacion de startup, terminal styling.

### v0.9.2 — Plugin System y TTY Hardening

Plugin loader con `plugin.toml`, clase base `RetroApp`, auto-discovery, registro dinamico en desktop/menu. Plugin de ejemplo (`todo-list`). Guia de desarrollo (`docs/plugin-guide.md`). Hardening de TTY: captura de puntero, drag-drop normalizado, menu Plugins dinamico.

### v0.9.3 — Refactor, Plugins Bundled y Windows

**Modularizacion del core**
- [x] Descomposicion de `core/app.py` en 5 modulos (window_manager, action_runner, dialog_dispatch, drag_drop, file_operations)
- [x] Event bus, IPC y notificaciones integrados al core
- [x] Extraccion de context menu handler y mouse utils

**Migracion a plugins bundled**
- [x] 9 apps migradas de `apps/` a `bundled_plugins/` (charmap, clock, image-viewer, minesweeper, retronet, snake, solitaire, tetris, wifi-manager)
- [x] Se cargan via el plugin system, no hardcodeadas

**Refactor de apps**
- [x] Notepad: dispatch table (`_KEY_DISPATCH`) reemplaza if/elif de 217 lineas
- [x] File Manager: unificacion de pane state con `PaneState` + propiedades de compatibilidad
- [x] Terminal: eliminacion de dead code (`_dirty_lines`), fix de visibilidad de errores de sesion

**Soporte Windows nativo**
- [x] Backend PTY dual: POSIX (`pty.fork()`) + Windows (`pywinpty` ConPTY)
- [x] Dependencias condicionales en `pyproject.toml` (`windows-curses`, `pywinpty`)
- [x] Shim `win_termios.py` para flow control cross-platform

**Estilos de iconos**
- [x] 3 estilos de iconos de escritorio: default, mini, braille
- [x] Braille pixel art: iconos 8x12 renderizados como caracteres braille Unicode (4x3)
- [x] Iconos per-plugin via `[plugin.icon]` en `plugin.toml` (emoji + token)
- [x] Seleccion desde Settings con gallery preview

**Auto-refresh de plugins animados**
- [x] Mecanismo `needs_redraw` en `Window` para plugins con animacion
- [x] Timeout adaptativo (100ms) para ventanas animadas sin afectar idle (500ms)
- [x] Plugins animados se refrescan solos: aquarium, matrix, starwars, game-of-life, pomodoro, system-monitor, network-monitor

**Calidad**
- [x] 970 tests reportados para el release v0.9.3
- [x] 97 archivos de test en el arbol actual
- [x] Optimizaciones de rendering (cache de taskbar, window stats)

---

## Versiones Planificadas

### Criterio de realineacion

El proyecto queda realineado hacia una base estable antes de ampliar la superficie:

- Primero cerrar bloqueos, I/O en render, seguridad y consistencia de input.
- Despues fortalecer Terminal como ventana PTY confiable para apps TUI comunes.
- Luego certificar GPM/SGR/SSH/tmux/Windows con baselines reproducibles.
- Solo despues volver a features visibles como Session Restore, Start Menu, widgets y apps creativas.

### v0.9.4 — Hardening y Pulido

Antes de agregar grandes features, cerrar los problemas de robustez detectados en la auditoria.

- [x] Event loop con `tick()` por ventana fuera de `draw()`
- [x] Terminal: PTY start/read/resize fuera de render, resize cacheado, errores visibles sin spam, tabs de 8 columnas, CSI `H`/`f`/`J`, wrap en alt-screen, PageUp/PageDown para apps full-screen, F1-F12 basico, fallback de interrupcion simplificado
- [x] File Manager: `Path.touch()`, copia de directorios a destino exacto, bloqueo de operaciones sobre `..`, preview de imagen async, cache por stat, teclas normalizadas, tamaños GB/TB
- [x] Notepad: wrap por ancho de celda, cache de wrap visible, titulo cacheado, presupuesto de undo para archivos grandes, Ctrl+W persistente, context menu real
- [x] Perfil base minimo por defecto: solo File Manager/Explorer, Terminal y Notepad visibles; apps secundarias y plugins quedan deshabilitados por configuracion
- [x] Documentacion de auditoria actualizada con remediaciones cerradas
- [x] Suite actual verde: 946 tests + `tools/qa.py --skip-tests`
- [x] Corregir seguridad/thread-safety de RetroNet (state lock en url, history, content, title, search; dedup de history; SSL con fallback explícito)
- [x] Separar tick/update de `draw()` en Snake, Tetris, Process Manager, Hex Viewer, System Monitor, Clipboard Viewer, Image Viewer y WiFi Manager
- [x] Eliminar I/O bloqueante restante: WiFi Manager (hilos scan/connect), Image Viewer (hilo de render con cache), Hex Viewer (cache en tick), System Monitor (platform guard)
- [x] Normalizar manejo de teclas en Minesweeper, Tetris, Solitaire, Clipboard Viewer y WiFi Manager
- [x] Reducir imports repetidos en rutas calientes de render/input (charmap, control_panel, clipboard_viewer, wifi_manager)
- [x] Bundled plugins (9) propagan `title` del manifest a la ventana
- [x] Trash: nuevo dialogo dedicado para "Empty Trash" (`REQUEST_EMPTY_TRASH_CONFIRM`); restore con sidecar `.trashinfo`
- [x] Control Panel: toggle de `word_wrap_default` alcanzable; Settings usa `apply_preferences` consistente en Left/Right
- [x] App Manager `IconsWindow` delega a `super()` y cachea el catalogo
- [x] System Monitor: CPU history se reescala al redimensionar; plataforma no-Linux con mensaje claro
- [x] Hex Viewer: `_rows_visible` y `draw` consistentes; `_parse_search_query` captura `ValueError`
- [x] Log Viewer: matches incrementales al appendear; resaltado usa `A_BOLD` para no chocar con severity color
- [x] Process Manager: cmd sort, scroll_offset init, magic numbers extraidos a constantes, sin doble-click destructivo
- [x] Solitaire: foundation→column bloqueado (Klondike), double-click con ventana de 500ms
- [x] Tetris: restart usa `reset_game()` en vez de re-llamar `__init__`
- [x] Clock: `TextCalendar` cacheado por (year, month, first-weekday)
- [x] Markdown: italic, inline code, scroll wheel, estado `in_code_block` preservado al scrollear
- [x] Charmap: action `copy_hex` renombrada a `copy_char`/`copy_hex` con semantica correcta
- [x] Calculator: `RecursionError` capturado en eval
- [x] Cerrar polish restante en File Manager: `perform_undo` API, bookmarks persistentes, feedback para drag de directorios

### v0.9.5 — Terminal PTY y Buffer 2D

Convertir la Terminal embebida en una base fiable para apps TUI comunes sin salir de curses/GPM.

- [ ] Introducir `TerminalScreenBuffer` normal-screen `rows x cols`
- [ ] Mantener alt-screen separado de normal-screen y scrollback
- [ ] Cursor real por fila/columna en normal-screen
- [ ] Wrap, scroll, clear, insert/delete char/line y resize con pruebas unitarias
- [ ] Atributos por celda compatibles con seleccion/copy
- [ ] Mouse pass-through opcional solo cuando el programa hijo active mouse reporting
- [ ] Mantener compatibilidad GPM: RetroTUI conserva menus/seleccion cuando el hijo no pide mouse

### v0.9.6 — Certificacion Cross-Terminal

Cerrar matriz de compatibilidad real.

- [ ] Matriz manual completa: Linux console, tmux, SSH (MobaXterm, Windows Terminal, terminales GUI)
- [ ] Capturar baselines en `docs/baseline/` para rendimiento y estabilidad
- [ ] Cerrar gaps GPM vs SGR en edge-cases de seleccion/drag/right-click
- [ ] Documentar desvios por terminal y mitigaciones
- [ ] Verificar soporte Windows nativo end-to-end (pywinpty + windows-curses)

### v0.9.7 — Session Restore

Comportamiento de "sistema" mas robusto.

- [ ] Restauracion de sesion: recordar ventanas abiertas, posiciones, archivos abiertos
- [ ] Soft restart interno sin romper sesion host
- [ ] Deteccion de primera ejecucion con wizard de bienvenida
- [ ] Metadata de plugins visible en UI (version, capabilities)
- [ ] Pulir flujo boot/init/run/shutdown con comportamiento determinista

### v0.9.8 — Widgets Reutilizables

- [ ] Extraer widgets reutilizables a `widgets/` (checkbox, radio, text input, list, scrollbar)
- [ ] Simplificar apps existentes usando los widgets compartidos
- [ ] Documentar API de widgets para plugin developers

### v0.9.9 — Menu Inicio y Temas Avanzados

La experiencia de escritorio completa.

- [ ] Start Menu estilo Windows — boton "Start" en taskbar, menu desplegable con apps y submenues
- [ ] TUI App Launcher — detectar apps TUI instaladas (`nvim`, `mc`, `htop`) y lanzarlas en ventana
- [ ] Tema Luna (Windows XP) — colores azul/verde/plateado, bordes redondeados
- [ ] Tema personalizable — editor de temas en vivo desde Settings

### v0.10.0 — Apps Creativas

- [ ] Paintbrush — editor de ASCII art (brush, line, rect, fill, text)
- [ ] RetroCalc — visor/editor de CSV/TSV estilo VisiCalc
- [ ] Wallpaper — ASCII art o imagen como fondo de escritorio
- [ ] Sonido — terminal bell para feedback UI + efectos via `aplay`/`paplay`

### v0.x — Reservada

Reservada para absorber ideas nuevas despues de validar v0.9.4-v0.10.0.

---

### v1.0.0 — Release Formal

Calidad de release. Publicacion y empaquetado.

- [x] `pyproject.toml` con entry point de consola (`retrotui`)
- [ ] Publicacion en PyPI (`pip install retrotui`)
- [ ] Metadata completa: classifiers, keywords, URLs, LICENSE
- [ ] Paquete `.deb` para Ubuntu/Debian
- [ ] Paquete AUR para Arch
- [ ] Man page (`man retrotui`)
- [ ] Opcion auto-start: agregar a `.bash_profile` como reemplazo de login shell

---

## Vision a largo plazo

### Post-1.0 — RetroTUI como Login Shell

RetroTUI como shell de login: al abrir la terminal, aparece el escritorio.

- [ ] Auto-start como login shell (`/etc/shells` + `chsh`)
- [ ] Script de provision para Raspberry Pi / thin clients
- [ ] System tray en taskbar: bateria, WiFi, volumen (extiende `NotificationManager` existente)
- [ ] Notificaciones del SO via event bus (bateria baja, updates disponibles)

---

## Ideas Futuras (Backlog)

Ideas sin version asignada, se consideraran segun prioridad.

| Categoria | Idea | Descripcion |
|---|---|---|
| Apps | Music Player | Wrapper `mpv --no-video` o `cmus` en ventana PTY |
| Apps | SSH File Manager | Navegar servidores remotos via SFTP/paramiko |
| UX | Screensaver | Starfield, flying toasters, maze despues de idle (plugin) |
| UX | Escritorios multiples | N listas de ventanas con Ctrl+Left/Right para cambiar |
| UX | Temas comunitarios | Repositorio de archivos TOML con temas de la comunidad |
| Sistema | Pipe integration | stdout de terminal -> Notepad o Log Viewer |

---

*Ultima actualizacion: 15 de junio de 2026*
