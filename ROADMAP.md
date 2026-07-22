# RetroTUI — Roadmap

**Objetivo:** construir un entorno de escritorio estilo Windows 3.1 completamente funcional dentro de la terminal, sin X11 ni Wayland.

**Ruta de versiones:**

- `v0.9.6`: certificación cross-terminal.
- `v0.9.7`: experiencia de sistema.
- `v0.9.8`: feature complete.
- `v0.9.9`: bugtest y estabilización únicamente.
- `v1.0.0`: primera versión estable.

**Regla de freeze:** después de `v0.9.8` no entran features nuevas para 1.0. Todo lo demás pasa a post-1.0.

## Estado actual

`v0.9.5` fue publicado el 2026-06-19.

La auditoría de julio de 2026 detectó problemas de ownership y contratos que debían resolverse antes de interpretar una matriz TTY como certificación. El gate pre-v0.9.6 ya está **completado**. El resultado está documentado en [docs/STABILIZATION_PRE_0.9.6.md](docs/STABILIZATION_PRE_0.9.6.md).

El trabajo activo continúa en **v0.9.6 — certificación cross-terminal**. Después del gate original se completó una campaña adicional de hardening: ownership de workers, operaciones de archivos recuperables, contrato `TERM` honesto, celdas Unicode, controles DEC, geometría por columnas físicas y barra global inferior. No se deben agregar features nuevas durante este milestone salvo que sean estrictamente necesarias para corregir un blocker encontrado en un entorno real.

Fuentes operativas:

- [docs/CODEX_NEXT_STEPS.md](docs/CODEX_NEXT_STEPS.md)
- [docs/TTY_TEST_MATRIX.md](docs/TTY_TEST_MATRIX.md)
- [tools/TESTING.md](tools/TESTING.md)
- [docs/RELEASE.md](docs/RELEASE.md)

---

## Historial completado

### v0.1 — Escritorio y ventanas

- Escritorio retro, ventanas, menús, iconos, teclado y mouse.

### v0.2 — File Manager

- Navegación de archivos, visores y eventos por ventana.

### v0.3 — Editor, resize y taskbar

- Notepad, word wrap, guardado, resize, maximize/minimize, taskbar y video ASCII.

### v0.4 — Terminal embebida

- PTY, parser ANSI, scrollback, múltiples terminales y separación de loop/render/input.

### v0.5 — Temas y configuración

- Temas, preview y configuración persistente.

### v0.6 — Clipboard e inter-app

- Clipboard interno, sincronización opcional, drag-and-drop y acciones tipadas.

### v0.7 — Utilidades

- Log Viewer, Process Manager, Calculadora y Reloj/Calendario.

### v0.8 — File Manager avanzado

- Operaciones de archivo, dual pane, previews y bookmarks.

### v0.9 — Media y Hex

- Image Viewer, Hex Viewer y mejoras del Video Player.

### v0.9.1 — Apps avanzadas y UX

- Character Map, Markdown Viewer, System Monitor, Control Panel, Tetris, RetroNet, context menus e iconos persistentes.

### v0.9.2 — Plugins y TTY hardening

- Loader, `plugin.toml`, `RetroApp`, discovery, registro dinámico y documentación de plugins.

### v0.9.3 — Core modular y Windows

- Managers especializados, EventBus, IPC, notificaciones, bundled plugins y backend PTY POSIX/Windows.

### v0.9.4 — Hardening y perfil base

- `tick()` fuera de `draw()`, Terminal sin I/O en render, File Manager y Notepad más seguros y perfil base mínimo.

### v0.9.5 — TerminalScreen y buffer 2D

- [x] `TerminalScreenBuffer` normal y alterno.
- [x] Cursor y atributos por celda.
- [x] Wrap, scroll, clear, insert/delete y resize.
- [x] Mouse pass-through por modos DEC.
- [x] Compatibilidad GPM preservada cuando el hijo no solicita mouse.
- [x] RetroNet con tabs, bookmarks y view source.

Las validaciones reales de `nano`, `vim`, `mc`, `htop`, `less` y otras TUIs pertenecen a v0.9.6, no al gate automatizado de v0.9.5.

---

## Gate pre-v0.9.6 — completado

### P0 cerrados

- [x] Spawn único mediante `WindowManager`.
- [x] EventBus determinístico.
- [x] Cierre transaccional y protección de buffers dirty.
- [x] Ticks de servicio para ventanas minimizadas.
- [x] Contrato único de redraw.
- [x] Circuit breaker para `tick()` y `draw()`.
- [x] Negociación de pares de color según `curses.COLOR_PAIRS`.
- [x] Scrollback sin duplicación.
- [x] Geometría consistente de tabs de RetroNet.
- [x] CI que recoge chequeos, `unittest` y pytest.

### P1 de estabilización cerrados

- [x] Workflows de diálogo tipados y ligados a la ventana fuente.
- [x] Precedencia autoritativa de drag-and-drop.
- [x] Presupuesto total de lectura PTY por tick.
- [x] Cola FIFO para escrituras PTY parciales.
- [x] Paridad del backend Windows para `cwd`, entorno y cierre verificable.

### Gate automatizado

- [x] Ubuntu, Python 3.10.
- [x] Ubuntu, Python 3.12.
- [x] Ubuntu, Python 3.14.
- [x] Windows, Python 3.10.
- [x] Windows, Python 3.12.
- [x] Windows, Python 3.14.
- [x] Chequeos del repositorio.
- [x] Suite `unittest`.
- [x] Suite pytest.

### Diferencia entre estabilización y certificación

El gate completado demuestra contratos internos y regresiones simulables. No sustituye las pruebas en terminales físicas o emuladores reales. Unicode width, mouse protocol, color capacity, resize, SSH, tmux, screen y ConPTY deben seguir registrándose en la matriz TTY.

---

## Hardening posterior al gate — completado

- [x] Ownership explícito de workers y shutdown global ordenado.
- [x] Transferencias cooperativas con progreso, cancelación y publicación transaccional.
- [x] Trash transaccional con journals de recuperación.
- [x] Contrato conservador `TERM=retrotui` / fallback `TERM=ansi` y terminfo instalable.
- [x] Ownership de teclado para Terminal y prefijo host `F12`.
- [x] Celdas Unicode físicas, autowrap, scroll regions y edición DEC.
- [x] IND/NEL/RI, tab stops y device/cursor reports.
- [x] Hardening de OSC, close hooks y scrollback live-tail.
- [x] Geometría Unicode para chrome, taskbar, menús, diálogos, iconos y listas.
- [x] Barra global inferior con `Inicio`, menús hacia arriba, ventanas minimizadas y reloj.
- [x] Hitboxes precisos de checkboxes en Control Panel.
- [x] Matriz permanente verde en cada corte y ramas absorbidas eliminadas.

Estos cambios amplían lo que debe verificarse en terminales reales; no sustituyen la certificación v0.9.6.

---

## v0.9.6 — Certificación cross-terminal

**Objetivo:** validar RetroTUI en entornos reales y documentar el soporte sin promesas generales que contradigan la evidencia.

### Entornos objetivo

- [ ] Linux console directa.
- [ ] Terminales GUI en Linux.
- [ ] SSH remoto.
- [ ] tmux.
- [ ] GNU screen.
- [ ] WSL + Windows Terminal.
- [ ] Windows nativo con `pywinpty` / ConPTY.

### Superficies a certificar

- [ ] Inicio y cierre limpio.
- [ ] Teclado, ownership de Terminal y prefijo host `F12`.
- [ ] Mouse: GPM, SGR/xterm y pass-through DEC.
- [ ] Resize, workspace desde fila cero y taskbar inferior en terminales pequeñas.
- [ ] Unicode, combining marks, emoji y caracteres de ancho doble en chrome, menús, iconos, listas y Terminal.
- [ ] Paletas y terminales con pocos pares de color.
- [ ] File Manager, Notepad y Terminal.
- [ ] Terminal minimizado y sesiones de salida continua.
- [ ] `nano`, `vim`, `less`, `top`, `htop` y `mc` usando el perfil terminfo conservador donde esté disponible.
- [ ] Plugins bundled representativos.

### Entregables

- [ ] Completar [docs/TTY_TEST_MATRIX.md](docs/TTY_TEST_MATRIX.md).
- [ ] Ejecutar [tools/TESTING.md](tools/TESTING.md) por entorno.
- [ ] Convertir fallos reproducibles en regresiones automáticas.
- [ ] Documentar limitaciones no corregibles de cada terminal.
- [ ] Actualizar README y release notes con resultados reales.

**Criterio de salida:** cada entorno objetivo queda clasificado como soportado, parcialmente soportado, no soportado o explícitamente no probado con una razón; no quedan blockers críticos conocidos en los entornos marcados como soportados.

---

## v0.9.7 — Experiencia de sistema

**Objetivo:** que RetroTUI se comporte como un escritorio persistente y comprensible para usuarios nuevos.

- [ ] Restaurar ventanas, posiciones, tamaños y archivos recientes.
- [ ] Wizard de primera ejecución.
- [ ] Start Menu con categorías y accesos del sistema.
- [ ] Control Panel para activar o desactivar apps y plugins.
- [ ] Metadata visible de plugins.
- [ ] Atajos globales documentados.
- [ ] Recovery seguro ante crash de plugin.
- [ ] Política clara de migración de configuración.

**Criterio de salida:** el usuario puede instalar, configurar, cerrar y volver a abrir RetroTUI sin perder el contexto básico.

---

## v0.9.8 — Feature complete

**Objetivo:** congelar el producto funcional que llegará a 1.0.

- [ ] Congelar apps incluidas.
- [ ] Congelar API pública de plugins.
- [ ] Congelar schema y migración de configuración.
- [ ] Revisar empaquetado, entrypoints y dependencias.
- [ ] Completar smoke tests de inicio, ventanas y perfil base.
- [ ] Limpiar TODOs, debug prints y warnings evitables.
- [ ] Mover features fuera de alcance a `docs/post-1.0.md`.
- [ ] Revisión integral de documentación.

**Criterio de salida:** no quedan features requeridas para 1.0.

---

## v0.9.9 — Bugtest y estabilización

**Objetivo:** no agregar nada nuevo.

- [ ] Bug bash y checklist de regresión.
- [ ] Pruebas manuales en toda la matriz soportada.
- [ ] QA automatizado completo.
- [ ] Revisión de CPU alta, loops y recursos no cerrados.
- [ ] Resize extremo y operación sin mouse.
- [ ] Errores de permisos y rutas raras.
- [ ] Cierre con terminales y plugins abiertos.
- [ ] Cero bugs críticos y altos reproducibles.

---

## v1.0.0 — Stable

- [ ] Sincronizar versión en todas las fuentes.
- [ ] Changelog y release notes finales.
- [ ] Tag `v1.0.0`.
- [ ] Instalación limpia verificada.
- [ ] README alineado con la matriz certificada.

**Criterio de salida:** release estable, documentado y reproducible, sin bugs críticos conocidos.

---

## Definition of Done para 1.0

RetroTUI 1.0 estará listo cuando:

- CI recoja y ejecute toda la suite escrita;
- File Manager, Notepad y Terminal no tengan errores críticos conocidos;
- la terminal embebida sea usable en los entornos certificados;
- la matriz de compatibilidad sea explícita;
- plugins y configuración tengan contratos estables;
- instalación, inicio y cierre sean reproducibles;
- no existan bugs críticos conocidos.

## Post-1.0

No deben bloquear 1.0:

- más juegos o temas;
- networking avanzado;
- operaciones remotas del File Manager;
- multimedia ampliada;
- marketplace de plugins;
- builder visual de TUIs;
- integraciones específicas con shells.
