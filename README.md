# RetroTUI 🖥️

**Entorno de escritorio retro estilo Windows 3.1 para la terminal (Linux / WSL)**

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

## Estado del proyecto

- Versión actual: `0.6.0` (tag: `v0.6.0`).
- La rama `main` incluye trabajo posterior a la última release; el estado por hitos está en `ROADMAP.md`.

## Requisitos

- Linux (o WSL) con `curses`/ncurses disponible en Python.
- Python 3.9+.
- Terminal de al menos 80x24.
- Locale UTF-8 recomendado (si no, RetroTUI hace fallback a bordes ASCII).
- Sin dependencias Python externas.

> Nota sobre Windows: en Python para Windows normalmente no existe el módulo `curses` (el runtime de RetroTUI es Linux/WSL).
> Aun así, la suite de tests y `tools/qa.py` corren en Windows usando un `fake curses` para poder validar lógica no-interactiva.

## Instalación y ejecución

```bash
git clone https://github.com/roccolate/RetroTUI.git
cd RetroTUI

# (opcional) setup para Ubuntu minimal (Python, ncurses y GPM si estás en TTY)
bash setup.sh

# Ejecutar
python3 -m retrotui
```

Si lo instalas en editable:

```bash
python3 -m pip install -e .
retrotui
```

## Mouse (sin X11)

### Consola virtual (tty1–tty6)

Requiere **GPM**:

```bash
sudo apt install gpm
sudo systemctl enable --now gpm
```

### Emulador de terminal (SSH, tmux, screen, etc.)

Usa el protocolo de **xterm mouse tracking**. No requiere `gpm`.

## Extras opcionales (utilidades del sistema)

- ASCII Video Player: `mpv` (preferido) o `mplayer` (fallback).
- Image Viewer: `chafa` (preferido), `timg` o `catimg`.
- Clipboard sync: `wl-copy/wl-paste`, `xclip` o `xsel` (si están disponibles).

## Controles

### Global (teclado)
| Tecla         | Acción                     |
|---------------|----------------------------|
| `Tab`         | Ciclar foco entre ventanas |
| `Esc`         | Cerrar menú / diálogo      |
| `Enter`       | Activar selección          |
| `Ctrl+Q`      | Salir                      |
| `F10`         | Abrir/cerrar menú          |
| `Up/Down/Left/Right` | Navegar menús / scroll |
| `PgUp/PgDn`   | Scroll contenido           |

### File Manager
| Tecla         | Acción                              |
|---------------|-------------------------------------|
| `Up / Down`   | Mover selección                     |
| `Enter`       | Abrir directorio/archivo            |
| `Backspace`   | Directorio padre                    |
| `PgUp/PgDn`   | Selección por página                |
| `Home/End`    | Inicio / final de lista             |
| `F5`          | Copiar ítem seleccionado            |
| `F4`          | Mover ítem seleccionado             |
| `F2`          | Renombrar ítem seleccionado         |
| `Delete`      | Eliminar ítem seleccionado          |
| `F7`          | Crear carpeta                       |
| `F8`          | Crear archivo                       |
| `D`           | Toggle dual-pane (requiere >= 92 col) |
| `Tab`         | Cambiar panel activo (modo dual)    |
| `H`           | Toggle archivos ocultos             |
| `F6 / Ins`    | Copiar ruta seleccionada            |

### Notepad (editor de texto)
| Tecla         | Acción                           |
|---------------|----------------------------------|
| `Up/Down/Left/Right` | Mover cursor             |
| `Home/End`    | Inicio / fin de línea            |
| `PgUp/PgDn`   | Página arriba / abajo            |
| `Backspace`   | Borrar atrás                     |
| `Delete`      | Borrar adelante                  |
| `Enter`       | Nueva línea                      |
| `F6` / `Ins`  | Copiar línea actual              |
| `Ctrl+V`      | Pegar clipboard (multilínea)     |
| `Ctrl+W`      | Toggle word wrap                 |

### Terminal embebida
| Tecla         | Acción                       |
|---------------|------------------------------|
| `F6`          | Interrumpir proceso (SIGINT) |
| `F7`          | Terminar proceso (SIGTERM)   |
| `F8`          | Copiar selección             |
| `Ctrl+V`      | Pegar texto del clipboard    |
| `PgUp/PgDn`   | Scroll de scrollback         |

### Calculadora
| Tecla         | Acción                          |
|---------------|---------------------------------|
| `Enter`       | Evaluar expresión               |
| `Up / Down`   | Navegar historial               |
| `Ctrl+V`      | Pegar expresión desde clipboard |
| `F6 / Ins`    | Copiar último resultado         |
| `F9`          | Toggle always-on-top            |
| `Ctrl+L`      | Limpiar historial               |
| `Ctrl+Q`      | Cerrar calculadora              |

### Log Viewer
| Tecla         | Acción                       |
|---------------|------------------------------|
| `F6 / Ins`    | Copiar selección             |
| `F`           | Toggle follow tail           |
| `Space`       | Congelar/reanudar autoscroll |
| `/`           | Buscar texto                 |
| `n / N`       | Siguiente / anterior match   |
| `O`           | Abrir ruta (diálogo)         |
| `R`           | Recargar archivo             |
| `Home/End`    | Ir al inicio/fin del buffer  |
| `Q`           | Cerrar ventana               |

### Process Manager
| Tecla         | Acción                          |
|---------------|---------------------------------|
| `C`           | Ordenar por CPU                 |
| `M`           | Ordenar por memoria             |
| `P`           | Ordenar por PID                 |
| `K` / `Del`   | Solicitar kill con confirmación |
| `F5`          | Refrescar lista                 |
| `Up/Down`     | Mover selección                 |
| `PgUp/PgDn`   | Navegar por página              |
| `Q`           | Cerrar ventana                  |

### Image Viewer
| Tecla         | Acción                          |
|---------------|---------------------------------|
| `+ / -`       | Zoom in / zoom out              |
| `0`           | Reset zoom (100%)               |
| `O`           | Abrir imagen por ruta (diálogo) |
| `R`           | Recargar render                 |
| `Q`           | Cerrar ventana                  |

### Hex Viewer
| Tecla         | Acción                            |
|---------------|-----------------------------------|
| `F6 / Ins`    | Copiar selección                   |
| `Up/Down`     | Navegar por filas hex              |
| `PgUp/PgDn`   | Navegar por página                 |
| `Home/End`    | Ir al inicio / final               |
| `/`           | Buscar bytes/texto                 |
| `N`           | Siguiente match                    |
| `G`           | Ir a offset (decimal o 0xHEX)      |
| `O`           | Abrir archivo por ruta (diálogo)   |
| `Q`           | Cerrar ventana                     |

### Reloj / Calendario
| Tecla         | Acción                         |
|---------------|--------------------------------|
| `T`           | Toggle always-on-top           |
| `B`           | Toggle chime por hora          |
| `S`           | Semana inicia en domingo/lunes |
| `Q`           | Cerrar widget                  |

### ASCII Video Player (mpv / mplayer)
| Tecla         | Acción                              |
|---------------|-------------------------------------|
| `q`           | Salir del video y volver a RetroTUI |
| `Space`       | Pausa / reanudar                    |
| `Left/Right`  | Seek atrás / adelante               |

> Abre desde `File > ASCII Video` (diálogo de ruta y subtítulos opcionales). Usa `mpv --vo=tct` (color, preferido) o `mplayer -vo caca/aa` (fallback).

### Settings
| Tecla         | Acción                             |
|---------------|------------------------------------|
| `Up/Down`     | Mover selección                    |
| `Left/Right`  | Cambiar tema / alternar toggles    |
| `Enter/Space` | Activar opción (preview / Save / Cancel) |

### Trash
| Tecla         | Acción                             |
|---------------|------------------------------------|
| `Enter`       | Abrir directorio/archivo           |
| `Del`         | Eliminar permanentemente           |
| `E`           | Vaciar papelera                    |
| `R` / `F5`    | Refrescar                          |
| `Q`           | Cerrar ventana                     |

### Ventanas
| Acción             | Resultado                    |
|--------------------|------------------------------|
| Drag título        | Mover ventana                |
| Drag borde/esquina | Redimensionar ventana        |
| Click `[─]`        | Minimizar a taskbar          |
| Click `[□]`        | Maximizar / restaurar        |
| Click `[×]`        | Cerrar ventana               |
| Doble-click título | Toggle maximizar             |
| Click en taskbar   | Restaurar ventana minimizada |

### Mouse
| Acción            | Resultado             |
|------------------|-----------------------|
| Click            | Seleccionar / activar |
| Doble-click icono| Abrir aplicación      |
| Scroll wheel     | Scroll contenido      |

## Desarrollo

```bash
# Validaciones de encoding + compile + version sync + tests
python tools/qa.py

# Reporte opcional de cobertura por módulo (muestra los módulos con menor cobertura)
python tools/qa.py --module-coverage --module-coverage-top 10

# Gate de cobertura total por módulo (umbral actual en CI)
python tools/qa.py --module-coverage --module-coverage-top 10 --module-coverage-fail-under 100.0

# Activa hook local de pre-commit para correr QA automáticamente
git config core.hooksPath .githooks
```

- CI corre en GitHub Actions para Linux y Windows (Python 3.9 y 3.12): `.github/workflows/ci.yml`.
- El gate de cobertura por módulo (stdlib `trace`) se ejecuta en `ubuntu-latest` + Python `3.12`.
- Política de formato de texto (UTF-8 + LF) definida con `.editorconfig` y `.gitattributes`.
- Reporte de cobertura por módulo: `tools/report_module_coverage.py`.

## Documentación

- `ROADMAP.md`: roadmap y estado por versiones.
- `CHANGELOG.md`: historial de cambios.
- `PROJECT.md`: guía técnica y arquitectura.
- `RELEASE.md`: política y checklist de releases.
- `preview.html`: preview interactiva en navegador.

## New apps and icons

This release adds several small, self-contained applications (desktop icons and menu entries) useful for demos and utility workflows:

- `Minesweeper` — classic minesweeper game with safe-first-click placement and headless-friendly UI for tests.
- `Solitaire` — Klondike-like solitaire with auto-move/drain heuristics and optional auto-complete trigger.
- `Snake` — simple time-driven snake game with pause/resume support and legacy-compatible step behavior.
- `Charmap` — character map utility for browsing and inserting Unicode glyphs.
- `Clipboard Viewer` — read-only viewer for the system clipboard (supports common backends, falls back gracefully).
- `WiFi Manager` — lightweight scanner UI that uses `nmcli` when available and degrades safely when not present.

The icons for these apps are registered with the desktop layer and available in the main application menu.

## Licencia

MIT
