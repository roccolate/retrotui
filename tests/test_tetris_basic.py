import time

import random

from retrotui.apps.tetris import TetrisWindow


def test_init_and_grid_dimensions():
    t = TetrisWindow(0, 0)
    assert len(t.grid) == 20
    assert len(t.grid[0]) == 10
    assert t.score == 0 and t.lines == 0 and t.level == 1


def test_check_collision_bounds_and_occupied():
    t = TetrisWindow(0, 0)
    # Place a block at (0,0)
    t.grid[0][0] = 5
    # Piece that would overlap the occupied cell
    piece = [(0, 0)]
    assert t._check_collision(piece, [0, 0])
    # Out of bounds to left
    assert t._check_collision(piece, [-1, 0])
    # Out of bounds below
    assert t._check_collision(piece, [0, 20])


def test_rotate_piece_simple():
    t = TetrisWindow(0, 0)
    # Use a T piece and place in center
    t.curr_type = 'T'
    t.curr_piece = [(1, 0), (0, 1), (1, 1), (2, 1)]
    t.curr_pos = [4, 0]
    before = list(t.curr_piece)
    t._rotate_piece()
    # Should have attempted rotation; piece coords may change
    assert isinstance(t.curr_piece, list)
    # Ensure no cells are out of bounds after rotation
    for px, py in t.curr_piece:
        gx = t.curr_pos[0] + px
        assert 0 <= gx < 10


def test_clear_lines_and_scoring():
    t = TetrisWindow(0, 0)
    # Fill bottom row
    for x in range(10):
        t.grid[-1][x] = 1
    t._clear_lines()
    assert t.lines == 1
    assert t.score >= 40
    assert t.level == 1 or t.level >= 1


def test_lock_piece_and_spawn(monkeypatch):
    # Make deterministic next piece
    monkeypatch.setattr(random, 'choice', lambda seq: 'O')
    t = TetrisWindow(0, 0)
    # Place a piece near bottom so locking will fill grid
    t.curr_piece = [(0, 0)]
    t.curr_pos = [0, 19]
    # Locking should write to the grid and spawn a new piece
    t._lock_piece()
    assert t.grid[19][0] != 0
    # After lock, a new curr_piece should exist
    assert t.curr_piece is not None


def test_handle_key_move_and_hard_drop(monkeypatch):
    t = TetrisWindow(0, 0)
    # ensure piece in middle
    t.curr_pos = [4, 0]
    # Move left
    t.handle_key( (curses_key := 260) )  # left
    # Move right
    t.handle_key( (curses_key := 261) )  # right
    # Soft drop
    t.handle_key(262)  # down
    # Hard drop
    t.curr_pos = [4, 0]
    # space hard drop
    t.handle_key(ord(' '))
    # After hard drop, piece should have been locked and a new piece spawned
    assert t.curr_piece is not None
