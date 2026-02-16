# RetroTUI — Roadmap

**Objetivo:** Un entorno de escritorio estilo Windows 3.1 completamente funcional para la terminal Linux. Sin X11. Sin Wayland. Solo curses, una TTY y vibes.

**Estado actual:** v0.6.0 (febrero 2026)

---

## Versiones Completadas

### v0.1 — Escritorio y Ventanas ✅
- [x] Escritorio con patrón Win 3.1, barra de menú, reloj en tiempo real
- [x] Ventanas con bordes Unicode, arrastrar, cerrar [×]
- [x] Soporte de mouse sin X11 (GPM para TTY, xterm protocol para emuladores)
- [x] Diálogos modales, menú desplegable, iconos de escritorio
- [x] Navegación completa por teclado (Tab, F10, Enter, Escape, Ctrl+Q)

### v0.2 — File Manager ✅
- [x] Navegación de directorios, FileEntry con metadata
- [x] Teclado: selección, PgUp/PgDn, Home/End, toggle ocultos (H)
- [x] Visor de archivos de texto, detección de binarios
- [x] Delegación de eventos por ventana (handle_click/handle_key)

### v0.3 — Editor, Resize, Menús, Video ✅
- [x] NotepadWindow con cursor, edición multilínea, word wrap (Ctrl+W)
- [x] Guardar archivos (Ctrl+S), indicador de modificación (*) en título
- [x] Resize de ventanas (bordes/esquinas), maximize/minimize, taskbar
- [x] Barras de menú por ventana (WindowMenu) con hover tracking
- [x] ASCII Video Player — mpv --vo=tct (color) / mplayer fallback

---

## Versiones Planificadas

### v0.4 — Terminal Embebida & Refactor Interno

La release que hace RetroTUI usable como shell diario.

**Core: Terminal Embebida**
- [x] Base de sesion PTY en `retrotui/core/terminal_session.py` (spawn, I/O no bloqueante, resize, poll y cierre)
- [x] Ventana Terminal usando `pty.fork()` con parser de escape VT100/ANSI
- [x] Forwarding de input (keystrokes raw, secuencias Ctrl, señales)
- [x] Buffer de scrollback con soporte de scroll wheel
- [x] Múltiples instancias de terminal (cada una con su propio pty)
- [x] Detección de shell del usuario (`$SHELL` o fallback a `/bin/sh`)

**Refactor: Unificación de Menús**
- [x] Fusionar `Menu` y `WindowMenu` en una sola clase `MenuBar` con coordenadas configurables
- [x] Mover lógica de teclado del menú global inline a `MenuBar.handle_key()`
- [x] Eliminar código duplicado de hover/click/draw

**Refactor: Descomposición de Mouse Handler**
- [x] Dividir `handle_mouse()` en métodos auxiliares para routing por etapas
- [x] Formalizar orden de routing de eventos como pipeline claro
- [x] Extraer routing de mouse a `retrotui/core/mouse_router.py` para desacoplar `retrotui/core/app.py`

**Refactor: Descomposición de Keyboard Handler**
- [x] Extraer routing de teclado a `retrotui/core/key_router.py`
- [x] Mantener compatibilidad de contratos internos (`_handle_*`) delegando desde `RetroTUI`

**Refactor: Descomposición de Rendering**
- [x] Extraer render de desktop/iconos/taskbar/statusbar a `retrotui/core/rendering.py`
- [x] Mantener API publica de `RetroTUI` con wrappers (`draw_*`) para compatibilidad

**Refactor: Descomposición de Event Loop**
- [x] Extraer ciclo principal de ejecucion a `retrotui/core/event_loop.py`
- [x] Mantener `RetroTUI.run()` como wrapper estable hacia `run_app_loop()`

**Refactor: Bootstrap de Terminal**
- [x] Extraer inicializacion/restauracion de terminal a `retrotui/core/bootstrap.py`
- [x] Centralizar configuracion de mouse tracking y flow control (`XON/XOFF`)

**Refactor: Protocolo de Ventana**
- [x] Definir métodos base en Window: `handle_key()`, `handle_click()`, `handle_scroll()`
- [x] Eliminar chequeos duck-typing con `hasattr()` en routing de ventanas
- [x] Implementaciones default en Window (scroll contenido) para que subclases solo overrideen lo necesario

**Calidad**
- [x] Guard contra loop infinito en menus con solo separadores
- [x] Verificacion de tamano minimo de terminal al iniciar
- [x] Fix emojis en FileEntry para respetar `check_unicode_support()`
- [x] Pipeline de teclado consolidado para `get_wch()` con normalizacion de teclas compartida
- [x] Compatibilidad Unicode en input de Dialog/Notepad/File Manager y guardado UTF-8 en Notepad
- [x] Automatizacion de QA en CI/pre-commit (UTF-8, compileall, unittest) con matriz Linux/Windows
- [x] Politica de archivos de texto (UTF-8 + EOL LF) via `.editorconfig` y `.gitattributes`
- [x] Tests unitarios directos para modulos extraidos `core/event_loop.py` y `core/bootstrap.py`
- [x] Tests unitarios directos para `core/key_router.py`, `core/mouse_router.py`, `core/rendering.py` y `core/action_runner.py`
- [x] Politica de release/tagging documentada (`RELEASE.md`)
- [x] Verificacion automatica de version sync en QA (`pyproject.toml` vs `retrotui/core/app.py`)
- [x] Tests de manejo de errores de file I/O para Notepad/File Manager (PermissionError)
- [x] Workflow de release automatizado en GitHub Actions (`.github/workflows/release.yml`) con validacion de tag/version y build de artifacts
- [x] Reporte de cobertura por modulo con stdlib `trace` (`tools/report_module_coverage.py`) y opcion en QA
- [x] Umbral de cobertura por modulo en CI elevado a `--module-coverage-fail-under 100.0` (lane gradual en `ubuntu-latest` + Python `3.12`)
- [x] Baseline actual de calidad: `458 tests` en QA y cobertura total por modulo `100.0%`

---
### v0.5 — Temas y Configuración

Personalidad y persistencia.

**Motor de Temas**
- [x] Dataclass/dict `Theme` mapeando nombres semánticos a colores
- [x] Todos los draws referencian keys de tema, no color pairs crudos
- [x] `init_colors()` lee del tema activo
- [x] Temas built-in:
  - Windows 3.1 (actual, default)
  - DOS/CGA — fondo azul, texto amarillo, bordes simples
  - Windows 95 — paneles grises biselados, efecto 3D, barra Start
  - Hacker — verde sobre negro, patrón estilo Matrix
  - Amiga Workbench — naranja/azul/blanco con gradiente copper

**Configuración Persistente**
- [x] `~/.config/retrotui/config.toml`
- [x] Estado guardado: tema activo, mostrar ocultos, word wrap default
- [ ] Restaurar sesión: recordar ventanas abiertas, posiciones, archivos abiertos
- [ ] Detección de primera ejecución con wizard de bienvenida

**Ventana de Settings (funcional)**
- [x] Reemplazar placeholder actual con radio buttons y toggles funcionales
- [x] Preview de tema (aplicar en vivo, confirmar o revertir)
- [x] Guardar/cargar configuración

---

### v0.6 - Clipboard y Comunicacion Inter-App

Hacer que las apps se sientan como un entorno integrado.

**Clipboard Interno**
- [x] Atajos de copy/paste sin depender de Ctrl+C (base funcional)
- [x] Copiar texto desde Notepad, pegar en Terminal u otro Notepad
- [x] Copiar nombre/ruta desde File Manager
- [x] Sync con xclip/xsel/wl-copy cuando este disponible (clipboard SSH)

**Drag and Drop**
- [x] Arrastrar archivo de File Manager a Notepad -> abrir archivo
- [x] Arrastrar archivo de File Manager a Terminal -> pegar ruta
- [x] Feedback visual durante drag (highlight drop targets)

**Limpieza del Sistema de Acciones**
- [x] Reemplazar magic strings (`'filemanager'`, `'np_save'`, etc.) con enum `Action`
- [x] Formalizar protocolo de retorno con dataclass: `ActionResult(type, payload)`
- [x] Dispatcher centralizado de acciones con logging para debug

---

### v0.7 — Aplicaciones Utilitarias

Las apps que hacen que la gente quiera quedarse en RetroTUI.

**Log Viewer**
- [ ] Modo tail (`tail -f` equivalente) con auto-scroll
- [ ] Color highlighting: rojo ERROR, amarillo WARN, verde INFO
- [ ] Búsqueda con `/` (estilo vim)
- [ ] Abrir desde File Manager o por ruta desde diálogo
- [ ] Congelar/reanudar scroll

**Process Manager**
- [ ] Lista de tareas actualizada en vivo desde `/proc`
- [ ] CPU %, memoria, PID, nombre de comando
- [ ] Ordenar por columna (CPU, MEM, PID)
- [ ] Kill proceso con diálogo de confirmación
- [ ] Barra de resumen (uptime, load average, memoria total/usada)

**Calculadora**
- [x] Evaluador de expresiones usando `ast` de Python (eval seguro)
- [x] Historial de cálculos recientes
- [x] Ventana pequeña de tamaño fijo, opción always-on-top

**Reloj/Calendario**
- [ ] Widget pequeño mostrando hora + fecha
- [ ] Calendario ASCII del mes actual
- [ ] Toggle always-on-top
- [ ] Chime opcional en punto (terminal bell)

---

### v0.8 — File Manager Avanzado

Hacer el file manager competitivo con Midnight Commander.

**Operaciones de Archivo**
- [x] Copiar / mover / renombrar / eliminar con dialogos de confirmacion
- [x] Crear nuevo directorio / nuevo archivo
- [x] Diálogo de progreso para operaciones largas
- [x] Deshacer última operación (mover a trash)

**Modo Dual-Pane**
- [x] Dividir File Manager en dos paneles de directorio (estilo Norton Commander / mc)
- [x] Copiar/mover entre paneles
- [x] Tab para cambiar panel activo

**Previews de Archivos**
- [x] Preview de texto en panel lateral
- [x] Preview de imagen vía chafa o timg (renderizado ASCII art)
- [x] Panel de info: permisos, propietario, fecha de modificación, tipo MIME

**Bookmarks**
- [x] Acceso rápido a directorios frecuentes
- [x] ~, /, /var/log, /etc como defaults
- [x] Configurables por el usuario

---

### v0.9 — Media y Hex

Extender lo que se puede hacer sin salir del escritorio.

**Image Viewer**
- [ ] Abrir PNG/JPEG/GIF desde File Manager
- [ ] Renderizar usando chafa (preferido), timg o catimg como backend
- [ ] Zoom (renderizar a diferentes densidades de caracteres)
- [ ] Escalar a tamaño de ventana

**Hex Editor**
- [ ] Abrir archivos binarios desde File Manager (en vez de mostrar error "binary file")
- [ ] Layout tres columnas: offset | bytes hex | ASCII
- [ ] Navegación, búsqueda, go-to-offset
- [ ] Inicialmente read-only; modo edición como stretch goal

**Video Player Mejorado**
- [ ] Diálogo selector de archivos de video (sin requerir File Manager)
- [ ] Soporte de subtítulos (si mpv lo maneja)
- [ ] Overlay de controles de playback

---

### v1.0 — Empaquetado, Plugins y Documentación

Calidad de release.

**Empaquetado**
- [x] `pyproject.toml` con entry point de consola (comando `retrotui`)
- [ ] Publicación en PyPI para `pip install retrotui`
- [ ] Paquete `.deb` para Ubuntu/Debian
- [ ] Paquete AUR para Arch
- [ ] Opción auto-start: agregar a `.bash_profile` como reemplazo de login shell

**Modularización**
- [x] Separar monolito base en paquete Python:
  - `retrotui/core/` — event loop, window manager
  - `retrotui/apps/` — filemanager, notepad
  - `retrotui/ui/` — ventanas, menús y diálogos
- [ ] Completar separación adicional en `widgets/` reutilizables y `themes/` dedicados
- [x] Cada app principal como módulo autocontenido
- [x] API interna limpia para comunicación window manager ↔ app (`ActionResult` / `AppAction`)

**Sistema de Plugins**
- [ ] Directorio `~/.config/retrotui/plugins/`
- [ ] Manifiesto de plugin (nombre, versión, icono, entradas de menú)
- [ ] Clase base `RetroApp` que plugins subclassean
- [ ] Auto-discovery y carga al iniciar
- [ ] Plugin de ejemplo como template

**Documentación**
- [ ] README en inglés + español
- [ ] Guía de desarrollo de plugins
- [ ] Documento de arquitectura
- [ ] Man page (`man retrotui`)

---

## Ideas Futuras (Backlog)

Estas ideas no tienen versión asignada y se considerarán después de v1.0:

| Idea | Descripción |
|------|-------------|
| SSH File Manager | Navegar servidores remotos vía SFTP/paramiko |
| Cliente IRC/Chat | Cliente IRC integrado estilo retro |
| Cliente Email | Lector IMAP básico (read-only) con estética Win 3.1 |
| Screensaver | Starfield, flying toasters o maze después de idle |
| Sonido | Beeps vía PC speaker/terminal bell para feedback de UI |
| Escritorios múltiples | Cambio de desktops virtuales (Ctrl+Left/Right) |
| Temas comunitarios | Repositorio de temas de la comunidad |
| Scripting/macros | Sistema de scripting para automatización |
| Pipe integration | Pipar stdout de comandos de terminal a Notepad o Log Viewer |

---

*Última actualización: 16 de febrero de 2026*
