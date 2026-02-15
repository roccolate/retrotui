"""
Constants and Configuration for RetroTUI.
"""
import curses

# ═══════════════════════════════════════════════════════════
# Box drawing characters (Unicode)
# ═══════════════════════════════════════════════════════════
BOX_TL = '╔'
BOX_TR = '╗'
BOX_BL = '╚'
BOX_BR = '╝'
BOX_H  = '═'
BOX_V  = '║'

# Single line for dialogs
SB_TL = '┌'
SB_TR = '┐'
SB_BL = '└'
SB_BR = '┘'
SB_H  = '─'
SB_V  = '│'

# Desktop pattern (Win 3.1 style)
DESKTOP_PATTERN = '░'

# ═══════════════════════════════════════════════════════════
# Icons
# ═══════════════════════════════════════════════════════════
ICONS = [
    {'label': 'Files',    'action': 'filemanager', 'art': ['┌──┐', '│▒▒│', '└──┘']},
    {'label': 'Notepad',  'action': 'notepad',     'art': ['╔══╗', '║≡≡║', '╚══╝']},
    {'label': 'ASCII Vid', 'action': 'asciivideo', 'art': ['┌──┐', '│▶█│', '└──┘']},
    {'label': 'Terminal', 'action': 'terminal',     'art': ['┌──┐', '│>_│', '└──┘']},
    {'label': 'Settings', 'action': 'settings',    'art': ['╭──╮', '│⚙ │', '╰──╯']},
    {'label': 'About',   'action': 'about',        'art': ['╭──╮', '│ ?│', '╰──╯']},
]

# Fallback ASCII icons for non-Unicode terminals
ICONS_ASCII = [
    {'label': 'Files',    'action': 'filemanager', 'art': ['+--+', '|##|', '+--+']},
    {'label': 'Notepad',  'action': 'notepad',     'art': ['+--+', '|==|', '+--+']},
    {'label': 'ASCII Vid', 'action': 'asciivideo', 'art': ['+--+', '|>|#', '+--+']},
    {'label': 'Terminal', 'action': 'terminal',     'art': ['+--+', '|>_|', '+--+']},
    {'label': 'Settings', 'action': 'settings',    'art': ['+--+', '|**|', '+--+']},
    {'label': 'About',   'action': 'about',        'art': ['+--+', '| ?|', '+--+']},
]

VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.webm', '.avi', '.mov', '.m4v', '.mpg', '.mpeg', '.wmv'
}

# ═══════════════════════════════════════════════════════════
# Color Pairs
# ═══════════════════════════════════════════════════════════
C_DESKTOP       = 1
C_MENUBAR       = 2
C_MENU_ITEM     = 3
C_MENU_SEL      = 4
C_WIN_BORDER    = 5
C_WIN_TITLE     = 6
C_WIN_TITLE_INV = 7
C_WIN_BODY      = 8
C_BUTTON        = 9
C_BUTTON_SEL    = 10
C_DIALOG        = 11
C_STATUS        = 12
C_ICON          = 13
C_ICON_SEL      = 14
C_SCROLLBAR     = 15
C_WIN_INACTIVE  = 16
C_FM_SELECTED   = 17
C_FM_DIR        = 18
C_TASKBAR       = 19
