# RetroTUI — Manual Testing Checklist

Run `bash tools/smoke_test.sh --create-data` first to create test data at `~/.retrotui-test-data/`.

## Test Data Contents

| Carpeta | Contenido | Para testear |
|---------|-----------|-------------|
| `documents/` | .txt, .py, .c, .sh, sin extensión, con espacios, Unicode, readonly | Notepad, File Manager |
| `configs/` | .toml, .json, .yaml | Notepad, preview |
| `code/` | Python, C, Shell scripts | Notepad syntax |
| `binary/` | .bin, fake PNG/ELF/EXE headers (256B a 64KB) | Hex Viewer |
| `images/` | PNG test images (red, blue, gradient) | Image Viewer |
| `deep/` | 4 niveles de subdirectorios | File Manager navigation |
| `many_files/` | 200 archivos .txt | File Manager performance |
| `.hidden_*` | Archivos y directorios ocultos | Toggle hidden (Ctrl+H) |

---

## Checklist por terminal

Testear en cada terminal. Marcar ✓/✗:

### Terminal: _______________

**Rendering**
- [ ] Desktop pattern visible y correcto
- [ ] Bordes de ventana Unicode (╔═╗║╚╝) se ven bien
- [ ] Tema Win31 — colores correctos
- [ ] Tema DOS CGA — colores correctos
- [ ] Tema Win95 — colores correctos
- [ ] Tema Hacker — colores correctos
- [ ] Tema Amiga — colores correctos
- [ ] Iconos de escritorio visibles con emoji

**Mouse**
- [ ] Click en icono abre app
- [ ] Double-click en icono abre app
- [ ] Drag de ventana (title bar) funciona
- [ ] Resize de ventana (esquina inferior derecha) funciona
- [ ] Scroll wheel en File Manager mueve selección
- [ ] Scroll wheel en Notepad scrollea texto
- [ ] Click en botón minimize [─]
- [ ] Click en botón maximize [□]
- [ ] Click en botón close [×]
- [ ] Click en menú bar abre menú
- [ ] Click en item de menú ejecuta acción

**Teclado**
- [ ] Ctrl+Q cierra RetroTUI
- [ ] Alt+F4 cierra ventana activa
- [ ] Tab cambia de ventana
- [ ] Flechas navegan en File Manager
- [ ] Enter abre archivo/directorio en FM
- [ ] Backspace sube al directorio padre en FM
- [ ] Typing funciona en Notepad
- [ ] Ctrl+S guarda en Notepad
- [ ] Escape cierra diálogos

**File Manager** (navegar a `~/.retrotui-test-data/`)
- [ ] Lista archivos correctamente
- [ ] Muestra tamaño de archivos
- [ ] Navegar a `deep/level1/level2/level3/level4/` y volver
- [ ] Abrir `documents/simple.txt` en Notepad
- [ ] Abrir `documents/spanish.txt` — acentos se ven bien
- [ ] Abrir `documents/japanese.txt` — caracteres CJK se ven
- [ ] Abrir `documents/emoji.txt` — emojis visibles
- [ ] Abrir `documents/long_file.txt` — scrollear hasta el final
- [ ] Abrir `documents/wide_lines.txt` — scroll horizontal
- [ ] Abrir `documents/empty.txt` — no crashea
- [ ] Abrir `documents/readonly.txt` — se puede leer
- [ ] Navegar a `many_files/` — los 200 archivos cargan rápido
- [ ] Ctrl+H toggle hidden files (`.hidden_file` aparece/desaparece)
- [ ] Seguir symlink `link_to_simple.txt`
- [ ] Archivo sin extensión `noextension` se puede abrir
- [ ] `file with spaces.txt` se muestra y abre correctamente
- [ ] Preview panel muestra contenido del archivo seleccionado
- [ ] Info panel muestra tamaño, fecha, permisos
- [ ] F5 copiar archivo — dialog aparece, operación funciona
- [ ] F6 mover archivo — operación funciona
- [ ] F7 crear directorio
- [ ] F8 eliminar → va a trash
- [ ] Ctrl+Z undo delete — restaura archivo
- [ ] Renombrar archivo (F2 o menú)
- [ ] Dual pane (toggle) — si ventana es suficientemente ancha
- [ ] Bookmarks — set y navegar

**Notepad**
- [ ] Abrir archivo, editar, guardar
- [ ] File → Save As con nuevo nombre
- [ ] Archivo nuevo (vacío)
- [ ] Copiar/pegar texto (Ctrl+C/Ctrl+V con clipboard interno)
- [ ] Texto largo scrollea correctamente
- [ ] Undo (Ctrl+Z) funciona

**Terminal**
- [ ] Abre shell correctamente
- [ ] `ls --color` muestra colores ANSI
- [ ] `htop` o `top` funciona (si instalado)
- [ ] `vim` o `nano` funciona dentro de la terminal
- [ ] `python3` REPL funciona
- [ ] Resize de ventana terminal actualiza PTY
- [ ] Ctrl+C interrumpe comando
- [ ] `exit` cierra la terminal

**Hex Viewer** (abrir archivos de `binary/`)
- [ ] `random_256b.bin` — muestra offset | hex | ASCII
- [ ] `random_4k.bin` — scrollea correctamente
- [ ] `random_64k.bin` — carga sin lag
- [ ] `fake_header.png` — header bytes visibles (89 50 4E 47)
- [ ] Navegación con flechas
- [ ] Go-to-offset funciona
- [ ] Búsqueda de bytes funciona

**Image Viewer** (abrir archivos de `images/`)
- [ ] `red_square.png` — se renderiza (con chafa/timg)
- [ ] `blue_rect.png` — proporción correcta
- [ ] Zoom funciona
- [ ] Fallback message si no hay backend de imagen

**Calculator**
- [ ] Operaciones básicas (+, -, *, /)
- [ ] Click en botones funciona
- [ ] Teclado funciona (números + operadores)

**Clock**
- [ ] Hora se actualiza
- [ ] Calendario visible

**Log Viewer**
- [ ] Abre un log (si hay)
- [ ] Auto-scroll funciona
- [ ] Filtro funciona

**Window Management**
- [ ] Abrir 5+ ventanas simultáneas — sin lag
- [ ] Abrir 10+ ventanas — sigue usable
- [ ] Ventanas se apilan correctamente (z-order)
- [ ] Ventana enfocada siempre dibuja al frente
- [ ] Minimizar ventana → aparece en taskbar
- [ ] Restaurar ventana desde taskbar
- [ ] Maximizar → llena pantalla
- [ ] Resize terminal (SIGWINCH) → RetroTUI se adapta

**Edge Cases**
- [ ] Terminal 80x24 (mínima) — todo cabe
- [ ] Terminal 200x60 (grande) — se ve bien
- [ ] Resize terminal mientras hay ventanas abiertas
- [ ] Abrir File Manager en directorio vacío
- [ ] Abrir File Manager en `/` (root)
- [ ] Abrir File Manager en home `~`

---

## Terminales a probar

Copiar la checklist de arriba para cada terminal:

1. **Linux TTY** (Ctrl+Alt+F2)
2. **gnome-terminal** o **konsole**
3. **alacritty** o **kitty**
4. **tmux** (dentro de otra terminal)
5. **SSH remoto** (ssh a otra máquina y ejecutar)
6. **MobaXterm** (Windows)
7. **Windows Terminal + WSL2**
8. **Raspberry Pi** (si disponible)

---

## Reporte de bugs

Si algo falla, documentar:
```
Terminal: [nombre y versión]
TERM: [valor de $TERM]
Size: [cols x lines]
Colors: [output de tput colors]
Bug: [descripción]
Steps: [pasos para reproducir]
Expected: [qué debería pasar]
Actual: [qué pasa]
```
