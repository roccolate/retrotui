# RetroTUI — Improvement Plan

Auditoría técnica viva del proyecto. Este documento funciona como índice del estado de hardening; los hallazgos detallados, evidencia y contratos propuestos viven en:

- [TECHNICAL_AUDIT_2026-07.md](TECHNICAL_AUDIT_2026-07.md) — auditoría general basada en código.
- [CORE_AUDIT_2026-07.md](CORE_AUDIT_2026-07.md) — análisis profundo de `retrotui/core/`.
- [../ROADMAP.md](../ROADMAP.md) — orden de ejecución y gates de release.
- [TTY_TEST_MATRIX.md](TTY_TEST_MATRIX.md) — certificación por terminal y plataforma.

**Estado:** v0.9.5 fue publicado, pero el hardening pre-v0.9.6 se reabrió después de la auditoría de código del 2026-07-19. Los ciclos anteriores siguen siendo historial útil, pero sus afirmaciones de “cerrado” no anulan fallos reproducibles encontrados posteriormente.

**Última revisión:** 2026-07-19.

---

## Ciclo abierto — auditoría 2026-07-19

### P0 — antes de certificar v0.9.6

- [ ] Unificar el spawn de ventanas mediante `WindowManager._spawn_window()`.
- [ ] Garantizar `window.opened`, `window.focused` y `subscribe_to_bus()` en el flujo real.
- [ ] Crear EventBus de forma determinista o usar siempre la propiedad pública.
- [ ] Definir un protocolo único `request_close()` → confirmación → `close()`.
- [ ] Proteger Notepad contra cierre por `[×]`, salida global y shutdown.
- [ ] Inicializar `_open_path_confirm_pending` y cubrir dirty → Open.
- [ ] Añadir circuit breaker/backoff al catch global del event loop.
- [ ] Ejecutar ticks de servicio en ventanas minimizadas.
- [ ] Unificar `_dirty`, retorno de `tick()`, `needs_redraw` y `_animated`.
- [ ] Negociar pares de color con `curses.COLOR_PAIRS`.
- [ ] Eliminar la doble captura del scrollback de Terminal.
- [ ] Corregir `content_w` no definido en tabs de RetroNet.
- [ ] Hacer que CI ejecute toda la suite escrita, incluidos tests pytest.

### P1 — antes del freeze de API/config

- [ ] Reemplazar diálogos identificados por títulos visibles por workflows tipados.
- [ ] Conservar la ventana fuente al completar callbacks de diálogo.
- [ ] Añadir IDs de generación y límites de descarga a RetroNet.
- [ ] Eliminar el fallback TLS automático con `CERT_NONE`.
- [ ] Hacer transaccional la metadata de Trash y ocultar sidecars.
- [ ] Corregir Undo de Cut/Paste sobre selección en Notepad.
- [ ] Priorizar `accept_dropped_path()` sobre `open_path()` en DnD.
- [ ] Añadir ownership y cancelación a background tasks.
- [ ] Aplicar resultados de workers en el main thread.
- [ ] Presupuestar lectura y escritura de PTY por iteración.
- [ ] Normalizar entradas de NotificationManager.
- [ ] Versionar el schema de configuración y definir preservación de secciones desconocidas.
- [ ] Restaurar XON/XOFF/termios al salir.

### P2 — compatibilidad y robustez

- [ ] Conservar private markers e intermediates en el parser CSI.
- [ ] Corregir terminación OSC.
- [ ] Ampliar secuencias ANSI requeridas por apps TUI comunes.
- [ ] Definir modo de captura de teclado para Terminal.
- [ ] Igualar `cwd`, `env`, close y señales entre PTY POSIX y Windows.
- [ ] Limitar spawn y tamaños de ventanas/plugins al viewport.
- [ ] Usar temporales únicos para escrituras atómicas concurrentes.

---

## Cómo cerrar un hallazgo

Un item no se considera cerrado solo porque exista una prueba o un comentario que describa la intención. Debe incluir:

1. prueba de regresión que reproduzca el fallo anterior;
2. prueba del contrato externo corregido;
3. inclusión comprobada en el runner real de CI;
4. validación manual en la matriz TTY si afecta curses, PTY, ANSI, mouse o resize;
5. actualización de README, arquitectura, roadmap y changelog cuando cambie una promesa pública.

## Clasificación de evidencia

- **Confirmado por flujo:** consecuencia directa de una ruta ejecutable.
- **Confirmado por prueba real:** reproducido en runtime/TTY.
- **Riesgo condicionado:** depende de plataforma, timing, backend o datos.
- **Limitación:** capacidad no implementada completamente.
- **Histórico:** trabajo registrado en ciclos anteriores que puede requerir revalidación.

---

## Historial de hardening anterior

Los ciclos de junio de 2026 aportaron mejoras reales que deben conservarse:

- modularización de `core/` y facade;
- puntero O(1) para ventana activa;
- caches por frame y por componente;
- `tick()` separado de `draw()` en múltiples apps;
- `TerminalScreenBuffer` normal/alt;
- mouse pass-through DEC;
- parser HTML basado en `html.parser`;
- helpers compartidos para TOML y escritura atómica;
- endurecimiento de operaciones de File Manager;
- worker para operaciones largas;
- mejoras de selección, wrap y Undo en Notepad;
- aislamiento defensivo de plugins, IPC y EventBus.

Esos cambios no se eliminan ni se consideran inútiles. La auditoría de julio detectó que algunos refactors introdujeron o dejaron contratos divergentes entre los módulos. El objetivo actual es consolidar esas mejoras detrás de protocolos únicos, no reescribir el proyecto.

Los detalles históricos completos permanecen disponibles en `git log`, `CHANGELOG.md` y las revisiones anteriores de este archivo.

---

## Política hacia 1.0

- No declarar “soportado” lo que solo está implementado parcialmente.
- No usar la cantidad total de tests como prueba si CI no recoge todos los archivos.
- No cerrar v0.9.6 mientras exista un P0 reproducible.
- No congelar API de plugins ni config antes de estabilizar lifecycle, dialogs y background tasks.
- Después de v0.9.8 no se aceptan features nuevas para 1.0.
