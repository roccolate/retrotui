# Contributing to RetroTUI

Thank you for your interest in contributing! RetroTUI is a community-driven project that aims to bring the Windows 3.1 nostalgia to your terminal.

## Getting Started

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally:
    ```bash
    git clone https://github.com/YOUR_USERNAME/RetroTUI.git
    cd RetroTUI
    ```
3.  **Install dependencies** (none required for Linux/WSL runtime!):
    - For development/testing, use Python 3.10+.
    - On Windows, install the conditional runtime package for the embedded terminal: `pip install pywinpty`. On Python 3.14+ the stdlib `curses` module is native on Windows, so no extra curses package is required.
    - (Optional) Install `gpm` if you are on Linux TTY and want mouse support.

## Development Workflow

### 1. Create a Branch
Always work on a feature branch, not `main`.
```bash
git switch main
git pull --ff-only
git switch -c feature/my-cool-feature
```

### 2. Coding Standards
-   **Python**: We target Python 3.10+. Use type hints where possible.
-   **Text Files**: Ensure all files are `UTF-8` with `LF` line endings.
    - We provide `.editorconfig` to help with this.
-   **No Linux Runtime Deps**: Do not add mandatory third-party dependencies for Linux/WSL runtime. Windows-only compatibility packages are declared conditionally in `pyproject.toml`.

### 3. Quality Assurance (QA)
Before submitting a PR, run the same core checks used by the permanent gate.

```bash
python -m pip install -e ".[test]"
python tools/qa.py --skip-tests
python -m ruff check --select F821 retrotui tests tools
python -m unittest discover -s tests -v
python -m pytest tests -q
```

For the module coverage floor:

```bash
python tools/report_module_coverage.py --quiet-tests --top 20 --fail-under 75.0
```

### 4. Commit Messages
Use clear, descriptive commit messages.
-   `feat: added X`
-   `fix: resolved issue Y`
-   `docs: updated README`

## Pull Requests

1.  Push your branch to your fork.
2.  Open a Pull Request against `roccolate/RetroTUI:main`.
3.  Ensure the CI (GitHub Actions) passes.
4.  Keep the branch synchronized with `main` and address review feedback.
5.  Prefer squash merge for branches containing operational/fixup commits.
6.  After merge, compare the branch against `main` and delete it when no exclusive commits remain.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) before changing lifecycle, shell geometry, physical text width, workers, file operations or terminal behavior. Cross-cutting changes must preserve the documented authority map and add focused regression coverage.
