"""Prepend the completed pre-v0.9.6 stabilization entry to CHANGELOG.md."""

from pathlib import Path

path = Path("CHANGELOG.md")
text = path.read_text(encoding="utf-8")
heading = "## [pre-v0.9.6] - 2026-07-21 (stabilization complete)"
if heading in text:
    raise SystemExit("changelog entry already present")

marker = "Todas las versiones notables de RetroTUI están documentadas aquí.\n\n---\n\n"
if text.count(marker) != 1:
    raise SystemExit("CHANGELOG.md header marker mismatch")

entry = '''## [pre-v0.9.6] - 2026-07-21 (stabilization complete)

Gate técnico completado antes de comenzar la certificación cross-terminal de v0.9.6.

### Core y lifecycle

- `WindowManager` quedó como autoridad única de spawn, focus, z-order y close.
- `Window.request_close()` implementa cierre transaccional; Notepad protege buffers dirty en todas las rutas.
- EventBus se crea y consume de forma determinística.
- `tick()`, `wants_periodic_tick` y `tick_when_hidden` tienen responsabilidades separadas.
- El event loop aísla fallos repetidos de `tick()` y `draw()` mediante circuit breaker.
- Los pares de color se negocian contra `curses.COLOR_PAIRS` sin perder los IDs lógicos históricos.

### Diálogos, input y apps

- Los workflows de diálogo usan IDs estables, callbacks tipados y ventana fuente capturada.
- Drag-and-drop prioriza `accept_dropped_path()` y usa `open_path()` solo como fallback.
- RetroNet comparte geometría entre render y click de tabs.
- El scrollback de Terminal conserva una sola fuente de verdad y no duplica filas visibles.

### Terminal PTY

- Terminal continúa dando servicio al PTY mientras está minimizado.
- Las lecturas admiten un presupuesto agregado de 8 KiB por tick.
- Las escrituras usan una cola FIFO y preservan sufijos ante partial write, retorno cero o `EAGAIN`.
- ConPTY recibe `cwd` y entorno heredado/extendido cuando la API lo permite.
- Se soportan variantes actuales, posicionales y legacy de `pywinpty.spawn()`.
- El cierre Windows es explícito y verificable; si el hijo sigue vivo no se declara éxito ni se descarta la cola pendiente.

### CI y compatibilidad

- `pytest` forma parte de las dependencias de test.
- CI ejecuta QA, `unittest` y pytest por separado.
- Matriz permanente: Ubuntu y Windows con Python 3.10, 3.12 y 3.14.
- Las seis combinaciones terminaron verdes al cerrar el gate.
- `windows-curses` y `pywinpty` se declaran como dependencias de runtime marcadas para Windows.

### Documentation

- README, arquitectura, roadmap, release policy y handoff operativo fueron alineados con el estado real.
- `docs/STABILIZATION_PRE_0.9.6.md` registra contratos, regresiones y límites del gate.
- Las auditorías de julio se conservan como documentos históricos; v0.9.6 continúa con pruebas reales en `docs/TTY_TEST_MATRIX.md`.

---

'''
path.write_text(text.replace(marker, marker + entry, 1), encoding="utf-8")
