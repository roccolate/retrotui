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

El estado actual del proyecto se publica en `docs/PROJECT_STATUS.md`. Ese documento no reemplaza las fuentes de versión; distingue la versión publicada del milestone activo.

## Modelo de ramas

- `main` es la fuente única de verdad.
- Las ramas de milestone, documentación o agente deben vivir solo mientras tengan trabajo no integrado.
- Todo cambio debe partir del `main` actual y regresar mediante PR.
- Un PR validado se integra preferiblemente mediante squash cuando acumuló varios commits operativos.
- Después del merge se eliminan las ramas totalmente contenidas en `main`.
- Nunca se elimina una rama con commits exclusivos sin comparar primero contra `main`.
- No se mantiene un workflow temporal de escritura o limpieza después de cumplir su propósito.

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

Antes del release, revisar conjuntamente:

- `README.md`
- `docs/PROJECT_STATUS.md`
- `ARCHITECTURE.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `docs/CODEX_NEXT_STEPS.md`
- `docs/TTY_TEST_MATRIX.md`
- `tools/TESTING.md`
- este documento

Reglas:

- README contiene la descripción pública y solo claims respaldados.
- PROJECT_STATUS resume versión publicada, milestone activo, trabajo cerrado y pendiente.
- ROADMAP define límites entre milestones.
- TTY_TEST_MATRIX es la autoridad para soporte por entorno real.
- CHANGELOG registra cambios históricos y alcance de cada release.
- CODEX_NEXT_STEPS describe el flujo operativo del milestone activo.

Una suite automatizada verde no certifica por sí sola un terminal físico, emulador, conexión SSH, multiplexer o host ConPTY.

## Checklist pre-release

### 1. Confirmar alcance

- El milestone correspondiente está cerrado.
- No se mezclaron features fuera de alcance.
- Los issues críticos y altos están cerrados o documentados como exclusiones de soporte.
- PROJECT_STATUS y ROADMAP señalan el mismo milestone.

### 2. Sincronizar versión

Actualizar las cuatro fuentes de versión y comprobarlas con las herramientas del repositorio.

### 3. Actualizar documentación

- Añadir o finalizar la entrada de `CHANGELOG.md`.
- Actualizar README si cambió comportamiento visible o soporte.
- Actualizar PROJECT_STATUS con el nuevo estado.
- Marcar el milestone correcto en ROADMAP.
- Actualizar la matriz TTY si la release incluye claims de compatibilidad.
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
- El CI debe corresponder exactamente al commit candidato.
- No deben quedar workflows temporales, jobs de escritura o scripts de diagnóstico.
- El workflow permanente debe ser `.github/workflows/ci.yml`.

### 6. Smoke test

Como mínimo:

- iniciar RetroTUI;
- abrir y cerrar File Manager;
- editar, guardar y cancelar cierre en Notepad;
- iniciar y cerrar Terminal;
- salir de la aplicación limpiamente.

Para v0.9.6 y releases con claims de compatibilidad, ejecutar además la parte relevante de `tools/TESTING.md` en cada entorno declarado.

### 7. Revisar el PR de release

- El diff contiene solo cambios previstos.
- No hay threads de revisión abiertos.
- El changelog y la versión coinciden.
- El PR está actualizado con `main`.
- CI está verde antes de fusionar.

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
2. Instalación de dependencias de build y test.
3. QA y suites automatizadas.
4. `tools/check_release_tag.py --tag vX.Y.Z`.
5. Build de sdist y wheel.
6. Publicación de artifacts.
7. GitHub Release con notas coherentes con el changelog.

## Release v0.9.6

Además del gate general, v0.9.6 requiere:

- completar o clasificar cada entorno objetivo en `docs/TTY_TEST_MATRIX.md`;
- registrar el commit exacto probado en cada resultado;
- registrar File Manager, Notepad y Terminal por entorno;
- comprobar terminal minimizado, salida continua, resize, Unicode, colores, teclado y mouse;
- validar ConPTY en Windows nativo;
- validar al menos un terminal GUI Linux y una TTY o sesión remota representativa;
- convertir fallos reproducibles en regresiones automáticas;
- actualizar README y PROJECT_STATUS con el soporte realmente certificado;
- no prometer soporte que no esté respaldado por la matriz.

La versión `0.9.6` no debe publicarse mientras los entornos objetivo permanezcan sin clasificación y sin una razón explícita.

## Rollback

### Tag todavía no publicado

```bash
git tag -d vX.Y.Z
git push origin :refs/tags/vX.Y.Z
```

### Release publicada

No reescribir silenciosamente el tag. Publicar una nueva versión patch con la corrección y documentar el problema.

## Limpieza post-merge

Después de integrar un milestone o PR documental:

1. Confirmar que `main` contiene el trabajo esperado.
2. Confirmar CI verde sobre el commit final de `main`.
3. Comparar ramas auxiliares contra `main`.
4. Eliminar ramas totalmente absorbidas.
5. Conservar tags y documentos históricos de auditoría.
6. Verificar que no quedaron workflows, permisos o scripts temporales.
7. Actualizar PROJECT_STATUS si cambió el milestone o el estado de release.
