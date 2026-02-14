# Changelog

Todas las versiones notables de RetroTUI están documentadas aquí.

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
