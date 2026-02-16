# Release Policy

## Versioning
- Follow SemVer: `MAJOR.MINOR.PATCH`.
- Tag format: `vX.Y.Z` (example: `v0.6.0`).
- Source of truth for runtime/package version:
  - `pyproject.toml` -> `[project].version`
  - `retrotui/core/app.py` -> `APP_VERSION`

## Pre-Release Checklist
1. Update version in:
   - `pyproject.toml`
   - `retrotui/core/app.py`
2. Update release notes/docs:
   - `CHANGELOG.md`
   - `README.md` (if user-visible changes)
   - `ROADMAP.md` (if roadmap status changed)
3. Run quality gate:
   - `python tools/qa.py`
4. Ensure CI is green for the release commit.

## Tagging and Push
1. Commit release changes:
   - `git add -A`
   - `git commit -m "release: vX.Y.Z"`
2. Create annotated tag:
   - `git tag -a vX.Y.Z -m "RetroTUI vX.Y.Z"`
3. Push branch + tag:
   - `git push`
   - `git push origin vX.Y.Z`

## CI Release Workflow
- Workflow file: `.github/workflows/release.yml`
- Triggers:
  - `push` de tags `v*.*.*`
  - `workflow_dispatch` con input `tag`
- Pipeline:
  1. Checkout del tag
  2. `python tools/qa.py`
  3. `python tools/check_release_tag.py --tag vX.Y.Z`
  4. Build de distribuciones (`python -m build`)
  5. Publicación de artifacts y GitHub Release

## Rollback
- If tag is wrong and not published:
  - `git tag -d vX.Y.Z`
  - `git push origin :refs/tags/vX.Y.Z`
