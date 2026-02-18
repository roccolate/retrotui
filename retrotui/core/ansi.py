"""
ANSI Escape Sequence Parser for RetroTUI.
"""
import curses


from ..constants import C_ANSI_START

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
        
        # Simple mapping for base 8 colors if terminal supports color
        if curses.has_colors():
             # FG 0-7 map to standard curses colors?
             # Curses usually handles pairs. We can't set FG/BG independently easily without pairs.
             # However, often pair N implies FG=N, BG=0 if we init them standardly.
             # Let's assume standard pair initialization 1-7:
             # Pair 1: Red on Black? No, usually 1 is Red.
             # Standard Curses: 
             # COLOR_BLACK=0, RED=1, GREEN=2, YELLOW=3, BLUE=4, MAGENTA=5, CYAN=6, WHITE=7
             if self.fg >= 0 and self.fg <= 7:
                 try:
                     # Attempt to use color_pair corresponding to FG color
                     # This assumes pair I is (FG=I, BG=Default/Black).
                     # We can fallback to just attributes if this fails or looks bad.
                     # Ideally init_colors in utils should safeguard this.
                     attr |= curses.color_pair(C_ANSI_START + self.fg)
                 except Exception:
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
                    elif not self.params:
                         self.params = [0] # Default param often 0 or 1 depending on command
                    
                    if ch == 'm':
                        self._handle_sgr(self.params)
                    else:
                        yield ('CSI', ch, list(self.params))
                    
                    self.state = 'TEXT'
                else:
                    # Intermediate bytes (like ? in ?25h)
                    pass

            elif self.state == 'OSC':
                if ch == '\x07' or (ch == '\\'): # Simplified termination check
                    self.state = 'TEXT'
            
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
            elif 39:
                self.fg = -1
            elif 40 <= p <= 47:
                self.bg = p - 40
            elif 49:
                self.bg = -1
            # 90-97 Bright FG
            elif 90 <= p <= 97:
                self.fg = p - 90
                self.bold = True # Often treated as bold
        self._update_attr()
