"""
Entry point for RetroTUI.
"""
import curses
import locale
import logging
import os
import time
from .core.app import RetroTUI

LOGGER = logging.getLogger(__name__)

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

def run():
    """Run RetroTUI and return process exit code."""
    try:
        curses.wrapper(main)
        print('\033c', end='')
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as e:
        # Top-level crash guard is intentionally broad to restore terminal state.
        try:
            curses.endwin()
        except curses.error:
            pass
        print(f'\nError: {e}')
        import traceback
        traceback.print_exc()
        return 1

def main_cli():
    """Console script entrypoint."""
    return run()

if __name__ == '__main__':
    raise SystemExit(main_cli())
