# RetroTUI - Guia tecnica

Este documento describe la arquitectura y las decisiones tecnicas del proyecto.
Para instalacion/uso rapido, ver `README.md`.

## Mapa de documentacion

- `README.md`: instalacion, ejecucion y controles.
- `ROADMAP.md`: estado por versiones/hitos.
- `CHANGELOG.md`: historial de cambios.
- `RELEASE.md`: politica y checklist de releases.
- `preview.html`: preview interactiva en navegador (no requiere curses).

## Objetivo y principios

- Experiencia tipo Windows 3.1 en terminal (TUI), sin X11/Wayland.
- Preferir stdlib de Python; evitar dependencias Python externas.
- Mantener el runtime simple y testeable: gran parte de la logica se valida con unit tests usando un `fake curses`.

## Plataformas

- Runtime: Linux (o WSL) con `curses`/ncurses disponible en Python.
- Windows nativo: normalmente no existe el modulo `_curses`, por lo que RetroTUI no corre como app interactiva.
  Aun asi, CI y la suite de tests corren en Windows usando un modulo `curses` falso en `tests/`.

Notas:
- Algunas apps usan features especificas de Linux:
  - Process Manager lee `/proc`.
  - Mouse en TTY usa GPM (ver seccion "Mouse sin X11").
- En emuladores de terminal (SSH/tmux/screen/etc) el mouse funciona via protocolo xterm.

## Estructura del repositorio

```
retrotui/            paquete principal
  core/              event loop, routing de input, rendering, acciones, config
  ui/                widgets base (Window, Dialog, Menu)
  apps/              apps (file manager, notepad, terminal, etc)
tests/               suite de unit tests (incluye fake curses)
tools/               herramientas de QA y cobertura por modulo
.github/workflows/    CI y release
.githooks/            hook local opcional (pre-commit)
```

## Arquitectura del runtime

### Entry point y version

- `retrotui/__main__.py` es el entrypoint (`python -m retrotui` y script `retrotui`).
  - Usa `curses.wrapper(...)` para asegurar setup/cleanup del terminal.
  - `RETROTUI_DEBUG=1` habilita logging DEBUG.
- La version se sincroniza entre:
  - `pyproject.toml` -> `[project].version`
  - `retrotui/core/app.py` -> `APP_VERSION`
  - `retrotui/__init__.py` -> `__version__`

### Core: `retrotui/core/`

- `app.py`: clase `RetroTUI` (estado global, ventanas, menu global, dialogos, config, dispatch de acciones).
- `event_loop.py`: loop principal (draw/input/resize) separado de `RetroTUI`.
- `bootstrap.py`: configuracion/restauracion de `curses`, mouse y flow control.
- `key_router.py` / `mouse_router.py`: routing de eventos a menu/dialog/ventana/escritorio.
- `rendering.py`: helpers de render (desktop, iconos, taskbar, statusbar).
- `actions.py`: `ActionType`, `ActionResult`, `AppAction`.
- `action_runner.py`: ejecucion centralizada de acciones de apps.
- `content.py`: builders de contenido estatico (welcome/help/about).
- `config.py`: carga/guardado de `~/.config/retrotui/config.toml`.
- `terminal_session.py`: sesion PTY (spawn/I-O/resize/seniales) usada por la terminal embebida.

### UI: `retrotui/ui/`

- `window.py`: clase base `Window` (frame, botones, resize/maximize/minimize, z-order, scroll basico).
- `dialog.py`: dialogos modales (`Dialog`, `InputDialog`, `ProgressDialog`).
- `menu.py`: `MenuBar` unificado (global y por ventana) + wrappers `Menu`/`WindowMenu`.

### Apps: `retrotui/apps/`

- `filemanager.py`: file manager (modo dual-pane, operaciones, previews, progreso, undo a trash).
- `notepad.py`: editor de texto.
- `terminal.py`: terminal embebida (ANSI/VT100 basico + scrollback).
- `calculator.py`: calculadora con evaluador seguro via `ast`.
- `logviewer.py`: visor de logs con tail y busqueda.
- `process_manager.py`: monitor de procesos via `/proc`.
- `clock.py`: reloj/calendario con always-on-top y chime opcional.
- `image_viewer.py`: visor de imagen con backends externos (`chafa`/`timg`/`catimg`).
- `hexviewer.py`: visor hex read-only.
- `settings.py`: preferencias con preview live y persistencia en config.
- `trash.py`: papelera (vista acotada al trash del usuario; borrado permanente y vaciado).

## Mouse sin X11

RetroTUI funciona con mouse en dos escenarios:

1. Consola virtual Linux (tty1-tty6):
   - Requiere GPM (General Purpose Mouse).
   - GPM toma eventos desde `/dev/input/mice` y los expone via `/dev/gpmctl` para ncurses.
2. Emulador de terminal:
   - Usa el protocolo de xterm mouse tracking (secuencias de escape).

El runtime no necesita distinguirlos: ambos caminos terminan en la misma API `curses.getmouse()`.

## Configuracion persistente

- Archivo: `~/.config/retrotui/config.toml`
- Campos (minimos):
  - `theme`
  - `show_hidden`
  - `word_wrap_default`

La ventana Settings aplica cambios en vivo y persiste al confirmar (Save).

## Calidad, CI y convenciones

- Gate local y CI: `python tools/qa.py`
  - Valida UTF-8 en archivos de texto del repo
  - `compileall` para detectar errores de sintaxis
  - sincronizacion de version (pyproject/app)
  - suite de `unittest`
  - opcional: cobertura por modulo via stdlib `trace` (`tools/report_module_coverage.py`)
- CI: `.github/workflows/ci.yml` (matriz Linux/Windows; gate de cobertura por modulo en ubuntu + Python 3.12).
- Convenciones de texto:
  - `.editorconfig` y `.gitattributes` fuerzan UTF-8 y EOL LF.
  - `.githooks/pre-commit` es opcional para correr QA antes de commitear.

