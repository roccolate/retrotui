# Política de releases

## Versionado

- Seguir SemVer: `MAJOR.MINOR.PATCH`.
- Formato de tag: `vX.Y.Z` (ejemplo: `v0.6.0`).
- Fuente de verdad de la versión runtime/paquete:
  - `pyproject.toml` → `[project].version`
  - `retrotui/core/app.py` → `APP_VERSION`

## Checklist pre-release

1. Actualizar versión en:
   - `pyproject.toml`
   - `retrotui/core/app.py`
   - `retrotui/__init__.py`
   - `setup.sh` (si aplica)
2. Actualizar notas/docs:
   - `CHANGELOG.md`
   - `README.md` (si hay cambios visibles)
   - `ROADMAP.md` (si cambia el estado)
3. Correr el gate local:
   - `python tools/qa.py`
4. Confirmar CI en verde para el commit de release.

## Tagging y push

1. Commitear cambios de release:
   - `git add -A`
   - `git commit -m "release: vX.Y.Z"`
2. Crear tag anotado:
   - `git tag -a vX.Y.Z -m "RetroTUI vX.Y.Z"`
3. Subir branch y tag:
   - `git push`
   - `git push origin vX.Y.Z`

## Workflow de release en CI

- Archivo: `.github/workflows/release.yml`
- Triggers:
  - push de tags `v*.*.*`
  - `workflow_dispatch` con input `tag`
- Pipeline:
  1. Checkout del tag
  2. `python tools/qa.py`
  3. `python tools/check_release_tag.py --tag vX.Y.Z`
  4. Build de distribuciones (`python -m pip install build` y luego `python -m build`)
  5. Publicación de artifacts y GitHub Release

## Rollback (tags)

- Si el tag es incorrecto y aún no fue publicado:
  - `git tag -d vX.Y.Z`
  - `git push origin :refs/tags/vX.Y.Z`
