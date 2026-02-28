# RetroTUI — Roadmap

**Objetivo:** Un entorno de escritorio estilo Windows 3.1 completamente funcional para la terminal. Sin X11. Sin Wayland. Solo curses, una TTY y vibes.

**Estado actual:** v0.9.3 released.

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
- [x] 970 tests, 100% cobertura por modulo
- [x] Optimizaciones de rendering (cache de taskbar, window stats)

---

## Versiones Planificadas

### v0.9.4 — Session Restore y Pulido

Comportamiento de "sistema" mas robusto.

- [ ] Restauracion de sesion: recordar ventanas abiertas, posiciones, archivos abiertos
- [ ] Soft restart interno sin romper sesion host
- [ ] Deteccion de primera ejecucion con wizard de bienvenida
- [ ] Metadata de plugins visible en UI (version, capabilities)
- [ ] Pulir flujo boot/init/run/shutdown con comportamiento determinista

### v0.9.5 — Certificacion Cross-Terminal

Cerrar matriz de compatibilidad real.

- [ ] Matriz manual completa: Linux console, tmux, SSH (MobaXterm, Windows Terminal, terminales GUI)
- [ ] Capturar baselines en `docs/baseline/` para rendimiento y estabilidad
- [ ] Cerrar gaps GPM vs SGR en edge-cases de seleccion/drag/right-click
- [ ] Documentar desvios por terminal y mitigaciones
- [ ] Verificar soporte Windows nativo end-to-end (pywinpty + windows-curses)

### v0.9.6 — Apps Creativas

- [ ] Paintbrush — editor de ASCII art (brush, line, rect, fill, text)
- [ ] RetroCalc — visor/editor de CSV/TSV estilo VisiCalc
- [ ] Wallpaper — ASCII art o imagen como fondo de escritorio
- [ ] Sonido — terminal bell para feedback UI + efectos via `aplay`/`paplay`

### v0.9.7 — Menu Inicio y Temas Avanzados

La experiencia de escritorio completa.

- [ ] Start Menu estilo Windows — boton "Start" en taskbar, menu desplegable con apps y submenues
- [ ] TUI App Launcher — detectar apps TUI instaladas (`nvim`, `mc`, `htop`) y lanzarlas en ventana
- [ ] Tema Luna (Windows XP) — colores azul/verde/plateado, bordes redondeados
- [ ] Tema personalizable — editor de temas en vivo desde Settings

### v0.9.8 — Widgets Reutilizables

- [ ] Extraer widgets reutilizables a `widgets/` (checkbox, radio, text input, list, scrollbar)
- [ ] Simplificar apps existentes usando los widgets compartidos
- [ ] Documentar API de widgets para plugin developers

### v0.9.9 — Reservada

Reservada para absorber ideas nuevas despues de validar v0.9.4-v0.9.8.

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

*Ultima actualizacion: 27 de febrero de 2026*
