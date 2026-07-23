"""
Entry point for RetroTUI.
"""
import argparse
import curses
import locale
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from .constants import _CURSES_ERROR

LOGGER = logging.getLogger(__name__)
# Resolved lazily so maintenance commands such as ``--install-terminfo`` do not
# import the complete curses desktop and all window classes.
RetroTUI = None
# Populated by ``main()`` when the curses session exits so ``run()`` can
# surface a meaningful exit code for signals caught by RetroTUI's own
# runtime handlers (SIGTERM/SIGHUP/SIGBREAK). ``KeyboardInterrupt`` is
# handled separately and returns 130.
_LAST_SHUTDOWN_SIGNAL = None
_TOP_LEVEL_RUNTIME_ERRORS = (
    ArithmeticError,
    AssertionError,
    AttributeError,
    ImportError,
    LookupError,
    MemoryError,
    NameError,
    OSError,
    RuntimeError,
    SyntaxError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)

# Ensure UTF-8
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    pass

if os.environ.get('RETROTUI_DEBUG'):
    logging.basicConfig(
        level=logging.DEBUG,
        format='ts=%(asctime)s level=%(levelname)s logger=%(name)s msg="%(message)s"'
    )


def _resolve_app_class():
    """Return the desktop class, importing it only for an interactive run."""
    global RetroTUI
    if RetroTUI is None:
        from .core.app import RetroTUI as app_class

        RetroTUI = app_class
    return RetroTUI


def main(stdscr):
    global _LAST_SHUTDOWN_SIGNAL
    boot_start = time.perf_counter()
    app = _resolve_app_class()(stdscr)
    boot_ms = (time.perf_counter() - boot_start) * 1000.0
    if os.environ.get('RETROTUI_DEBUG') or os.environ.get('RETROTUI_PROFILE'):
        LOGGER.debug(
            "startup boot_ms=%.2f use_unicode=%s windows=%d icons=%d",
            boot_ms,
            getattr(app, 'use_unicode', None),
            len(getattr(app, 'windows', [])),
            len(getattr(app, 'icons', [])),
        )
    app.run()
    shutdown_signal = getattr(app, '_shutdown_signal', None)
    if isinstance(shutdown_signal, int) and not isinstance(shutdown_signal, bool):
        _LAST_SHUTDOWN_SIGNAL = shutdown_signal


def _default_crash_log_dir() -> Path:
    """Return the default persistent crash log directory."""
    return Path.home() / ".config" / "retrotui" / "logs"


def _write_crash_report(exc: Exception, traceback_text: str) -> Path | None:
    """Persist a crash report and return its path (best effort)."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = _default_crash_log_dir() / f"crash-{stamp}.log"
    report = (
        f"timestamp={datetime.now().astimezone().isoformat()}\n"
        f"error={exc!r}\n"
        f"python={sys.version.replace(os.linesep, ' ')}\n"
        f"platform={sys.platform}\n"
        f"cwd={os.getcwd()}\n"
        "\ntraceback:\n"
        f"{traceback_text}"
    )
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(report, encoding="utf-8", newline="\n")
    except OSError:
        return None
    return log_path


def run():
    """Run RetroTUI and return process exit code."""
    global _LAST_SHUTDOWN_SIGNAL
    _LAST_SHUTDOWN_SIGNAL = None
    try:
        curses.wrapper(main)
        print('\033c', end='')
        if _LAST_SHUTDOWN_SIGNAL is not None:
            return 128 + _LAST_SHUTDOWN_SIGNAL
        return 0
    except KeyboardInterrupt:
        return 130
    except _TOP_LEVEL_RUNTIME_ERRORS as e:
        try:
            curses.endwin()
        except curses.error:
            pass
        import traceback
        traceback_text = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        crash_log_path = _write_crash_report(e, traceback_text)
        print(f'\nError: {e}')
        if crash_log_path is not None:
            print(f'Crash log saved to: {crash_log_path}')
        traceback.print_exc()
        return 1


def _terminfo_parser() -> argparse.ArgumentParser:
    """Build maintenance parser without affecting normal startup."""
    parser = argparse.ArgumentParser(
        prog="retrotui",
        description="RetroTUI terminal desktop and maintenance commands.",
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument(
        "--install-terminfo",
        action="store_true",
        help="compile the bundled conservative terminfo profile",
    )
    actions.add_argument(
        "--compat-lab",
        action="store_true",
        help="run the guided real-terminal compatibility lab",
    )
    parser.add_argument(
        "--terminfo-dir",
        metavar="PATH",
        help="destination terminfo database (default: ~/.terminfo)",
    )
    parser.add_argument(
        "--compat-output",
        metavar="PATH",
        help="report directory or .json/.md path",
    )
    parser.add_argument(
        "--compat-label",
        metavar="NAME",
        help="human-readable terminal label stored in the report",
    )
    parser.add_argument(
        "--compat-auto",
        action="store_true",
        help="collect automated probes without the interactive curses wizard",
    )
    return parser


def _install_terminfo_cli(argv) -> int:
    """Run the explicit terminfo installer and return a process exit code."""
    from .core.terminal_environment import TerminfoInstallError, install_terminfo

    args = _terminfo_parser().parse_args(argv)
    if not args.install_terminfo:
        return run()
    try:
        target = install_terminfo(args.terminfo_dir)
    except TerminfoInstallError as exc:
        print(f"Error installing RetroTUI terminfo: {exc}", file=sys.stderr)
        return 2
    print(f"Installed RetroTUI terminfo in: {target}")
    print("New embedded terminals will advertise TERM=retrotui.")
    return 0


def _compat_lab_cli(argv) -> int:
    """Run the compatibility lab without importing the desktop runtime."""
    args = _terminfo_parser().parse_args(argv)
    if not args.compat_lab:
        return run()
    from .compat_lab import run_compatibility_lab

    return run_compatibility_lab(
        output_path=args.compat_output,
        label=args.compat_label,
        interactive=not args.compat_auto,
    )


def main_cli(argv=None):
    """Console script entrypoint."""
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if any(arg == "--compat-lab" or arg.startswith("--compat-") for arg in raw_args):
        return _compat_lab_cli(raw_args)
    if "--install-terminfo" in raw_args:
        return _install_terminfo_cli(raw_args)
    return run()


if __name__ == '__main__':
    raise SystemExit(main_cli())
