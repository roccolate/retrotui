"""
Entry point for RetroTUI.
"""
import curses
import sys
import locale
from .core.app import RetroTUI

# Ensure UTF-8
try:
    locale.setlocale(locale.LC_ALL, '')
except locale.Error:
    pass

def main(stdscr):
    app = RetroTUI(stdscr)
    app.run()

if __name__ == '__main__':
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Ensure terminal is restored even on error
        try:
            curses.endwin()
        except Exception:
            pass
        print(f'\nError: {e}')
        import traceback
        traceback.print_exc()
