
import curses
import time

def main(stdscr):
    # Setup typical of RetroTUI
    curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)
    
    # Enable mouse
    new_mask, old_mask = curses.mousemask(
        curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION
    )
    
    # TTY specific sequences used in RetroTUI
    print('\033[?1002h', end='', flush=True)
    print('\033[?1006h', end='', flush=True)
    
    stdscr.clear()
    stdscr.addstr(0, 0, "RetroTUI Mouse Debugger (Ctrl+C to exit)")
    stdscr.addstr(1, 0, f"Mouse Mask: {new_mask:x} (Requested: {curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION:x})")
    stdscr.addstr(2, 0, "Try clicking, dragging, and releasing. Events will appear below.")
    stdscr.refresh()
    
    row = 3
    max_rows = curses.LINES - 1
    
    while True:
        try:
            key = stdscr.getch()
            if key == curses.KEY_MOUSE:
                try:
                    _, mx, my, _, bstate = curses.getmouse()
                    
                    event_type = []
                    if bstate & curses.BUTTON1_PRESSED: event_type.append("B1_PRESSED")
                    if bstate & curses.BUTTON1_RELEASED: event_type.append("B1_RELEASED")
                    if bstate & curses.BUTTON1_CLICKED: event_type.append("B1_CLICKED")
                    if bstate & curses.BUTTON1_DOUBLE_CLICKED: event_type.append("B1_DOUBLE")
                    if bstate & curses.REPORT_MOUSE_POSITION: event_type.append("REPORT_POS")
                    
                    msg = f"Event: x={mx}, y={my}, bstate={bstate:x} ({'|'.join(event_type)})"
                    
                    stdscr.move(row, 0)
                    stdscr.clrtoeol()
                    stdscr.addstr(row, 0, msg)
                    stdscr.refresh()
                    
                    row += 1
                    if row >= max_rows:
                        row = 3
                except curses.error:
                    pass
            elif key == 3: # Ctrl+C
                break
        except KeyboardInterrupt:
            break
            
if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
