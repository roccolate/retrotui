# RetroTUI Compatibility Lab

The Compatibility Lab records evidence from a real terminal session. It complements the automated Ubuntu/Windows Python matrix; it does not replace it.

## Run the guided lab

```bash
retrotui --compat-lab
```

The curses wizard collects host metadata and guides five checks:

1. colors and text attributes;
2. Unicode, CJK, emoji and combining text;
3. keyboard translation;
4. mouse input;
5. live resize behavior.

For each page:

- `P` records pass;
- `W` records a usable result with a warning;
- `F` records failure;
- `S` skips the check;
- `N` attaches a note;
- `Q` stops the remaining guided checks.

The default report directory is:

```text
~/.config/retrotui/compatibility/
```

Every run writes paired JSON and Markdown reports. JSON is the stable machine-readable format (`schema_version = 1`); Markdown is intended for reviews, issues and release evidence.

## Label and output path

Use an explicit label when the environment cannot identify the terminal reliably:

```bash
retrotui --compat-lab \
  --compat-label "Windows Terminal 1.24 / Windows 11" \
  --compat-output ./compat-reports
```

`--compat-output` accepts either a directory or a `.json`/`.md` filename. Supplying one report filename also creates the sibling format with the same stem.

## Automated mode

For CI, remote probes or sessions without an interactive TTY:

```bash
retrotui --compat-lab --compat-auto --compat-output ./compat-reports
```

Automated mode records:

- output and preferred encodings;
- stdin/stdout TTY state;
- viewport size against the 80x24 baseline;
- available terminal identity variables;
- the `wcwidth` model used for CJK and combining characters.

Guided checks are explicitly recorded as skipped. A warning does not fail the command; any failed check returns exit code `1`.

## Certification matrix

Run the guided lab separately for each environment that will be claimed as supported. Recommended labels:

```text
Linux console
xterm
GNOME Terminal
Konsole
kitty
Alacritty
tmux
GNU screen
SSH
WSL
Windows Terminal
Command Prompt
```

Nested environments should be tested independently. For example, a local `kitty` report does not certify `kitty -> SSH -> tmux`.

## Review policy

A terminal is certified only when:

- its guided report has no failed checks;
- warnings are understood and documented;
- the report identifies the host, terminal, Python version and dimensions;
- the matching RetroTUI commit also passes the permanent repository matrix.

Reports contain environment metadata but no command history, file contents, passwords or clipboard data. Review notes before publishing because labels and environment variables such as shell paths may identify a workstation.
