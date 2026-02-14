# RetroTUI 🖥️

**Entorno de escritorio retro estilo Windows 3.1 para la consola de Linux**

```
╔══════════════════════════════════════════════════════════════╗
║ ≡ File   Edit   Help                            12:30:45   ║
╠══════════════════════════════════════════════════════════════╣
║░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║░░ 📁 ░░░░╔═══ File Manager ══════════════════════════╗░░░░░║
║░ Files ░░║ 📂 /home/user                             ║░░░░░║
║░░░░░░░░░░║ ────────────────────────────────           ║░░░░░║
║░░ 📝 ░░░░║  📁 Documents/                            ║░░░░░║
║░Notepad░░║  📁 Downloads/                            ║░░░░░║
║░░░░░░░░░░║  📄 readme.txt              2.4K          ║░░░░░║
║░░ 💻 ░░░░║  📄 config.json             512B          ║░░░░░║
║░Terminal░╚════════════════════════════════════════════╝░░░░░║
║░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░║
║ RetroTUI v0.2.2 │ Windows: 1 │ Mouse: Enabled │ Ctrl+Q: Exit║
╚══════════════════════════════════════════════════════════════╝
```

## Requisitos

- **Ubuntu Server / Minimal** (sin GUI)
- **Python 3.8+** (incluido en Ubuntu)
- **Sin dependencias externas** — usa solo `curses` (stdlib)

## Instalación

```bash
git clone <repo-url> retro-tui
cd retro-tui

# Para mouse en TTY (consola virtual, NO emulador de terminal):
sudo apt install gpm
sudo systemctl enable --now gpm

# Ejecutar:
python3 retrotui.py
```

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
| Tecla         | Acción                     |
|---------------|----------------------------|
| `↑ / ↓`      | Mover selección            |
| `Enter`       | Abrir directorio/archivo   |
| `Backspace`   | Directorio padre           |
| `PgUp/PgDn`  | Selección por página       |
| `Home/End`    | Inicio / final de lista    |
| `H`           | Toggle archivos ocultos    |

### Mouse
| Acción        | Resultado                |
|---------------|--------------------------|
| Click         | Seleccionar / activar    |
| Drag título   | Mover ventana            |
| Click `[×]`   | Cerrar ventana           |
| Doble-click icono | Abrir aplicación     |
| Scroll wheel  | Scroll contenido         |

## Arquitectura

```
retrotui.py    — Aplicación principal (archivo único)
preview.html   — Preview interactiva en browser
PROJECT.md     — Documentación técnica del proyecto
README.md      — Este archivo
```

### Componentes internos:
- **RetroTUI** — Clase principal, event loop
- **Window** — Ventanas arrastrables con z-order
- **FileManagerWindow** — File Manager interactivo con navegación (v0.2)
- **FileEntry** — Entrada de archivo/directorio con metadata
- **Menu** — Sistema de menú desplegable
- **Dialog** — Diálogos modales
- **ThemeEngine** — Colores Win3.1 (256-color cuando disponible)

## Novedades en v0.2

- **File Manager interactivo** con navegación de directorios
- Click en carpetas para navegar, ".." para subir
- **Visor de archivos** — abre archivos de texto en Notepad read-only
- Selección con highlight (↑↓, Enter, Backspace)
- Toggle de archivos ocultos (H)
- Detección de archivos binarios
- Delegación de eventos por ventana (extensible)

## Roadmap

- ~~**v0.2** — File Manager funcional con navegación~~ ✅
- **v0.3** — Editor de texto integrado
- **v0.4** — Terminal embebida (vía pty)
- **v0.5** — Temas (DOS/CGA, Win95, personalizado)
- **v1.0** — Configuración persistente, plugins

## Licencia

MIT
