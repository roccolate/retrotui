# RetroTUI Shortcut Policy Plan (TTY)

Objetivo: evitar salidas accidentales a shell host y garantizar comportamiento consistente de atajos globales en `tty`, `tmux` y `ssh`.

## Principios

- Prioridad modal: `Dialog` > `Context Menu` > `Global/Window Menu` > `Focused App`.
- Atajos globales no deben romper atajos locales de apps si no hay capa global activa.
- Cualquier atajo de salida debe ser intencional y reversible.

## Politica Actual (implementada)

- `Ctrl+C`:
  - Sesion normal: no debe expulsar al host.
  - En Terminal app: con seleccion copia; sin seleccion envia interrupcion a foreground.
- `Ctrl+Q`:
  - Si hay capa UI abierta, cierra capa primero.
  - Solo sin capas abiertas dispara flujo de salida.
- `Esc`:
  - Cierra capa activa de menu/contexto.
  - Sin capas abiertas se delega a la app enfocada.
- `F10`:
  - Alterna menu de ventana activa o menu global.

## Conflictos pendientes

- Definir politica uniforme para `Alt+F4` / `Ctrl+W` por app.
- Revisar consistencia de `Tab` (cambio de foco global vs tab local en app).
- Documentar comportamiento de `Enter` cuando menu global esta activo vs app activa.

## Plan de cierre (sprint)

1. Congelar tabla de precedencia de atajos en tests.
2. Agregar casos de regresion para:
   - `Ctrl+Q` con dialog/context/menu/window-menu.
   - `Esc` con y sin capas.
   - `Tab` con `handle_tab_key` local y fallback global.
3. Ejecutar matriz manual en:
   - Linux `tty`
   - Linux `tmux`
   - SSH (`MobaXterm` + `Windows Terminal`)
4. Registrar desvíos en `docs/TTY_TEST_MATRIX.md` y cerrar tareas P1 relacionadas.
