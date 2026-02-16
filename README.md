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
║ RetroTUI v0.3.4│ Windows: 1/1 │ Mouse: Enabled │ Ctrl+Q: Exit║
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
python3 -m retrotui
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

### Notepad (Editor de Texto)
| Tecla         | Acción                     |
|---------------|----------------------------|
| `↑ ↓ ← →`    | Mover cursor               |
| `Home/End`    | Inicio / fin de línea      |
| `PgUp/PgDn`  | Página arriba / abajo      |
| `Backspace`   | Borrar atrás               |
| `Delete`      | Borrar adelante            |
| `Enter`       | Nueva línea                |
| `Ctrl+W`      | Toggle word wrap           |

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
- **FileEntry** — Entrada de archivo/directorio con metadata
- **MenuBar** — Menús globales y por ventana (unificados)
- **Dialog** — Diálogos modales
- **ActionResult/AppAction** — Contrato interno tipado para acciones
- **ThemeEngine** — Colores Win3.1 (256-color cuando disponible)

## Changelog

Ver [CHANGELOG.md](CHANGELOG.md) para el historial completo de versiones.

### Últimos cambios (v0.3.4)
- **Release de mantenimiento** — sincronización de versión y metadata del proyecto
- **Documentación/preview actualizados** y normalizados en UTF-8
- Se mantienen los hitos de v0.3.x: modularización base, menús por ventana, Notepad y ASCII Video

## Roadmap

- ~~**v0.1** — Escritorio, ventanas, menú, mouse, iconos~~ ✅
- ~~**v0.2** — File Manager funcional con navegación~~ ✅
- ~~**v0.3** — Editor de texto, resize, maximize/minimize~~ ✅
- **v0.4** — Terminal embebida (vía pty)
- **v0.5** — Temas (DOS/CGA, Win95, personalizado)
- **v1.0** — Configuración persistente, plugins

## Licencia

MIT
