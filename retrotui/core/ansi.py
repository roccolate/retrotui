"""
ANSI Escape Sequence Parser for RetroTUI.
"""
import curses


from ..constants import C_ANSI_START, _CURSES_ERROR
_ANSI_COLOR_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)

class AnsiStateMachine:
    """Parses ANSI escape sequences and properly delegates both text attributes and control commands."""

    def __init__(self):
        self.state = 'TEXT' # TEXT, ESC, CSI, OSC
        self.params = []
        self.current_param_str = ''
        self.attr = 0
        self.fg = -1
        self.bg = -1
        self.bold = False
        self.dim = False
        self.reverse = False
        self.underline = False
        self.buffer = []

    def reset_attributes(self):
        """Reset SGR attributes to default."""
        self.fg = -1
        self.bg = -1
        self.bold = False
        self.dim = False
        self.reverse = False
        self.underline = False
        self._update_attr()

    def _update_attr(self):
        """Recompute current curses attribute from state."""
        attr = 0
        if self.bold:
            attr |= curses.A_BOLD
        if self.dim:
            attr |= curses.A_DIM
        if self.reverse:
            attr |= curses.A_REVERSE
        if self.underline:
            attr |= curses.A_UNDERLINE
        
        # Simple mapping for base 8 colors if terminal supports color.
        # Calling `curses.has_colors()` can raise if curses wasn't initialized
        # (common in headless unit tests). Guard and treat as no-color in that case.
        try:
            has_colors = curses.has_colors()
        except _ANSI_COLOR_ERRORS:
            has_colors = False

        if has_colors:
            # FG 0-7 map to standard curses colors. Use color pairs if available.
            if self.fg >= 0 and self.fg <= 7:
                try:
                    attr |= curses.color_pair(C_ANSI_START + self.fg)
                except _ANSI_COLOR_ERRORS:
                    pass
        
        self.attr = attr

    def parse_chunk(self, text):
        """
        Process a chunk of text.
        Yields:
          ('TEXT', char, attr)
          ('CSI', final_char, params_list)
          ('OSC', ...) # Not fully implemented, just consumed
          ('CONTROL', char) # For \n, \r, \b, \t
        """
        for ch in text:
            if self.state == 'TEXT':
                if ch == '\x1b':
                    self.state = 'ESC'
                elif ch in ('\n', '\r', '\b', '\t', '\x07', '\x08'):
                    yield ('CONTROL', ch, 0)
                elif ord(ch) >= 32:
                    yield ('TEXT', ch, self.attr)
            
            elif self.state == 'ESC':
                if getattr(self, '_osc_in_esc', False):
                    # We arrived here from inside OSC. ``\\`` closes the OSC
                    # cleanly via ST; any other byte just closes OSC and is
                    # reprocessed normally. A stray non-backslash after ESC
                    # is unusual (the OSC spec mandates ST = ``ESC \\`` or
                    # ``BEL``); we drop the stray ESC but keep the byte.
                    self._osc_in_esc = False
                    if ch == '\\':
                        self.state = 'TEXT'
                        continue
                    self.state = 'TEXT'
                    # Fall through to normal ESC handling for this byte.
                if ch == '[':
                    self.state = 'CSI'
                    self.params = []
                    self.current_param_str = ''
                elif ch == ']':
                    self.state = 'OSC'
                elif ch == '(':
                    self.state = 'CHARSET'
                else:
                    # Fallback for unhandled ESC sequence or immediate char
                    self.state = 'TEXT' # Reset and treat as text or ignore?
                    # Properly we should handle ESC c etc.
            
            elif self.state == 'CSI':
                if ch.isdigit():
                    self.current_param_str += ch
                elif ch == ';':
                    if self.current_param_str:
                        self.params.append(int(self.current_param_str))
                    else:
                        self.params.append(0)
                    self.current_param_str = ''
                elif 0x40 <= ord(ch) <= 0x7E:
                    # Final byte dispatch
                    if self.current_param_str:
                        try:
                            self.params.append(int(self.current_param_str))
                        except ValueError:
                            pass

                    if ch == 'm':
                        self._handle_sgr(self.params)
                    else:
                        # Consumers supply per-command defaults via _num(idx, default),
                        # so we do not synthesize a fake `[0]` here. Filling it would
                        # shadow the consumer's defaults (e.g. CUP without params is
                        # documented to default to row=1, col=1, not row=0/col=0).
                        yield ('CSI', ch, list(self.params))

                    self.state = 'TEXT'
                else:
                    # Intermediate bytes (like ? in ?25h)
                    pass

            elif self.state == 'OSC':
                if ch == '\x07' or (ch == '\\'): # Simplified termination check
                    self.state = 'TEXT'
                elif ch == '\x1b':
                    # ESC inside the OSC body opens the String Terminator
                    # (``ESC \\``). Move into ESC state so the next byte can
                    # decide: a ``\\`` close cleans up; anything else routes
                    # through the regular escape handler instead of looping
                    # forever inside OSC. Without this the parser would
                    # consume every following byte whenever an OSC was
                    # terminated by raw ESC + non-``\\``.
                    self._osc_in_esc = True
                    self.state = 'ESC'
            
            elif self.state == 'CHARSET':
                self.state = 'TEXT'

    def _handle_sgr(self, params):
        if not params:
            params = [0]
        for p in params:
            if p == 0:
                self.reset_attributes()
            elif p == 1:
                self.bold = True
            elif p == 2:
                self.dim = True
            elif p == 4:
                self.underline = True
            elif p == 7:
                self.reverse = True
            elif p == 22:
                self.bold = False
                self.dim = False
            elif p == 24:
                self.underline = False
            elif p == 27:
                self.reverse = False
            elif 30 <= p <= 37:
                self.fg = p - 30 # Standard colors 0-7
            elif p == 39:
                self.fg = -1
            elif 40 <= p <= 47:
                self.bg = p - 40
            elif p == 49:
                self.bg = -1
            # 90-97 Bright FG
            elif 90 <= p <= 97:
                self.fg = p - 90
                self.bold = True # Often treated as bold
        self._update_attr()
