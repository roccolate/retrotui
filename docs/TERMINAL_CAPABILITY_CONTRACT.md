# RetroTUI terminal capability contract

RetroTUI must not inherit and advertise the outer terminal's `TERM` value to an
embedded PTY. Doing so can make shells, curses applications and full-screen TUIs
emit control sequences that the embedded renderer does not implement.

## Child environment

Every Terminal window created by the desktop receives an explicit environment
overlay:

| Variable | Value | Reason |
|---|---|---|
| `TERM` | `retrotui` when its compiled terminfo entry is visible; otherwise `ansi` | Never promise more than the renderer can honor |
| `TERM_PROGRAM` | `RetroTUI` | Identifies the terminal host without overstating capabilities |
| `TERM_PROGRAM_VERSION` | current package version | Allows diagnostics to identify the implementation version |
| `COLORTERM` | empty | True color is not yet implemented or certified |
| `RETROTUI_EMBEDDED_TERMINAL` | `1` | Explicit marker for child-side diagnostics |

`RETROTUI_CHILD_TERM` may override the automatic choice for development or
compatibility testing. Per-window overrides supplied by the application take
final precedence.

This environment is injected only into Terminal windows. RetroTUI does not
mutate the process-wide `TERM`, so the host curses session and unrelated
subprocesses retain their original environment.

## Bundled terminfo profile

The source profile is packaged at:

```text
retrotui/terminfo/retrotui.src
```

It declares only behavior implemented by the embedded terminal:

- eight ANSI colors and 64 foreground/background pairs;
- basic cursor movement and erase operations;
- normal and alternate screens;
- cursor visibility;
- application cursor keys;
- autowrap mode;
- F1 through F12, navigation and editing keys;
- bold, dim, underline and reverse attributes.

It deliberately does not declare 256 colors, RGB/true color, OSC extensions or
other capabilities that have not been implemented and tested.

## Installation

Compile the bundled profile into the default user database:

```bash
retrotui --install-terminfo
```

The default destination is:

```text
~/.terminfo
```

A custom destination can be selected with:

```bash
retrotui --install-terminfo --terminfo-dir /path/to/terminfo
```

The command requires the ncurses `tic` compiler. It returns exit code `2` and a
clear diagnostic when `tic` is unavailable or compilation fails.

After installation, new Terminal windows advertise:

```text
TERM=retrotui
```

Existing sessions keep the environment with which they were started and should
be restarted.

## Safe fallback

When no compiled `retrotui` entry is visible, the child receives:

```text
TERM=ansi
```

This is intentionally conservative. Applications may use fewer features, but
they will not be encouraged to send unsupported xterm or 256-color sequences.

## Certification boundary

Changing `retrotui.src` requires corresponding parser, renderer and regression
coverage. The profile is a public compatibility contract, not a wishlist.

The next capability expansion should happen only after the Unicode cell engine,
real autowrap behavior and extended SGR support are complete and verified with
shells and curses applications.
