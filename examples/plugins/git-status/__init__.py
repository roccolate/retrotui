"""Git Status plugin (example).

Shows current branch and recent commits for a repository. Uses `git` if
available and falls back to a message otherwise.
"""
import shutil
import subprocess
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, repo_path='.', **kwargs):
        super().__init__(*args, **kwargs)
        self.repo = repo_path
        self.info = []
        self._load()

    def _load(self):
        if not shutil.which('git'):
            self.info = ['git not available on PATH']
            return
        try:
            # git rev-parse --abbrev-ref HEAD
            branch = subprocess.check_output(['git', '-C', self.repo, 'rev-parse', '--abbrev-ref', 'HEAD'], stderr=subprocess.DEVNULL)
            branch = branch.decode('utf-8', 'ignore').strip()
            commits = subprocess.check_output(['git', '-C', self.repo, 'log', '--oneline', '-n', '10'], stderr=subprocess.DEVNULL)
            commits = commits.decode('utf-8', 'ignore').splitlines()
            self.info = [f'Branch: {branch}'] + commits
        except Exception:
            self.info = ['Not a git repository or git command failed']

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        for i, line in enumerate(self.info[:h]):
            safe_addstr(stdscr, y + i, x, line[:w], attr)

    def handle_key(self, key):
        if key == ord('r'):
            self._load()
