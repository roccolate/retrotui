"""Tetris game for RetroTUI."""
import curses
import random
import time

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr

class TetrisWindow(Window):
    """Retro Tetris implementation."""

    PIECES = {
        'I': ([(0, 1), (1, 1), (2, 1), (3, 1)], 6), # Cyan
        'O': ([(0, 0), (1, 0), (0, 1), (1, 1)], 3), # Yellow
        'T': ([(1, 0), (0, 1), (1, 1), (2, 1)], 5), # Purple
        'S': ([(1, 0), (2, 0), (0, 1), (1, 1)], 2), # Green
        'Z': ([(0, 0), (1, 0), (1, 1), (2, 1)], 1), # Red
        'J': ([(0, 0), (0, 1), (1, 1), (2, 1)], 4), # Blue
        'L': ([(2, 0), (0, 1), (1, 1), (2, 1)], 7), # White
    }

    def __init__(self, x, y):
        # 10x20 grid, each block is 2 chars wide
        super().__init__('Tetris', x, y, 44, 24, resizable=False)
        self.grid = [[0 for _ in range(10)] for _ in range(20)]
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.paused = False
        
        self.curr_piece = None
        self.curr_pos = [0, 0] # [x, y]
        self.curr_color = 0
        self.next_piece_type = random.choice(list(self.PIECES.keys()))
        
        self.last_drop_time = time.time()
        self.drop_interval = 0.8
        
        self._spawn_piece()

    def _spawn_piece(self):
        self.curr_type = self.next_piece_type
        self.next_piece_type = random.choice(list(self.PIECES.keys()))
        
        coords, self.curr_color = self.PIECES[self.curr_type]
        self.curr_piece = list(coords)
        self.curr_pos = [3, 0]
        
        if self._check_collision(self.curr_piece, self.curr_pos):
            self.game_over = True

    def _check_collision(self, piece, pos):
        for px, py in piece:
            gx, gy = pos[0] + px, pos[1] + py
            if gx < 0 or gx >= 10 or gy >= 20:
                return True
            if gy >= 0 and self.grid[gy][gx] != 0:
                return True
        return False

    def _rotate_piece(self):
        if self.curr_type == 'O': return
        
        cx, cy = 1, 1
        if self.curr_type == 'I': 
            cx, cy = 1.5, 1.5
            
        new_piece = []
        for px, py in self.curr_piece:
            rx, ry = px - cx, py - cy
            nx, ny = -ry, rx
            new_piece.append((int(nx + cx), int(ny + cy)))
            
        # Try rotation with wall kicks (simplistic)
        for offset in [0, 1, -1, 2, -2]:
            test_pos = [self.curr_pos[0] + offset, self.curr_pos[1]]
            if not self._check_collision(new_piece, test_pos):
                self.curr_piece = new_piece
                self.curr_pos = test_pos
                return

    def _lock_piece(self):
        for px, py in self.curr_piece:
            gx, gy = self.curr_pos[0] + px, self.curr_pos[1] + py
            if 0 <= gy < 20 and 0 <= gx < 10:
                self.grid[gy][gx] = self.curr_color
        
        self._clear_lines()
        self._spawn_piece()

    def _clear_lines(self):
        lines_cleared = 0
        new_grid = []
        for row in self.grid:
            if all(cell != 0 for cell in row):
                lines_cleared += 1
            else:
                new_grid.append(row)
        
        while len(new_grid) < 20:
            new_grid.insert(0, [0 for _ in range(10)])
        
        self.grid = new_grid
        if lines_cleared > 0:
            self.lines += lines_cleared
            # Scoring: 1: 40, 2: 100, 3: 300, 4: 1200
            score_map = {1: 40, 2: 100, 3: 300, 4: 1200}
            self.score += score_map.get(lines_cleared, 0) * self.level
            self.level = self.lines // 10 + 1
            self.drop_interval = max(0.1, 0.8 - (self.level - 1) * 0.1)

    def draw(self, stdscr):
        if not self.visible: return
        
        # Game loop logic
        now = time.time()
        if not self.game_over and not self.paused:
            if now - self.last_drop_time > self.drop_interval:
                test_pos = [self.curr_pos[0], self.curr_pos[1] + 1]
                if not self._check_collision(self.curr_piece, test_pos):
                    self.curr_pos = test_pos
                else:
                    self._lock_piece()
                self.last_drop_time = now

        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        
        # Clear background
        for i in range(bh):
            safe_addstr(stdscr, by + i, bx, ' ' * bw, body_attr)

        # Draw Grid Board (10x20 blocks, each 2 chars wide = 20 chars)
        board_x = bx + 1
        board_y = by + 1
        
        # Frame for board
        for i in range(21):
            safe_addstr(stdscr, board_y + i, board_x - 1, '│', body_attr)
            safe_addstr(stdscr, board_y + i, board_x + 20, '│', body_attr)
        safe_addstr(stdscr, board_y + 20, board_x - 1, '└' + '─'*20 + '┘', body_attr)

        for y, row in enumerate(self.grid):
            for x, cell in enumerate(row):
                if cell != 0:
                    # Use ANSI pairs 50+cell (e.g. 51=Red, 52=Green...)
                    # We use [] for blocks
                    attr = curses.color_pair(50 + cell)
                    safe_addstr(stdscr, board_y + y, board_x + x*2, "[]", attr)
        
        # Draw current piece
        if self.curr_piece and not self.game_over:
            attr = curses.color_pair(50 + self.curr_color)
            for px, py in self.curr_piece:
                gx, gy = self.curr_pos[0] + px, self.curr_pos[1] + py
                if 0 <= gy < 20:
                    safe_addstr(stdscr, board_y + gy, board_x + gx*2, "[]", attr)

        # Draw HUD
        hud_x = board_x + 23
        safe_addstr(stdscr, board_y, hud_x, f"SCORE: {self.score}", body_attr | curses.A_BOLD)
        safe_addstr(stdscr, board_y + 1, hud_x, f"LINES: {self.lines}", body_attr)
        safe_addstr(stdscr, board_y + 2, hud_x, f"LEVEL: {self.level}", body_attr)
        
        safe_addstr(stdscr, board_y + 4, hud_x, "NEXT:", body_attr)
        next_coords, next_color = self.PIECES[self.next_piece_type]
        attr = curses.color_pair(50 + next_color)
        for px, py in next_coords:
            safe_addstr(stdscr, board_y + 5 + py, hud_x + px*2, "[]", attr)

        if self.game_over:
            safe_addstr(stdscr, board_y + 10, board_x + 3, " GAME OVER ", theme_attr('window_title') | curses.A_BOLD)
            safe_addstr(stdscr, board_y + 11, board_x + 2, " (R) Restart ", body_attr)
        elif self.paused:
            safe_addstr(stdscr, board_y + 10, board_x + 5, " PAUSED ", theme_attr('window_title') | curses.A_BOLD)

    def handle_key(self, key):
        if self.game_over:
            if key in (ord('r'), ord('R')):
                self.__init__(self.x, self.y)
                return None
            return super().handle_key(key)

        if key == ord('p') or key == ord('P'):
            self.paused = not self.paused
            return None

        if self.paused: return None

        if key == curses.KEY_LEFT:
            test_pos = [self.curr_pos[0] - 1, self.curr_pos[1]]
            if not self._check_collision(self.curr_piece, test_pos):
                self.curr_pos = test_pos
        elif key == curses.KEY_RIGHT:
            test_pos = [self.curr_pos[0] + 1, self.curr_pos[1]]
            if not self._check_collision(self.curr_piece, test_pos):
                self.curr_pos = test_pos
        elif key == curses.KEY_DOWN:
            test_pos = [self.curr_pos[0], self.curr_pos[1] + 1]
            if not self._check_collision(self.curr_piece, test_pos):
                self.curr_pos = test_pos
        elif key == curses.KEY_UP:
            self._rotate_piece()
        elif key == ord(' '):
            # Hard drop
            while not self._check_collision(self.curr_piece, [self.curr_pos[0], self.curr_pos[1] + 1]):
                self.curr_pos[1] += 1
            self._lock_piece()
            self.last_drop_time = time.time()
        
        return super().handle_key(key)
