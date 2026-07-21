# Política de releases

Este documento define el proceso mínimo para publicar una versión de RetroTUI de forma reproducible.

## Versionado

RetroTUI usa SemVer:

```text
MAJOR.MINOR.PATCH
```

Los tags usan:

```text
vX.Y.Z
```

## Fuentes de versión

Las cuatro fuentes deben coincidir:

- `pyproject.toml` → `[project].version`
- `retrotui/__init__.py` → `__version__`
- `retrotui/core/app.py` → `APP_VERSION`
- `setup.sh` → banner/versión del instalador

`tools/check_release_tag.py` valida que el tag solicitado coincide con todas ellas.

## Modelo de ramas

- `main` es la fuente única de verdad.
- Las ramas de milestone o agente deben vivir solo mientras tengan trabajo no integrado.
- Un PR validado se integra preferiblemente mediante squash cuando acumuló muchos commits operativos.
- Después del merge se eliminan las ramas totalmente contenidas en `main`.
- Nunca se elimina una rama que contenga commits exclusivos sin revisar el diff contra `main`.

## Gate permanente

Antes de preparar una release, el commit candidato debe pasar la matriz permanente:

| OS | Python |
|---|---|
| Ubuntu | 3.10, 3.12, 3.14 |
| Windows | 3.10, 3.12, 3.14 |

Cada combinación ejecuta:

```bash
python tools/qa.py --skip-tests
python -m unittest discover -s tests -v
python -m pytest tests -q
```

Los dos runners son obligatorios. Un test que no sea recogido por el gate permanente no cuenta como protección de release.

## Gate de documentación

Antes del release, revisar:

- `README.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `docs/CODEX_NEXT_STEPS.md`
- `docs/TTY_TEST_MATRIX.md`
- `tools/TESTING.md`
- este documento

Las afirmaciones públicas de soporte deben coincidir con la matriz TTY. Una suite automatizada verde no certifica por sí sola un terminal físico, emulador, conexión SSH o multiplexer.

## Checklist pre-release

### 1. Confirmar alcance

- El milestone correspondiente está cerrado.
- No se mezclaron features fuera de alcance.
- Los issues críticos/altos están cerrados o documentados como exclusiones de soporte.

### 2. Sincronizar versión

Actualizar las cuatro fuentes de versión.

### 3. Actualizar documentación

- Añadir o finalizar la entrada de `CHANGELOG.md`.
- Actualizar README si cambió comportamiento visible o soporte.
- Marcar el estado correcto en ROADMAP.
- Actualizar la matriz TTY si la release hace claims de compatibilidad.
- Actualizar el handoff operativo para el siguiente milestone.

### 4. Ejecutar el gate local

```bash
python -m pip install -e ".[test]"
python tools/qa.py --skip-tests
python -m unittest discover -s tests -v
python -m pytest tests -q
```

### 5. Verificar CI

- Las seis combinaciones deben terminar en verde.
- No deben quedar workflows temporales, jobs de escritura o scripts de diagnóstico.
- El workflow permanente debe ser `.github/workflows/ci.yml`.

### 6. Smoke test

Como mínimo:

- iniciar RetroTUI;
- abrir y cerrar File Manager;
- editar/guardar/cancelar cierre en Notepad;
- iniciar y cerrar Terminal;
- salir de la aplicación limpiamente.

Para v0.9.6 y posteriores con claims de compatibilidad, ejecutar también la porción relevante de `tools/TESTING.md` en los entornos declarados.

## Commit y tag

```bash
git add -A
git commit -m "release: vX.Y.Z"
git tag -a vX.Y.Z -m "RetroTUI vX.Y.Z"
git push
git push origin vX.Y.Z
```

No reutilizar un tag publicado.

## Workflow de release

Archivo:

```text
.github/workflows/release.yml
```

Triggers previstos:

- push de tags `v*.*.*`;
- `workflow_dispatch` con tag explícito.

Pipeline esperado:

1. Checkout del tag.
2. Instalación de dependencias de build/test.
3. QA y suites automatizadas.
4. `tools/check_release_tag.py --tag vX.Y.Z`.
5. Build de sdist/wheel.
6. Publicación de artifacts.
7. GitHub Release con notas coherentes con el changelog.

## Release v0.9.6

Además del gate general, v0.9.6 requiere:

- completar o clasificar cada entorno objetivo en `docs/TTY_TEST_MATRIX.md`;
- registrar File Manager, Notepad y Terminal por entorno;
- comprobar terminal minimizado, resize, Unicode, colores, teclado y mouse;
- validar ConPTY en Windows nativo;
- no prometer soporte que no esté respaldado por la matriz.

## Rollback

### Tag todavía no publicado

```bash
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
```

### Release publicada

No reescribir silenciosamente el tag. Publicar una nueva versión patch con la corrección y documentar el problema.

## Limpieza post-merge

Después de integrar un milestone:

1. Confirmar que `main` contiene el trabajo esperado.
2. Confirmar CI verde sobre `main`.
3. Comparar ramas auxiliares contra `main`.
4. Eliminar ramas totalmente absorbidas.
5. Conservar tags y documentos históricos de auditoría.
6. Verificar que no quedaron workflows/scripts temporales.
