"""Calculator application with safe expression evaluation."""

import ast
import curses
import operator

from ..core.actions import ActionResult, ActionType, AppAction
from ..core.clipboard import copy_text, paste_text
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


_ALLOWED_BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}

_ALLOWED_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _eval_ast_node(node):
    """Evaluate a parsed AST node with a restricted math-only grammar."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value

    if isinstance(node, ast.BinOp):
        op = _ALLOWED_BINARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError("Operator not allowed.")
        return op(_eval_ast_node(node.left), _eval_ast_node(node.right))

    if isinstance(node, ast.UnaryOp):
        op = _ALLOWED_UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError("Unary operator not allowed.")
        return op(_eval_ast_node(node.operand))

    raise ValueError("Unsupported expression.")


def evaluate_expression(expression):
    """Safely evaluate one arithmetic expression and return display text."""
    expr = (expression or "").strip()
    if not expr:
        raise ValueError("Expression is empty.")

    parsed = ast.parse(expr, mode="eval")
    value = _eval_ast_node(parsed.body)
    if isinstance(value, float):
        # Compact float formatting and normalize negative zero.
        if value == 0.0:
            value = 0.0
        text = f"{value:.12g}"
        return text
    return str(value)


class CalculatorWindow(Window):
    """Fixed-size calculator window with expression input and history."""

    KEY_F6 = getattr(curses, "KEY_F6", -1)
    KEY_F9 = getattr(curses, "KEY_F9", -1)
    KEY_INSERT = getattr(curses, "KEY_IC", -1)
    MAX_HISTORY = 200

    BUTTONS = [
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "=", "+"],
        ["(", ")", "C", "AC"],
    ]

    def __init__(self, x, y, w, h):
        # Increased default height to fit buttons
        super().__init__("Calculator", x, y, max(32, w), max(18, h), content=[], resizable=False)
        self.always_on_top = True
        self.expression = ""
        self.cursor_pos = 0
        self.view_left = 0
        self.history = []
        self.history_index = None
        self.last_result = None

    def _set_expression(self, text):
        self.expression = text
        self.cursor_pos = len(text)
        self._ensure_cursor_visible(max(1, self.w - 10))

    def _append_history(self, line):
        self.history.append(line)
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY :]

    def _history_expr_only(self):
        values = []
        for line in self.history:
            if " = " in line:
                values.append(line.split(" = ", 1)[0])
            elif " ! " in line:
                values.append(line.split(" ! ", 1)[0])
        return values

    def _insert_text(self, text):
        if not text:
            return
        clean = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        self.expression = self.expression[: self.cursor_pos] + clean + self.expression[self.cursor_pos :]
        self.cursor_pos += len(clean)

    def _delete_backward(self):
        if self.cursor_pos <= 0:
            return
        self.expression = self.expression[: self.cursor_pos - 1] + self.expression[self.cursor_pos :]
        self.cursor_pos -= 1

    def _delete_forward(self):
        if self.cursor_pos >= len(self.expression):
            return
        self.expression = self.expression[: self.cursor_pos] + self.expression[self.cursor_pos + 1 :]

    def _ensure_cursor_visible(self, input_width):
        if self.cursor_pos < self.view_left:
            self.view_left = self.cursor_pos
            return
        if self.cursor_pos >= self.view_left + input_width:
            self.view_left = self.cursor_pos - input_width + 1

    def _evaluate_current(self):
        expr = self.expression.strip()
        if not expr:
            return
        try:
            result = evaluate_expression(expr)
            self.last_result = result
            self._append_history(f"{expr} = {result}")
            self._set_expression(result)
        except Exception as exc:
            self._append_history(f"{expr} ! {exc}")
            self.history_index = None

    def _history_move(self, direction):
        entries = self._history_expr_only()
        if not entries:
            return

        if self.history_index is None:
            self.history_index = len(entries) if direction < 0 else -1

        self.history_index += direction
        if self.history_index < 0:
            self.history_index = 0
        if self.history_index > len(entries):
            self.history_index = len(entries)

        if self.history_index == len(entries):
            self._set_expression("")
        else:
            self._set_expression(entries[self.history_index])
    
    def _button_rect(self, row_idx, col_idx):
        """Get (x, y, w, h) for a button based on grid position."""
        bx, by, bw, bh = self.body_rect()
        # Input takes 1 row, History takes remaining top space
        # Buttons take bottom 5 rows * 2 (height) ?
        # Let's say buttons are at the bottom.
        
        btn_rows = len(self.BUTTONS)
        btn_height = 1 # Single line height
        padding_y = 1
        
        start_y = by + bh - (btn_rows * (btn_height + padding_y)) - 2 # 2 for status bar and margin
        start_x = bx + 2
        
        btn_width = 5
        spacing_x = 2
        
        y = start_y + row_idx * (btn_height + padding_y)
        x = start_x + col_idx * (btn_width + spacing_x)
        return x, y, btn_width, btn_height

    def draw(self, stdscr):
        """Draw input row, history area, buttons and status line."""
        if not self.visible:
            return

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if bh <= 0:
            return

        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)

        # Draw Input
        label = "Expr> "
        input_x = bx + len(label)
        input_w = max(1, bw - len(label))
        self._ensure_cursor_visible(input_w)
        view = self.expression[self.view_left : self.view_left + input_w]

        safe_addstr(stdscr, by, bx, label, body_attr | curses.A_BOLD)
        safe_addstr(stdscr, by, input_x, view.ljust(input_w), body_attr)

        cursor_x = input_x + (self.cursor_pos - self.view_left)
        if input_x <= cursor_x < bx + bw:
            char = " "
            if 0 <= self.cursor_pos < len(self.expression):
                char = self.expression[self.cursor_pos]
            safe_addstr(stdscr, by, cursor_x, char, body_attr | curses.A_REVERSE)

        # Draw History (above buttons)
        btn_area_height = len(self.BUTTONS) * 2 + 1
        history_top = by + 2
        history_rows = max(0, bh - 3 - btn_area_height) 
        visible_history = self.history[-history_rows:] if history_rows else []
        for i, line in enumerate(visible_history):
            safe_addstr(stdscr, history_top + i, bx, line[:bw].ljust(bw), body_attr)

        # Draw Buttons
        btn_attr = theme_attr("button")
        for r, row_keys in enumerate(self.BUTTONS):
            for c, key in enumerate(row_keys):
                x, y, w, h = self._button_rect(r, c)
                if y < by or y >= by + bh: continue
                
                # Draw button box
                safe_addstr(stdscr, y, x, f"[{key:^3}]", btn_attr)

        # Status Bar
        topmost_state = "ON" if self.always_on_top else "OFF"
        status = (
            f"F9=Top:{topmost_state}  Ctrl+L=Clear"
        )
        safe_addstr(stdscr, by + bh - 1, bx, status[:bw].ljust(bw), theme_attr("status"))

    def handle_click(self, mx, my, bstate=None):
        _ = bstate
        bx, by, bw, bh = self.body_rect()
        if not (bx <= mx < bx + bw and by <= my < by + bh):
            return None

        # Check buttons
        for r, row_keys in enumerate(self.BUTTONS):
            for c, key in enumerate(row_keys):
                x, y, w, h = self._button_rect(r, c)
                if y == my and x <= mx < x + w:
                    self._handle_button_press(key)
                    return ActionResult(ActionType.SKIP, None) # Consumed

        # Check Input line
        if my == by:
            prefix = len("Expr> ")
            input_w = max(1, bw - prefix)
            col = max(0, min(input_w, mx - (bx + prefix)))
            self.cursor_pos = min(len(self.expression), self.view_left + col)
            return None
            
        return None

    def _handle_button_press(self, key):
        if key == "C":
            self._delete_backward()
        elif key == "AC":
            self._set_expression("")
        elif key == "=":
            self._evaluate_current()
        else:
            self._insert_text(key)

    def handle_key(self, key):
        key_code = normalize_key_code(key)

        if key_code == curses.KEY_LEFT:
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
        elif key_code == curses.KEY_RIGHT:
            if self.cursor_pos < len(self.expression):
                self.cursor_pos += 1
        elif key_code == curses.KEY_HOME:
            self.cursor_pos = 0
        elif key_code == curses.KEY_END:
            self.cursor_pos = len(self.expression)
        elif key_code in (curses.KEY_BACKSPACE, 127, 8):
            self._delete_backward()
        elif key_code == curses.KEY_DC:
            self._delete_forward()
        elif key_code in (curses.KEY_ENTER, 10, 13):
            self._evaluate_current()
        elif key_code == curses.KEY_UP:
            self._history_move(-1)
        elif key_code == curses.KEY_DOWN:
            self._history_move(1)
        elif key_code == 22:  # Ctrl+V
            self._insert_text(paste_text())
        elif key_code in (self.KEY_F6, self.KEY_INSERT):
            if self.last_result:
                copy_text(str(self.last_result))
        elif key_code == self.KEY_F9:
            self.always_on_top = not self.always_on_top
        elif key_code == 12:  # Ctrl+L
            self.history = []
            self.history_index = None
        elif key_code == 27:  # Escape
            self.history_index = None
            self._set_expression("")
        elif key_code == 3:  # Ctrl+C inside app copies result instead of closing app
            if self.last_result:
                copy_text(str(self.last_result))
        elif isinstance(key, str) and key.isprintable() and key not in ("\n", "\r", "\t"):
            self._insert_text(key)
        elif isinstance(key, int) and 32 <= key <= 126:
            self._insert_text(chr(key))
        elif key_code == 24:  # Ctrl+X clears input row
            self._set_expression("")
        elif key_code == 17:  # Ctrl+Q closes calculator window
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)

        bx, by, bw, _ = self.body_rect()
        _ = by
        input_w = max(1, bw - len("Expr> "))
        self._ensure_cursor_visible(input_w)
        return None

