# RetroTUI — Roadmap

**Objetivo:** construir un entorno de escritorio estilo Windows 3.1 completamente funcional dentro de la terminal. Sin X11. Sin Wayland. Solo curses, una TTY y vibes.

**Meta:** llegar a **v0.9.8 feature complete**, usar **v0.9.9 solo para bugtest/estabilización**, y lanzar **v1.0.0 sin bugs críticos conocidos**.

**Regla:** después de v0.9.8 no entran features nuevas para 1.0. Todo lo nuevo pasa a post-1.0.

---

## Estado completado

### v0.1 — Escritorio y ventanas
- Escritorio retro, ventanas, menús, iconos, teclado y mouse.

### v0.2 — File Manager
- Navegación de archivos, visor de texto, binarios, ocultos y eventos por ventana.

### v0.3 — Editor, resize y taskbar
- Notepad, word wrap, guardado, resize, maximize/minimize, taskbar y ASCII Video Player.

### v0.4 — Terminal embebida
- PTY, parser ANSI, scrollback, múltiples terminales y refactor de event loop/render/input.

### v0.5 — Temas y configuración
- Temas, preview, config persistente en `~/.config/retrotui/config.toml`.

### v0.6 — Clipboard e inter-app
- Clipboard interno, sync opcional, drag-and-drop y acciones tipadas.

### v0.7 — Utilidades
- Log Viewer, Process Manager, Calculadora y Reloj/Calendario.

### v0.8 — File Manager avanzado
- Operaciones de archivo, dual-pane, previews y bookmarks.

### v0.9 — Media y Hex
- Image Viewer, Hex Viewer y Video Player mejorado.

### v0.9.1 — Apps avanzadas y UX
- Character Map, Markdown Viewer, System Monitor, Control Panel, Tetris, RetroNet, context menus, iconos persistentes y mejoras de terminal.

### v0.9.2 — Plugin system y TTY hardening
- Loader de plugins, `plugin.toml`, `RetroApp`, auto-discovery, registro dinámico, plugin de ejemplo y guía dev.

### v0.9.3 — Refactor, bundled plugins y Windows
- Core modular, event bus, IPC, notificaciones, plugins bundled, backend PTY POSIX/Windows, estilos de iconos y tests.

### v0.9.4 — Hardening y pulido
- `tick()` fuera de `draw()`, terminal sin I/O bloqueante en render, File Manager más seguro, Notepad robusto, perfil base mínimo y pulido de apps/plugins.

---

# Plan de cierre hacia 1.0

## v0.9.5 — Terminal PTY y Buffer 2D

**Objetivo:** hacer que la terminal embebida sea confiable para apps TUI comunes.

- [x] Crear `TerminalScreenBuffer` normal-screen `rows x cols`.
- [x] Separar normal-screen, alt-screen y scrollback.
- [x] Soportar wrap, scroll, clear, insert/delete char/line y resize.
- [ ] Cablear `TerminalScreenBuffer` dentro de `TerminalWindow` como fuente única de verdad.
- [ ] Cursor real por fila/columna.
- [ ] Atributos por celda para selección/copy.
- [ ] Mouse pass-through opcional cuando el programa hijo active mouse reporting.
- [ ] Mantener compatibilidad GPM para menús/selección de RetroTUI.
- [ ] Validar `nano`, `vim`, `mc`, `htop`, `less` y `top`.
- [ ] Pruebas de regresión: alt-screen, resize, cursor, copy/select y atributos.
- [ ] Sincronizar versión en `pyproject.toml` y `APP_VERSION`.

**Criterio de salida:** Terminal usable con apps TUI comunes y sin grids paralelos inconsistentes.

---

## v0.9.6 — Certificación cross-terminal

**Objetivo:** comprobar RetroTUI en entornos reales antes de agregar más experiencia visual.

- [ ] Probar Linux console directa.
- [ ] Probar terminales GUI en Linux.
- [ ] Probar SSH remoto.
- [ ] Probar tmux/screen.
- [ ] Probar WSL + Windows Terminal.
- [ ] Probar Windows nativo con `pywinpty`/ConPTY.
- [ ] Documentar diferencias GPM vs SGR mouse.
- [ ] Crear `docs/testing-matrix.md`.
- [ ] Corregir bugs de input, resize, foco, mouse y redraw encontrados en la matriz.

**Criterio de salida:** matriz clara de soportado, parcialmente soportado y no soportado.

---

## v0.9.7 — Experiencia de sistema

**Objetivo:** que RetroTUI se sienta como un escritorio completo.

- [ ] Restaurar sesión: ventanas abiertas, posiciones, tamaños y archivos recientes.
- [ ] Wizard de primera ejecución.
- [ ] Start Menu estilo Windows: categorías, apps recientes y accesos del sistema.
- [ ] Control Panel para activar/desactivar apps y plugins.
- [ ] Metadata visible de plugins: versión, autor, capabilities y estado.
- [ ] Atajos globales documentados.
- [ ] Manejo consistente de errores en apps y plugins.
- [ ] Recovery seguro ante crash de plugin.
- [ ] Documentar configuración del usuario y perfiles.

**Criterio de salida:** un usuario puede instalar, abrir, personalizar, cerrar y volver a abrir RetroTUI sin perder contexto básico.

---

## v0.9.8 — Feature complete / Release candidate funcional

**Objetivo:** cerrar todas las features necesarias para 1.0.

- [ ] Congelar lista de apps incluidas en 1.0.
- [ ] Congelar API pública de plugins para 1.0.
- [ ] Congelar formato de config para 1.0.
- [ ] Revisar documentación principal: README, plugins, install, usage, testing.
- [ ] Revisar empaquetado: `pyproject.toml`, entrypoints, dependencias y extras.
- [ ] QA completo con `python tools/qa.py`.
- [ ] Agregar smoke tests para inicio, abrir/cerrar ventanas, Terminal, File Manager y Notepad.
- [ ] Limpiar TODOs obvios, prints de debug y warnings evitables.
- [ ] Marcar explícitamente lo que queda fuera de 1.0 en `docs/post-1.0.md`.

**Criterio de salida:** v0.9.8 es feature complete. Desde aquí solo se corrigen bugs.

---

## v0.9.9 — Bugtest, QA y estabilización

**Objetivo:** no agregar nada nuevo. Solo probar, corregir y estabilizar.

- [ ] Crear checklist de bug bash.
- [ ] Ejecutar pruebas manuales en toda la matriz soportada.
- [ ] Ejecutar QA automatizado completo.
- [ ] Revisar memory leaks o loops de CPU altos.
- [ ] Validar resize extremo, terminal pequeña y terminal grande.
- [ ] Validar uso sin mouse.
- [ ] Validar uso solo teclado.
- [ ] Validar errores de permisos, archivos inexistentes y rutas raras.
- [ ] Validar cierre limpio con ventanas, terminales y plugins abiertos.
- [ ] Corregir bugs críticos y altos.
- [ ] Clasificar bugs menores no bloqueantes para post-1.0.
- [ ] No aceptar features nuevas.

**Criterio de salida:** cero bugs críticos conocidos, cero bugs altos reproducibles y QA verde.

---

## v1.0.0 — Stable release

**Objetivo:** publicar la primera versión estable.

- [ ] Actualizar versión a `1.0.0` en `pyproject.toml` y `APP_VERSION`.
- [ ] Crear changelog de 1.0.
- [ ] Crear tag `v1.0.0`.
- [ ] Publicar release notes.
- [ ] Confirmar instalación limpia desde repo/paquete.
- [ ] Confirmar que el README refleja la realidad de 1.0.

**Criterio de salida:** release estable, documentado y reproducible.

---

# Definition of Done para 1.0

RetroTUI 1.0 está listo cuando:

- `python tools/qa.py` pasa limpio.
- File Manager, Notepad y Terminal funcionan sin errores críticos.
- La terminal embebida corre apps TUI comunes de forma usable.
- El sistema de plugins está documentado y estable.
- La matriz de compatibilidad está documentada.
- La configuración persiste sin corromperse.
- La app inicia, cierra y restaura estado básico de forma confiable.
- No hay bugs críticos conocidos.

---

# Post-1.0

Ideas que no deben bloquear 1.0:

- Más juegos.
- Más temas.
- Networking avanzado.
- File Manager con operaciones remotas.
- Mejor soporte multimedia.
- Marketplace de plugins.
- TUI builder/SDK visual.
- Integraciones con shells específicas.

---

# Política de versiones

- `0.9.5`: Terminal sólida.
- `0.9.6`: Compatibilidad certificada.
- `0.9.7`: Experiencia de sistema.
- `0.9.8`: Feature complete.
- `0.9.9`: Bugtest only.
- `1.0.0`: Stable release.
