# Plan Deuda Tecnica - RetroTUI

## Objetivo
Reducir riesgo de regresiones y acelerar desarrollo en 2 sprints, sin frenar features clave.

## Resumen de deuda (alta prioridad)
1. Complejidad alta en enrutamiento de eventos (`retrotui/core/app.py`).
2. Contratos internos fragiles (tuplas/string + `hasattr`) entre app y ventanas.
3. Manejo de errores inconsistente en guardado (Notepad + Save As).
4. Drift de documentacion/versiones (`README.md`, `ROADMAP.md`, `CHANGELOG.md`, `setup.sh`).
5. Falta de base de release engineering (tests, `.gitignore`, packaging).

## Sprint 1 (enfoque: estabilidad)

### 1) Corregir bugs funcionales y deuda de bajo costo
- Tareas:
  - Import faltante de `C_WIN_BODY` en `retrotui/ui/dialog.py`.
  - Corregir doble instanciacion en `open_file_viewer()` en `retrotui/core/app.py`.
  - Normalizar retorno de errores de guardado (`save_error`) y procesarlo en `app.py`.
  - Manejar resultado de callback en Save As para mostrar errores al usuario.
- Esfuerzo: S
- Impacto: Alto
- DoD:
  - Save/Save As no falla silenciosamente.
  - InputDialog funciona sin NameError.

### 2) Reducir complejidad de `handle_mouse` y `handle_key`
- Tareas:
  - Extraer pipeline de mouse a metodos privados:
    - `_mouse_dialog`, `_mouse_menu`, `_mouse_drag_resize`, `_mouse_windows`, `_mouse_desktop`.
  - Extraer navegacion de menu global a metodo dedicado.
- Esfuerzo: M
- Impacto: Alto
- DoD:
  - `handle_mouse` < 100 lineas.
  - `handle_key` < 70 lineas.
  - Misma cobertura funcional.

### 3) Contrato de acciones tipado (fase inicial)
- Tareas:
  - Crear `ActionType` + `ActionResult` (dataclass) en `retrotui/core`.
  - Adaptar Notepad/FileManager para devolver `ActionResult`.
  - Eliminar parsing por indices (`result[0]`, `result[1]`) en `app.py`.
- Esfuerzo: M
- Impacto: Alto
- DoD:
  - Sin comparaciones de tuplas string en el dispatcher principal.

## Sprint 2 (enfoque: mantenibilidad y release)

### 4) Unificar Menu y WindowMenu
- Tareas:
  - Crear `MenuBar` configurable (posicion/global/window).
  - Eliminar duplicacion en draw/hover/click/key.
- Esfuerzo: M
- Impacto: Alto
- DoD:
  - Una sola implementacion de logica de menu.

### 5) Disciplina de errores y logs
- Tareas:
  - Reemplazar `except Exception` genericos por excepciones concretas donde aplique.
  - Agregar logging basico para errores de runtime no fatales.
- Esfuerzo: S
- Impacto: Medio
- DoD:
  - Menos `pass` silenciosos en rutas criticas.

### 6) Release engineering minimo
- Tareas:
  - Agregar `.gitignore` (`__pycache__/`, `*.pyc`, etc.).
  - Crear `pyproject.toml` con entrypoint `retrotui`.
  - Agregar smoke tests de logica no-curses (helpers, parsing acciones, file ops mockeadas).
  - Actualizar docs/versionado:
    - `README.md` (entrypoint real del paquete).
    - `ROADMAP.md`/`CHANGELOG.md` a version actual.
    - `setup.sh` (comando correcto de ejecucion).
- Esfuerzo: M
- Impacto: Alto
- DoD:
  - Repo reproducible y docs alineadas con el codigo.

## Orden recomendado de ejecucion
1. Bugs funcionales + Save As.
2. Refactor de handlers.
3. ActionResult tipado.
4. Unificacion de menus.
5. Release engineering y docs.

## Riesgos y mitigacion
- Riesgo: regresion en eventos de mouse/teclado.
  - Mitigacion: checklist manual de interacciones antes de merge.
- Riesgo: refactor grande sin red de tests.
  - Mitigacion: introducir smoke tests antes de cambios estructurales.

## Métricas de salida
- `handle_mouse` y `handle_key` con menor tamaño/ciclomática.
- Cero errores silenciosos en Save/Save As.
- Cero `.pyc` trackeados.
- Documentación y versión consistentes en todos los archivos clave.

## Avance ejecutado (2026-02-15)
- [x] Contrato tipado de acciones (`ActionType` + `ActionResult`) integrado en dispatcher principal.
- [x] `handle_mouse()` y `handle_key()` descompuestos en helpers con pipeline explícito.
- [x] Protocolo base de ventana formalizado (`handle_click`, `handle_key`, `handle_scroll`) con defaults.
- [x] Eliminado duck-typing basado en `hasattr()` para routing de ventanas.
- [x] Guard de tamaño mínimo de terminal al iniciar (80x24).
- [x] `.gitignore` agregado y limpieza de artefactos compilados (`*.pyc`).
- [x] Bootstrap de packaging con `pyproject.toml` y entrypoint `retrotui`.
- [x] Smoke test inicial en `tests/test_actions.py`.
- [x] Fallback ASCII para iconos/emojis en File Manager (`check_unicode_support()`).
- [x] Unificación de menús en una sola implementación (`MenuBar`) con wrappers de compatibilidad.
- [x] Reemplazo de `except Exception` genéricos en rutas internas críticas (input/meminfo/sysinfo); queda solo crash guard top-level intencional.
- [x] Tests de navegación para `MenuBar` (skip separadores, ESC, LEFT/RIGHT, Enter).
- [x] Logging básico en dispatcher de acciones y activación opcional vía `RETROTUI_DEBUG=1`.
- [x] Reemplazo de magic strings de acciones por `AppAction` enum (global, ventanas e iconos) con compatibilidad legacy.
- [x] Smoke tests de integración para contrato `MenuBar` (global y ventana, flujo por coordenadas).

## Pendiente recomendado (siguiente iteración)
1. Aumentar cobertura de tests en rutas no-curses (acciones, parsing de comandos, file ops).
2. Definir política de release/tagging (version bump + checklist de verificación manual).
3. Extender CI a chequeos por plataforma (Linux/Windows) y mantener hook activo en todos los entornos de dev.

## Avance ejecutado (2026-02-16)
- [x] Pipeline de teclado consolidado para `get_wch()` con normalizacion comun (`normalize_key_code`).
- [x] `Dialog`/`InputDialog` compatibles con teclas `str` e `int` (incluye ESC/Enter/Backspace con `get_wch`).
- [x] `NotepadWindow` actualizado para input Unicode real y atajos Ctrl via `get_wch`.
- [x] `FileManagerWindow` actualizado para hotkeys y navegacion con entrada normalizada.
- [x] I/O de Notepad fijado en UTF-8 (`open(..., encoding='utf-8')` para carga y guardado).
- [x] Cobertura de tests ampliada para flujo Unicode/`get_wch` (suite total: 23 tests OK).
- [x] QA automatizado con `tools/qa.py` (UTF-8 + compileall + unittest).
- [x] Workflow CI en `.github/workflows/ci.yml` ejecutando QA en push/PR.
- [x] Hook local `.githooks/pre-commit` para ejecutar QA antes de cada commit.

