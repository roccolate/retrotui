# RetroTUI — Codex Next Steps

This document is an operational handoff for Codex. The goal is to close the next milestone without destabilizing the project.

## Current milestone

Target milestone: **v0.9.6 — cross-terminal certification**.

RetroTUI is already in the late `0.9.x` stabilization phase. Do not add new user-facing features while working on this milestone. The current roadmap reserves v0.9.6 for real-environment validation, compatibility documentation, and fixes for bugs discovered during that validation.

## Prime directive

Stabilize RetroTUI across real terminals.

Do not redesign the architecture. Do not expand the app list. Do not change the plugin API unless a discovered compatibility bug absolutely requires it. Prefer small, testable fixes over broad refactors.

## Source of truth

Use these files as the main references:

- `ROADMAP.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `docs/IMPROVEMENTS.md`
- `docs/TTY_TEST_MATRIX.md`
- `tools/TESTING.md`
- `docs/RELEASE.md`
- `docs/SHORTCUT_POLICY_PLAN.md`
- `pyproject.toml`
- `retrotui/__init__.py`
- `setup.sh`

When in doubt, follow the roadmap milestone boundaries.

## v0.9.6 scope

The v0.9.6 milestone exists to certify RetroTUI in real terminal environments:

- Linux console / TTY
- Linux GUI terminal emulators
- SSH remote sessions
- tmux
- screen
- WSL + Windows Terminal
- Windows native with `pywinpty` / ConPTY

Expected deliverable:

- Updated `docs/TTY_TEST_MATRIX.md`
- Compatibility notes for keyboard, mouse, resize, redraw, Unicode, color, terminal PTY, and app behavior
- Fixes for critical or high-impact issues found during testing
- Regression tests for bugs that can be reproduced without a real terminal

## Hard boundaries

Do not work on the following during v0.9.6 unless needed to fix a certification blocker:

- Start Menu redesign
- Session restore
- First-run wizard
- Marketplace or plugin discovery UX
- New games
- New themes
- New bundled apps
- Network features beyond existing RetroNet behavior
- Visual redesigns
- Large architectural rewrites

These belong to v0.9.7, v0.9.8, or post-1.0.

## Compatibility matrix document

`docs/TTY_TEST_MATRIX.md` is the living v0.9.6 terminal compatibility matrix. Do not create a parallel `docs/testing-matrix.md` unless the matrix is intentionally renamed in a dedicated documentation-only commit and every reference is updated.

During v0.9.6, update `docs/TTY_TEST_MATRIX.md` so it includes:

```markdown
## v0.9.6 Certification Summary

Last updated: YYYY-MM-DD
RetroTUI version tested: 0.9.5 / 0.9.6-dev

### Legend

- ✅ Supported
- ⚠️ Partially supported
- ❌ Not supported
- 🧪 Not tested yet

### Summary

| Environment | Startup | Keyboard | Mouse | Resize | Unicode | Colors | Embedded Terminal | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Linux TTY | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| Linux GUI terminal | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| SSH | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| tmux | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| screen | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| WSL + Windows Terminal | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| Windows native | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
```

Keep the existing per-environment checklist and result log format in `docs/TTY_TEST_MATRIX.md`; extend it rather than replacing it.

## Manual certification procedure

For each environment:

1. Install from a clean checkout:

   ```bash
   python -m pip install -e .
   ```

2. Run QA first:

   ```bash
   python tools/qa.py
   ```

3. Launch RetroTUI:

   ```bash
   retrotui
   ```

4. Test the base profile first:

   - File Manager
   - Notepad
   - Terminal

5. Run the relevant portions of `tools/TESTING.md`.

6. Record results in `docs/TTY_TEST_MATRIX.md`.

7. Convert any reproducible failure into either:

   - a small fix with a regression test, or
   - a documented limitation if the terminal cannot support the behavior reliably.

## Embedded terminal focus tests

The embedded terminal is a major blocker for v1.0 quality. During v0.9.6, explicitly test:

```bash
nano
vim
less README.md
top
htop
mc
printf '\033[31mred\033[0m normal\n'
printf '\033[?1049hALT SCREEN\033[?1049lNORMAL\n'
```

Check these behaviors:

- Cursor position is accurate.
- Alt-screen returns to normal screen.
- Scrollback does not corrupt live screen.
- Mouse pass-through works when the child app enables DEC mouse reporting.
- RetroTUI keeps mouse control when the child app does not request mouse reporting.
- Resize updates terminal dimensions without corrupting buffers.

## Bug fix policy

When fixing v0.9.6 issues:

1. Prefer the smallest localized patch.
2. Add a regression test when the bug can be simulated.
3. Avoid broad cleanup unless the bug cannot be fixed safely otherwise.
4. Preserve existing public behavior.
5. Update documentation if the behavior is intentionally limited.

## Regression test targets

Prioritize tests around these areas:

- Terminal buffer resize
- Alt-screen transitions
- Cursor row/column after line wrap
- Mouse pass-through mode detection
- No-pass-through mouse behavior
- WindowManager active window consistency
- Shutdown with open PTY sessions
- File Manager operations on missing or permission-denied paths
- Notepad save/open dirty-buffer behavior

## Definition of done for v0.9.6

v0.9.6 is done when:

- `docs/TTY_TEST_MATRIX.md` covers all target environments.
- Each target environment is marked supported, partially supported, unsupported, or explicitly untested with a reason.
- Base profile behavior is documented for each environment.
- Critical and high-impact bugs discovered during certification are fixed or explicitly deferred with justification.
- `python tools/qa.py` passes cleanly.
- README and ROADMAP do not claim support that the matrix contradicts.

## Suggested commit sequence

Use small commits in this order:

1. `docs: update terminal compatibility matrix`
2. `test: add terminal regression coverage for v0.9.6 blockers`
3. `fix: handle <specific terminal/input/resize issue>`
4. `docs: document v0.9.6 compatibility findings`
5. `chore: prepare v0.9.6 release notes`

## Notes for future milestones

After v0.9.6 is closed, move to v0.9.7 system experience work:

- Session restore
- First-run wizard
- Start Menu categories
- Control Panel plugin toggles
- Global shortcut documentation
- Safe plugin crash recovery

Do not start those until cross-terminal behavior is documented and stable.
