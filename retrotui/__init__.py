"""
RetroTUI Package
"""

__version__ = "0.9.5"

# Install the curses compatibility layer before importing any RetroTUI
# submodule. Existing code can keep using the stable logical pair IDs while the
# negotiator maps them onto the actual COLOR_PAIRS exposed by the terminal.
try:
    import curses as _curses

    from .color_pairs import install_color_pair_negotiation

    install_color_pair_negotiation(_curses)
except (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError):
    # Importing the package must remain possible in documentation/headless
    # environments where curses is unavailable or only partially implemented.
    pass
