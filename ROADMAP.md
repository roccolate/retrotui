# RetroTUI — Roadmap

**Objetivo:** Un entorno de escritorio estilo Windows 3.1 completamente funcional para la terminal Linux. Sin X11. Sin Wayland. Solo curses, una TTY y vibes.

**Estado actual:** v0.9.0 estable — roadmap definido hasta v1.0 (febrero 2026)

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

### v0.4 — Terminal Embebida & Refactor Interno ✅

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
- [x] Baseline actual de calidad: suite de tests en verde y cobertura total por modulo `100.0%`

---
### v0.5 — Temas y Configuración ✅

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

### v0.6 - Clipboard y Comunicacion Inter-App ✅

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

### v0.7 — Aplicaciones Utilitarias ✅

Las apps que hacen que la gente quiera quedarse en RetroTUI.
Estado: checklist completado en codigo; pendiente empaquetado/release formal.

**Log Viewer**
- [x] Modo tail (`tail -f` equivalente) con auto-scroll
- [x] Color highlighting: rojo ERROR, amarillo WARN, verde INFO
- [x] Búsqueda con `/` (estilo vim)
- [x] Abrir desde File Manager o por ruta desde diálogo
- [x] Congelar/reanudar scroll

**Process Manager**
- [x] Lista de tareas actualizada en vivo desde `/proc`
- [x] CPU %, memoria, PID, nombre de comando
- [x] Ordenar por columna (CPU, MEM, PID)
- [x] Kill proceso con diálogo de confirmación
- [x] Barra de resumen (uptime, load average, memoria total/usada)

**Calculadora**
- [x] Evaluador de expresiones usando `ast` de Python (eval seguro)
- [x] Historial de cálculos recientes
- [x] Ventana pequeña de tamaño fijo, opción always-on-top

**Reloj/Calendario**
- [x] Widget pequeño mostrando hora + fecha
- [x] Calendario ASCII del mes actual
- [x] Toggle always-on-top
- [x] Chime opcional en punto (terminal bell)

---

### v0.8 — File Manager Avanzado ✅

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

### v0.9 — Media y Hex ✅

**Image Viewer**
- [x] Abrir PNG/JPEG/GIF desde File Manager
- [x] Renderizar usando chafa (preferido), timg o catimg como backend
- [x] Zoom (renderizar a diferentes densidades de caracteres)
- [x] Escalar a tamaño de ventana

**Hex Editor**
- [x] Abrir archivos binarios desde File Manager (en vez de mostrar error "binary file")
- [x] Layout tres columnas: offset | bytes hex | ASCII
- [x] Navegación, búsqueda, go-to-offset
- [x] Inicialmente read-only; modo edición como stretch goal

**Video Player Mejorado**
- [x] Diálogo selector de archivos de video (sin requerir File Manager)
- [x] Soporte de subtítulos (si mpv lo maneja)
- [x] Overlay de controles de playback

---

## Versiones Planificadas

### v0.9.1 — Ultimate Release ✅

La versión definitiva pre-1.0 con utilidades avanzadas y refinamiento de UX.

**Apps & Games**
- [x] 🔠 Character Map — Overhaul completo con categorías y soporte Unicode extendido
- [x] 📖 Markdown Viewer — Renderizado de archivos .md con formato y navegación
- [x] 📊 System Monitor — Dashboard de rendimiento (CPU, RAM, Disk)
- [x] ⚙️ Control Panel — Configuración centralizada del sistema
- [x] 🕹️ Tetris — Juego clásico integrado con sistema de puntos y niveles
- [x] 🌐 RetroNet Explorer Ultra — Navegador web de texto premium con modo sidecar, RichLine y scrollbar

**UX & Core**
- [x] Context Menu — Menú contextual (clic derecho) funcional
- [x] Desktop Persistence — Iconos de escritorio guardan/cargan posición
- [x] Startup Optimization — Eliminación de intro vBIOS para carga instantánea
- [x] Terminal Styling — Bordes y sombreados mejorados para todas las ventanas

---

### v0.9.2 — Plugin System ✅

Extensibilidad para la comunidad. Branch: `feature/plugins`

**Core**
- [x] Plugin loader — escanea `~/.config/retrotui/plugins/`
- [x] Manifiesto `plugin.toml` (nombre, versión, icono, menú)
- [x] Clase base `RetroApp` (wrapper ergonómico sobre `Window`)
- [x] Auto-discovery y registro dinámico en desktop/menú (no crashea la app si un plugin falla)
- [x] Plugin de ejemplo (`todo-list`) incluido como template

**Integración y pruebas**
- [x] Apertura de plugins desde menú/acciones (`plugin:<id>`) y iconos dinámicos
- [x] Tests unitarios: `tests/test_plugin_loader.py`, `tests/test_plugin_base.py`, `tests/test_plugin_example.py`
- [x] QA local: `tools/qa.py` (UTF-8, compileall, unit tests, version sync) — verde

**Documentación**
- [x] Guía de desarrollo de plugins (`docs/plugin-guide.md`)

Notas: Implementado en la rama `feature/plugins` (commit `84c3376`). QA: todos los checks locales pasaron el 21 de febrero de 2026.

**Ideas de plugins (comunidad / contribuidores)**

*Productividad:*
- [x] 📝 Todo List — Tareas con prioridades, fechas, checkboxes (example plugin enhanced)
- [x] 🍅 Pomodoro Timer — Temporizador 25/5 con bell y historial (scaffolded + persistence)
- [x] 📌 Sticky Notes — Post-its en el escritorio que persisten entre sesiones (scaffolded)
- [x] 📇 Contacts / Cardfile — Mini CRM: nombre, teléfono, email, notas (scaffolded)
- [x] 📰 RSS Reader — Leer feeds RSS/Atom en ventana retro (scaffolded)

*Sistema:*
- [x] 💾 Disk Usage — Visualización de uso de disco estilo `ncdu` (scaffolded)
- [x] 📊 System Monitor — Dashboard: CPU, RAM, disco, uptime, temperatura (scaffolded)
- [x] 🌐 Network Monitor — Ancho de banda, conexiones activas, ping (scaffolded)
- [x] ⚙️ Service Manager — Start/stop/restart servicios `systemd` (scaffolded)
- [x] 🕐 Cron Editor — Editar crontab con interfaz visual (scaffolded)

*Entretenimiento:*
- [x] 🥠 Fortune Cookie — Frase aleatoria al abrir (como `fortune`) (scaffolded)
- [x] 🐠 ASCII Aquarium — Pecera animada como screensaver/widget (scaffolded)
- [x] 🧬 Conway's Game of Life — Autómata celular interactivo (scaffolded)
- [x] 🌤️ Weather Widget — Clima actual vía `wttr.in` (scaffolded)
- [x] 🟢 Matrix Rain — Efecto Matrix como screensaver (scaffolded)

*Desarrollo:*
- [x] 🔀 Git Status — Branch, commits recientes, diff viewer (scaffolded)
- [x] 📄 JSON Viewer — Explorar archivos JSON con tree collapsible (scaffolded)
- [x] 🐳 Docker Manager — Listar contenedores, start/stop, ver logs (scaffolded)
- [x] 🗄️ DB Browser — Explorar tablas SQLite con interfaz visual (scaffolded)

---

### v0.9.3 — Creative & System

Apps creativas, multimedia y configuración avanzada. Branch: `feature/creative`

**Apps creativas**
- [ ] 🎨 Paintbrush — Editor de ASCII art (brush, line, rect, fill, text)
- [ ] 📊 RetroOffice — Visor/editor de CSV/TSV estilo VisiCalc
- [ ] 🖥️ Wallpaper — ASCII art o imagen (chafa) como fondo de escritorio

**Sistema**
- [ ] 🔊 Sonido — Terminal bell para feedback UI + efectos vía `aplay`/`paplay`
- [ ] 🎮 Emuladores — Wrapper DOSBox/mgba (lanzar desde File Manager)
- [ ] 🍓 Raspi Config — Editor visual para `raspi-config`

**Configuración**
- [ ] Restaurar sesión: recordar ventanas abiertas, posiciones, archivos abiertos
- [ ] Detección de primera ejecución con wizard de bienvenida
- [ ] Completar separación adicional en `widgets/` reutilizables

---

### v0.9.4 — Menú Inicio & Temas Avanzados

La experiencia de escritorio completa. Branch: `feature/start-menu`

**Menú Inicio**
- [ ] 🪟 Start Menu estilo Windows — Botón "Start" en taskbar, menú desplegable con apps, submenús
- [ ] 🍎 Dock estilo Mac — Barra inferior con iconos, animación bounce, auto-hide
- [ ] TUI App Launcher — Detectar apps TUI instaladas (`claude`, `nvim`, `mc`, `htop`) y lanzarlas en ventana

**Temas avanzados**
- [ ] 🌙 Tema Luna (Windows XP) — Colores azul/verde/plateado, bordes redondeados (`╭╮╰╯`), botones con gradiente
- [ ] Tema macOS Aqua — Aspecto tipo macOS clásico
- [ ] Tema personalizable — Editor de temas en vivo desde Settings

**App Manager**
- [ ] Gestor de apps de RetroTUI: listar, habilitar/deshabilitar, configurar, ver info

---

### v0.9.5 — DOS Mode 🐭

MS-DOS con mouse en RetroTUI. Branch: `feature/dos-mode`

**DOS Shell**
- [ ] Modo pantalla completa estilo MS-DOS 6.22 con prompt `C:\>`
- [ ] Mouse habilitado con cursor block `█`
- [ ] Menu bar tipo DOS (`Alt` activa menú superior)

**DOSBox Integration**
- [ ] DOSBox embebido en ventana RetroTUI vía PTY
- [ ] Mouse passthrough RetroTUI → DOSBox
- [ ] Lanzar apps DOS clásicas: StarOffice 3.1, WordPerfect, Lotus 1-2-3, Turbo Pascal
- [ ] Juegos DOS: DOOM, Duke Nukem, Commander Keen

---

### v1.0.0 — Release Formal

Calidad de release. Publicación y empaquetado.

**Empaquetado**
- [x] `pyproject.toml` con entry point de consola (comando `retrotui`)
- [ ] Publicación en PyPI para `pip install retrotui`
- [ ] Metadata completa: classifiers, keywords, URLs, LICENSE
- [ ] Paquete `.deb` para Ubuntu/Debian
- [ ] Paquete AUR para Arch
- [ ] Man page (`man retrotui`)
- [ ] Opción auto-start: agregar a `.bash_profile` como reemplazo de login shell

---

## Visión a largo plazo

### v2.0 — RetroTUI como Login Shell

RetroTUI reemplaza bash como shell de login. Al encender el PC, aparece el escritorio.

- [ ] Auto-start como login shell (`/etc/shells` + `chsh`)
- [ ] Login screen con usuario/password estilo Win 3.1
- [ ] Gestión de sesiones de usuario
- [ ] Notificaciones del sistema (batería, updates, errores)
- [ ] System tray con widgets (reloj, WiFi, volumen, batería)

### v3.0 — RetroTUI OS

Distribución Linux mínima que bootea directo al escritorio RetroTUI.

- [ ] ISO booteable: Alpine/Void Linux + Python + RetroTUI
- [ ] Setup wizard de instalación
- [ ] Gestión de paquetes integrada
- [ ] Drivers y hardware auto-detectado
- [ ] Target: Raspberry Pi, laptops viejas, thin clients

---

## Ideas Futuras (Backlog)

Estas ideas no tienen versión asignada y se considerarán según prioridad:

| Categoría | Idea | Descripción |
| Apps | Music Player | Wrapper `mpv --no-video` o `cmus` |
| Apps | SSH File Manager | Navegar servidores remotos vía SFTP/paramiko |
| Apps | Cliente IRC/Chat | Chat retro integrado |
| Apps | Cliente Email | Lector IMAP read-only estilo Win 3.1 |
| UX | Screensaver | Starfield, flying toasters, maze después de idle |
| UX | Escritorios múltiples | Cambio de desktops virtuales (Ctrl+Left/Right) |
| UX | Temas comunitarios | Repositorio de temas de la comunidad |
| Sistema | Scripting/macros | Automatización de acciones |
| Sistema | Pipe integration | stdout de terminal → Notepad o Log Viewer |

---

*Última actualización: 21 de febrero de 2026*
