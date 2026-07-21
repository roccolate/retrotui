# RetroTUI Shortcut Policy (TTY)

Objetivo: evitar salidas accidentales al shell host, preservar la prioridad modal y permitir que una terminal enfocada reciba las teclas que necesita una TUI real.

## Principios

- Prioridad modal: `Dialog` > `Context Menu` > `Global/Window Menu` > `Focused App`.
- Una capa modal o menú abierto conserva el control del teclado.
- Una terminal enfocada recibe por defecto los atajos y teclas de función del proceso hijo.
- Los comandos del escritorio dentro de Terminal se ejecutan mediante un prefijo intencional.
- Un atajo de salida nunca debe saltarse una capa transitoria abierta.

## Política global

- `Ctrl+C`:
  - Sesión normal: no debe expulsar al host.
  - En Terminal: con selección copia; sin selección interrumpe el proceso foreground.
- `Ctrl+Q`:
  - Con diálogo o menú activo, cierra primero la capa transitoria.
  - En Terminal enfocada y sin capas abiertas, se envía al proceso hijo.
  - Fuera de Terminal y sin capas abiertas, inicia el flujo de salida.
- `Esc`:
  - Cierra la capa activa de menú o contexto.
  - Sin capas abiertas se delega a la aplicación enfocada.
- `F10`:
  - En Terminal enfocada y sin capas abiertas, se envía al proceso hijo.
  - En otras aplicaciones alterna el menú de ventana o el menú global.

## Propiedad del teclado en Terminal

Cuando Terminal tiene el foco y no existe una capa modal abierta, las siguientes teclas pertenecen al proceso hijo:

- `Tab` y `Shift+Tab`;
- `Ctrl+Q`;
- `F6`, `F7`, `F8` y `F10`;
- el resto de teclas que ya llegan normalmente a `TerminalWindow`.

Esto evita romper autocompletado de shells, Midnight Commander, Vim, Emacs y otras TUIs que usan esas teclas.

La detección es por capacidades (`_key_to_input` + `_forward_payload`), no por el título visible de la ventana ni por una clase concreta.

## Prefijo de comandos del host

`F12` arma un comando de RetroTUI para la Terminal enfocada. La siguiente tecla ejecuta:

| Secuencia | Acción |
|---|---|
| `F12`, `C` | Copiar selección o línea actual |
| `F12`, `V` | Pegar desde el clipboard |
| `F12`, `I` | Interrumpir proceso foreground |
| `F12`, `K` | Terminar proceso foreground |
| `F12`, `R` | Reiniciar la sesión |
| `F12`, `M` | Abrir o cerrar el menú de Terminal |
| `F12`, `X` | Cerrar la ventana Terminal |
| `F12`, `Q` | Salir de RetroTUI |
| `F12`, `Tab` | Cambiar el foco de ventana |
| `F12`, `Esc` | Cancelar el prefijo |
| `F12`, `F12` | Enviar un `F12` literal al proceso hijo |

Una combinación desconocida no pierde datos: reenvía al hijo el `F12` y la tecla posterior. El prefijo también se cancela cuando aparece un diálogo, menú o cambia el destino enfocado.

## Cobertura automatizada

Las regresiones deben congelar al menos:

- passthrough de `Tab`, `Shift+Tab`, `Ctrl+Q`, `F6`, `F7`, `F8` y `F10`;
- comandos y cancelación del prefijo `F12`;
- replay de comandos desconocidos;
- `Ctrl+Q` cerrando menú antes de salir;
- conservación de la política global en ventanas no terminales.

## Pendiente para certificación

- Hacer configurable el prefijo del host.
- Mostrar un indicador visible cuando el prefijo está armado.
- Probar físicamente Bash/Zsh/Fish, Vim/Neovim, `less`, `mc`, `htop` y `tmux`.
- Ejecutar la matriz manual en Linux TTY, terminal GUI, tmux, SSH, WSL y Windows ConPTY.
- Registrar desvíos en `docs/TTY_TEST_MATRIX.md`.
