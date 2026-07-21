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
from .core.app import RetroTUI
from .constants import _CURSES_ERROR

LOGGER = logging.getLogger(__name__)
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

def main(stdscr):
    global _LAST_SHUTDOWN_SIGNAL
    boot_start = time.perf_counter()
    app = RetroTUI(stdscr)
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
    # Capture the most recent external shutdown signal so ``run()`` can
    # mirror it in the process exit code. ``KeyboardInterrupt`` returns 130
    # explicitly; this path covers SIGTERM/SIGHUP/SIGBREAK caught by the
    # runtime handlers in ``signal_handler``. Tolerate non-int values
    # (e.g. test stubs that return ``Mock`` objects) without crashing.
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
            # Convention: ``128 + signum`` for terminations by signal.
            return 128 + _LAST_SHUTDOWN_SIGNAL
        return 0
    except KeyboardInterrupt:
        return 130
    except _TOP_LEVEL_RUNTIME_ERRORS as e:
        # Top-level crash guard is intentionally broad to restore terminal state.
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
    """Build the small maintenance parser without affecting normal startup."""
    parser = argparse.ArgumentParser(
        prog="retrotui",
        description="RetroTUI terminal desktop and maintenance commands.",
    )
    parser.add_argument(
        "--install-terminfo",
        action="store_true",
        help="compile the bundled conservative terminfo profile",
    )
    parser.add_argument(
        "--terminfo-dir",
        metavar="PATH",
        help="destination terminfo database (default: ~/.terminfo)",
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


def main_cli(argv=None):
    """Console script entrypoint.

    Normal invocations retain the historical no-argument path. The maintenance
    parser is activated only when ``--install-terminfo`` is present, which keeps
    programmatic callers and existing test runners insulated from their own
    command-line arguments.
    """
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if "--install-terminfo" in raw_args:
        return _install_terminfo_cli(raw_args)
    return run()

if __name__ == '__main__':
    raise SystemExit(main_cli())
