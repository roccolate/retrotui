# RetroTUI 🖥️

**Entorno de escritorio retro estilo Windows 3.1 para la consola de Linux**

```
╔══════════════════════════════════════════════════════════════╗
║ ≡ File   Edit   Help                            12:30:45   ║
╠══════════════════════════════════════════════════════════════╣
║░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║░░ 📁 ░░░░╔═══ File Manager ═══════════[─][□][×]╗░░░░░░░░░░║
║░ Files ░░║ 📂 /home/user                       ║░░░░░░░░░░║
║░░░░░░░░░░║ ──────────────────────────           ║░░░░░░░░░░║
║░░ 📝 ░░░░║  📁 Documents/                      ║░░░░░░░░░░║
║░Notepad░░║  📁 Downloads/                      ║░░░░░░░░░░║
║░░░░░░░░░░║  📄 readme.txt            2.4K      ║░░░░░░░░░░║
║░░ 💻 ░░░░║  📄 config.json           512B      ║░░░░░░░░░░║
║░Terminal░╚══════════════════════════════════════╝░░░░░░░░░░║
║░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║ RetroTUI v0.6.0│ Windows: 1/1 │ Mouse: Enabled │ Ctrl+Q: Exit║
╚══════════════════════════════════════════════════════════════╝
```

## Requisitos

- **Ubuntu Server / Minimal** (sin GUI)
- **Python 3.9+** (incluido en Ubuntu)
- **Sin dependencias externas** — usa solo `curses` (stdlib)

## Instalación

```bash
git clone <repo-url> retro-tui
cd retro-tui

# Para mouse en TTY (consola virtual, NO emulador de terminal):
sudo apt install gpm
sudo systemctl enable --now gpm

# Ejecutar:
python3 -m retrotui
```

## Calidad de desarrollo

```bash
# Ejecuta validaciones de encoding + compile + version sync + tests
python tools/qa.py

# Reporte opcional de cobertura por modulo (muestra modulos con menor cobertura)
python tools/qa.py --module-coverage --module-coverage-top 10

# Gate de cobertura total por modulo (umbral actual en CI)
python tools/qa.py --module-coverage --module-coverage-top 10 --module-coverage-fail-under 100.0

# Activa hook local de pre-commit para correr QA automaticamente
git config core.hooksPath .githooks
```

- CI corre en GitHub Actions para Linux y Windows (Python 3.9 y 3.12).
- CI aplica `--module-coverage-fail-under 100.0` de forma gradual (solo `ubuntu-latest` + Python `3.12`).
- Baseline QA actual: `484 tests` en verde y cobertura total por módulo `100.0%` (trace + AST).
- Politica de formato de texto definida con `.editorconfig` y `.gitattributes`.
- Politica de release/tagging en `RELEASE.md`.
- Release CI disponible en `.github/workflows/release.yml` (tag `vX.Y.Z` o dispatch manual).
- Reporte de cobertura por modulo disponible via `tools/report_module_coverage.py` (stdlib `trace`).

## Soporte de Mouse sin X11

RetroTUI funciona con mouse en **dos escenarios**:

### 1. Consola virtual (tty1–tty6)
Requiere **GPM** (General Purpose Mouse):
```bash
sudo apt install gpm
sudo systemctl start gpm
```
GPM intercepta eventos del mouse vía `/dev/input/mice` y los expone
a ncurses vía `/dev/gpmctl`. Soporta USB, PS/2 y serial.

### 2. Emulador de terminal (SSH, tmux, screen)
Usa el **protocolo xterm mouse tracking** — secuencias de escape que
los terminales modernos entienden nativamente. No requiere GPM.

Terminales compatibles: xterm, gnome-terminal, kitty, alacritty,
Windows Terminal (SSH), iTerm2, tmux, screen.

## Controles

### Teclado
| Tecla      | Acción                     |
|------------|----------------------------|
| `Tab`      | Ciclar foco entre ventanas |
| `Escape`   | Cerrar menú / diálogo      |
| `Enter`    | Activar selección          |
| `Ctrl+Q`   | Salir                      |
| `F10`      | Abrir menú                 |
| `↑ ↓ ← →`   | Navegar menús / scroll     |
| `PgUp/PgDn`| Scroll contenido           |

### File Manager
| Tecla         | Accion                      |
|---------------|-----------------------------|
| `Up / Down`   | Mover seleccion             |
| `Enter`       | Abrir directorio/archivo    |
| `Backspace`   | Directorio padre            |
| `PgUp/PgDn`   | Seleccion por pagina        |
| `Home/End`    | Inicio / final de lista     |
| `F5`          | Copiar item seleccionado    |
| `F4`          | Mover item seleccionado     |
| `F2`          | Renombrar item seleccionado |
| `Delete`      | Eliminar item seleccionado  |
| `F7`          | Crear carpeta               |
| `F8`          | Crear archivo               |
| `D`           | Toggle dual-pane (>= 92 col)|
| `Tab`         | Cambiar panel activo (dual) |
| `H`           | Toggle archivos ocultos     |
| `F6 / Ins`    | Copiar ruta seleccionada    |

### Notepad (Editor de Texto)
| Tecla         | Acción                     |
|---------------|----------------------------|
| `↑ ↓ ← →`    | Mover cursor               |
| `Home/End`    | Inicio / fin de línea      |
| `PgUp/PgDn`  | Página arriba / abajo      |
| `Backspace`   | Borrar atrás               |
| `Delete`      | Borrar adelante            |
| `Enter`       | Nueva línea                |
| `F6` / `Ins`  | Copiar línea actual        |
| `Ctrl+V`      | Pegar clipboard (multilínea) |
| `Ctrl+W`      | Toggle word wrap           |

### Terminal embebida
| Tecla         | Acción                        |
|---------------|-------------------------------|
| `Ctrl+V`      | Pegar texto del clipboard     |
| `PgUp/PgDn`  | Scroll de scrollback          |

### Calculadora
| Tecla         | Acción                            |
|---------------|-----------------------------------|
| `Enter`       | Evaluar expresión                 |
| `Up / Down`   | Navegar historial                 |
| `Ctrl+V`      | Pegar expresión desde clipboard   |
| `F6` / `Ins`  | Copiar último resultado           |
| `F9`          | Toggle always-on-top              |
| `Ctrl+L`      | Limpiar historial                 |
| `Ctrl+Q`      | Cerrar calculadora                |

### Log Viewer
| Tecla         | Acción                               |
|---------------|--------------------------------------|
| `F`           | Toggle follow tail                   |
| `Space`       | Congelar/reanudar autoscroll         |
| `/`           | Buscar texto                         |
| `n / N`       | Siguiente / anterior match           |
| `O`           | Abrir ruta (dialogo)                 |
| `R`           | Recargar archivo                     |
| `Home/End`    | Ir al inicio/fin del buffer          |
| `Q`           | Cerrar ventana                       |

### Process Manager
| Tecla         | Acción                               |
|---------------|--------------------------------------|
| `C`           | Ordenar por CPU                      |
| `M`           | Ordenar por memoria                  |
| `P`           | Ordenar por PID                      |
| `K` / `Del`   | Solicitar kill con confirmacion      |
| `F5`          | Refrescar lista                      |
| `Up/Down`     | Mover seleccion                      |
| `PgUp/PgDn`   | Navegar por pagina                   |
| `Q`           | Cerrar ventana                       |

### Reloj / Calendario
| Tecla         | Acción                               |
|---------------|--------------------------------------|
| `T`           | Toggle always-on-top                 |
| `B`           | Toggle chime por hora                |
| `S`           | Semana inicia en domingo/lunes       |
| `Q`           | Cerrar widget                        |

### ASCII Video Player (mpv / mplayer)
| Tecla         | Acción                              |
|---------------|-------------------------------------|
| `q`           | Salir del video y volver a RetroTUI |
| `Space`       | Pausa / reanudar                    |
| `← / →`       | Seek atrás / adelante               |

> Usa `mpv --vo=tct` (color, preferido) o `mplayer -vo caca/aa` (fallback).

### Ventanas
| Acción             | Resultado                    |
|--------------------|------------------------------|
| Drag título        | Mover ventana                |
| Drag borde/esquina | Redimensionar ventana        |
| Click `[─]`       | Minimizar a taskbar          |
| Click `[□]`       | Maximizar / restaurar        |
| Click `[×]`       | Cerrar ventana               |
| Doble-click título | Toggle maximizar             |
| Click en taskbar   | Restaurar ventana minimizada |

### Mouse
| Acción        | Resultado                |
|---------------|--------------------------|
| Click         | Seleccionar / activar    |
| Doble-click icono | Abrir aplicación     |
| Scroll wheel  | Scroll contenido         |

## Arquitectura

```
retrotui/      — Paquete principal (core/ui/apps)
preview.html   — Preview interactiva en browser
PROJECT.md     — Documentación técnica del proyecto
README.md      — Este archivo
```

### Componentes internos:
- **RetroTUI** — Clase principal, event loop
- **Window** — Ventanas con resize, maximize, minimize, z-order
- **NotepadWindow** — Editor de texto con word wrap (v0.3)
- **FileManagerWindow** — File Manager interactivo con navegación (v0.2)
- **TerminalWindow / TerminalSession** — Terminal embebida PTY con parser ANSI básico, forwarding de input y scrollback
- **CalculatorWindow** — Calculadora segura con evaluador `ast`, historial y modo always-on-top
- **LogViewerWindow** — visor de logs con tail, busqueda y highlighting por severidad
- **ProcessManagerWindow** — lista de procesos live desde `/proc`, sort y kill con confirmacion
- **ClockCalendarWindow** — widget de hora/fecha/calendario con chime opcional
- **FileEntry** — Entrada de archivo/directorio con metadata
- **MenuBar** — Menús globales y por ventana (unificados)
- **Dialog** — Diálogos modales
- **ActionResult/AppAction** — Contrato interno tipado para acciones
- **Action Runner / Content Builders** — ejecución de acciones y contenido estático desacoplados del `core/app.py`
- **Input Routers** — routing de mouse/teclado aislado en `retrotui/core/mouse_router.py` y `retrotui/core/key_router.py`
- **Rendering Helpers** — render de desktop/status/taskbar/iconos aislado en `retrotui/core/rendering.py`
- **Event Loop Helpers** — ciclo principal (`run`) aislado en `retrotui/core/event_loop.py`
- **Terminal Bootstrap** — setup/cleanup de `curses` y mouse tracking en `retrotui/core/bootstrap.py`
- **Clipboard Core** — clipboard interno compartido con sync opcional a `wl-copy/wl-paste`, `xclip` y `xsel`
- **ThemeEngine** — temas retro (`win31`, `dos_cga`, `win95`, `hacker`, `amiga`)

## Changelog

Ver [CHANGELOG.md](CHANGELOG.md) para el historial completo de versiones.

### Últimos cambios (v0.6.0)
- **Release v0.6.0** — versión sincronizada en runtime, package y setup.
- **Clipboard base inter-app** — copy con `F6`/`Ins` en Notepad y File Manager; paste con `Ctrl+V`.
- **Apps utilitarias v0.7** — Log Viewer (tail/busqueda/highlighting/freeze), Process Manager (/proc + sort + kill confirm), Calculadora, y Clock/Calendar (always-on-top + chime).
- **TTY/mouse** — fixes para drag/resize en consola y fallback robusto de doble-click en iconos de escritorio.
- **Calidad** — baseline actual: `484 tests` y cobertura por módulo `100.0%`.
- **Encoding/UI** — normalización de `retrotui/constants.py` para eliminar mojibake en bordes/iconos.

## Roadmap

- ~~**v0.1** - Escritorio, ventanas, menu, mouse, iconos~~
- ~~**v0.2** - File Manager funcional con navegacion~~
- ~~**v0.3** - Editor de texto, resize, maximize/minimize~~
- ~~**v0.4** - Terminal embebida (via pty)~~
- **v0.5** - Temas y configuracion (en progreso: motor de temas y settings listos)
- **v0.6** - Clipboard y comunicacion inter-app (clipboard + drag and drop base listos)
- **v0.7** - Apps utilitarias (log viewer, process manager, calculadora y clock/calendar listos)
- **v0.8** - File Manager avanzado (en progreso: dual-pane, previews (texto/imagen), info, bookmarks, undo y progreso de operaciones largas listos)
- **v0.9** - Media y hex editor
- **v1.0** - Empaquetado, plugins y documentacion

## Licencia
MIT
