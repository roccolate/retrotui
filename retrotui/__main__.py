"""
Entry point for RetroTUI.
"""
import curses
import locale
import logging
import os
from .core.app import RetroTUI

# Ensure UTF-8
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    pass

if os.environ.get('RETROTUI_DEBUG'):
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(levelname)s] %(name)s: %(message)s'
    )

def main(stdscr):
    app = RetroTUI(stdscr)
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
