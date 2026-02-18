# Contributing to RetroTUI

Thank you for your interest in contributing! RetroTUI is a community-driven project that aims to bring the Windows 3.1 nostalgia to your terminal.

## Getting Started

1.  **Fork the repository** on GitHub.
2.  **Clone your fork** locally:
    ```bash
    git clone https://github.com/YOUR_USERNAME/RetroTUI.git
    cd RetroTUI
    ```
3.  **Install dependencies** (none required for runtime!):
    - For development/testing, you just need Python 3.9+.
    - (Optional) Install `gpm` if you are on Linux TTY and want mouse support.

## Development Workflow

### 1. Create a Branch
Always work on a feature branch, not `main`.
```bash
git checkout -b feature/my-cool-feature
```

### 2. Coding Standards
-   **Python**: We target Python 3.9+. Use type hints where possible.
-   **Text Files**: Ensure all files are `UTF-8` with `LF` line endings.
    - We provide `.editorconfig` to help with this.
-   **No External Deps**: Do not add `pip` dependencies. RetroTUI must run with standard library only.

### 3. Quality Assurance (QA)
Before submitting a PR, run the local QA tool. It checks encoding, syntax, and runs tests.

```bash
python tools/qa.py
```

If you want to check test coverage:
```bash
python tools/qa.py --module-coverage
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
4.  Wait for review!

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) to understand the system design before making major changes.
