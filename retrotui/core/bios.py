"""Nostalgic BIOS-style boot sequence for RetroTUI."""
import curses
import time
import random

from ..utils import safe_addstr, theme_attr

class BIOS:
    """Handles the boot sequence animation."""
    
    LOGO = [
        r"  ____       _             _____ _   _ ___ ",
        r" |  _ \ ___| |_ _ __ ___ |_   _| | | |_ _|",
        r" | |_) / _ \ __| '__/ _ \  | | | | | || | ",
        r" |  _ <  __/ |_| | | (_) | | | | |_| || | ",
        r" |_| \_\___|\__|_|  \___/  |_|  \___/|___|",
    ]

    def __init__(self, stdscr):
        self.stdscr = stdscr

    def run(self):
        """Execute the BIOS sequence. Returns True if completed, False if skipped."""
        self.stdscr.nodelay(True)
        self.stdscr.clear()
        
        h, w = self.stdscr.getmaxyx()
        
        # Color: Light Gray on Black (Classic BIOS)
        # Using body_attr as a base, but ideally we want white on black
        attr = curses.A_NORMAL
        
        y = 1
        x = 2
        
        # 1. Print Logo
        for line in self.LOGO:
            safe_addstr(self.stdscr, y, x, line, attr)
            y += 1
            if self._check_skip(): return False
        
        y += 1
        safe_addstr(self.stdscr, y, x, f"RetroBIOS v0.9.1 (C) 2026 RetroTUI Corp.", attr)
        y += 2
        
        self.stdscr.refresh()
        if self._sleep(0.5): return False

        # 2. Memory Test
        safe_addstr(self.stdscr, y, x, "Memory Test: ", attr)
        self.stdscr.refresh()
        
        mem_total = 16383 # 16MB
        for m in range(0, mem_total + 1, 512):
            safe_addstr(self.stdscr, y, x + 13, f"{m:5} KB OK", attr)
            self.stdscr.refresh()
            if self._check_skip(): return False
            if self._sleep(0.01): return False
        
        y += 1
        if self._sleep(0.3): return False
        
        # 3. CPU Detection
        safe_addstr(self.stdscr, y, x, "CPU: i486DX-66 detected", attr)
        y += 1
        self.stdscr.refresh()
        if self._sleep(0.4): return False
        
        # 4. Peripheral Check
        safe_addstr(self.stdscr, y, x, "Detecting Storage Devices...", attr)
        y += 1
        self.stdscr.refresh()
        if self._sleep(0.6): return False
        
        safe_addstr(self.stdscr, y, x + 2, "Primary Master: HDD-40MB [OK]", attr)
        y += 1
        self.stdscr.refresh()
        if self._sleep(0.2): return False
        
        safe_addstr(self.stdscr, y, x + 2, "Primary Slave: NONE", attr)
        y += 2
        
        safe_addstr(self.stdscr, y, x, "Keyboard..... [OK]", attr)
        y += 1
        self.stdscr.refresh()
        if self._sleep(0.2): return False
        
        safe_addstr(self.stdscr, y, x, "Mouse........ [OK]", attr)
        y += 2
        
        # 5. OS Loader
        safe_addstr(self.stdscr, y, x, "Loading RetroTUI Operating System...", attr)
        y += 1
        self.stdscr.refresh()
        if self._sleep(0.8): return False
        
        # Final flash
        safe_addstr(self.stdscr, y, x, "Booting...", curses.A_BOLD)
        self.stdscr.refresh()
        if self._sleep(0.5): return False
        
        self.stdscr.nodelay(False)
        return True

    def _check_skip(self):
        """Check if any key was pressed to skip."""
        try:
            key = self.stdscr.getch()
            if key != -1:
                return True
        except:
            pass
        return False

    def _sleep(self, seconds):
        """Sleep while checking for skip."""
        start = time.time()
        while time.time() - start < seconds:
            if self._check_skip():
                return True
            time.sleep(0.05)
        return False
