# RetroTUI — Auditoría técnica de código (julio de 2026)

**Baseline auditado:** `main` en `f84d4ac0514533d5ff6fe9068798e2429d4e7d2e`  
**Fecha:** 2026-07-19  
**Método:** lectura estática del código y seguimiento de flujos. La documentación y los tests se usaron para detectar contradicciones, no como prueba de comportamiento.

## Estado real

RetroTUI tiene una separación modular útil y no necesita una reescritura. Sin embargo, todavía no debe considerarse certificado para v0.9.6 porque varios contratos internos divergen entre `core/`, `apps/` y `ui/`.

Las afirmaciones de soporte deben tratarse como objetivos hasta contar con pruebas de regresión y validación en terminales reales.

## Reglas para interpretar esta auditoría

- **Confirmado por flujo:** el fallo se deduce directamente de una ruta ejecutable concreta.
- **Riesgo condicionado:** depende del backend, plataforma, timing o datos recibidos.
- **Limitación:** el código no implementa todavía una capacidad prometida o esperada.
- **No cerrado:** un test existente no cierra un hallazgo si protege el comportamiento incorrecto o si no es recogido por CI.

## P0 — Bloqueantes de integridad y ciclo de vida

### 1. Cierre de ventanas con datos sin guardar

El botón de cierre de la barra de título llama directamente a `app.close_window(win)`. No existe un protocolo común `request_close()` / `can_close()` que permita a Notepad bloquear el cierre o solicitar confirmación. El cierre por menú tiene una ruta distinta, y `cleanup()` también ejecuta hooks de cierre directamente.

**Impacto:** pérdida silenciosa de texto modificado al usar `[×]`, salida global o ciertas rutas de shutdown.

### 2. Atributo de confirmación no inicializado en Notepad

`NotepadWindow.open_path()` consulta `_open_path_confirm_pending`, pero el constructor no lo inicializa.

**Impacto:** abrir otro archivo después de modificar el buffer puede lanzar `AttributeError` precisamente en la ruta destinada a proteger los datos.

### 3. Recuperación global de excepciones sin límite

`run_app_loop()` captura `Exception`, registra el traceback y continúa inmediatamente. Un error determinista que ocurra antes del bloqueo de input puede repetirse en cada iteración.

**Impacto:** CPU alta, crecimiento rápido de logs y aplicación aparentemente congelada.

### 4. Inicialización de pares de color sin consultar capacidades

`init_colors()` registra pares hasta el ID 121 sin validar `curses.COLOR_PAIRS`.

**Impacto:** fallo de inicio en backends con pocos pares disponibles.

### 5. Terminal minimizado deja de drenar el PTY

El loop omite `tick()` para ventanas no visibles. Minimizar Terminal establece `visible=False`, mientras la lectura del PTY ocurre solo en `TerminalWindow.tick()`.

**Impacto:** un proceso hijo con salida abundante puede bloquearse al llenarse el buffer del PTY.

### 6. Scrollback duplicado

El buffer normal entrega al scrollback las filas que salen por arriba. Además, `TerminalWindow._append_newline()` agrega manualmente la fila actual antes de ejecutar `line_feed()`.

**Impacto:** líneas duplicadas, conteos incorrectos, scrollbar inconsistente y selección sobre un historial inflado.

### 7. Click en pestañas de RetroNet

`RetroNetWindow.handle_click()` pasa `content_w` a `_handle_tab_bar_click()` sin definir esa variable en la función.

**Impacto:** `NameError` reproducible al hacer clic en una barra con dos o más pestañas.

### 8. Tests pytest fuera de la suite ejecutada por CI

CI ejecuta `python tools/qa.py`, que usa `unittest discover`. Existen archivos con funciones y fixtures de pytest que no son recogidos por unittest.

**Impacto:** la cifra total de tests no representa toda la suite escrita y algunas rutas defensivas no están protegidas en CI.

## P1 — Correctitud de subsistemas

### Redraw y actualización

El código utiliza varias señales distintas:

- `app._dirty`
- retorno booleano de `tick()`
- `needs_redraw`
- `_animated`

La función activa `_tick_and_probe_windows()` consulta `_animated`, mientras otros helpers y ventanas usan `needs_redraw`.

**Acción:** definir dos contratos separados:

1. `tick()` devuelve si hubo un cambio puntual.
2. `wants_periodic_tick` / `is_animated` indica actualización continua.

### RetroNet y red

- Una respuesta anterior puede sobrescribir una navegación posterior porque no existe request generation ID.
- Un error TLS provoca una segunda descarga con `CERT_NONE` y hostname verification desactivado.
- La respuesta se lee completa sin límite de tamaño.
- El parser duplica el texto de enlaces cerrados correctamente.

### File Manager y Trash

- Los sidecars `.trashinfo` pueden aparecer como elementos visibles de Trash.
- El archivo puede moverse aunque falle la escritura de metadata, dejando restauración incompleta.
- Los moves largos entre filesystems pueden bloquear el hilo principal.
- Drag-and-drop prioriza `open_path()` sobre `accept_dropped_path()`, por lo que File Manager puede no ejecutar la copia esperada.

### Notepad

- Cut por teclado elimina selección sin guardar previamente el estado de undo.
- Paste sobre selección guarda el snapshot después de borrar el texto original.
- Abrir con `errors="replace"` puede convertir bytes inválidos en `U+FFFD` y guardar después una versión destructiva sin advertencia.

### Trabajo asíncrono

- Image Viewer usa índices desplazados en el fast path de cache.
- El cancel event evita publicar un resultado viejo, pero no detiene subprocesses ya iniciados.
- WiFi Manager limpia el SSID antes de construir el mensaje final y comparte listas mutables entre worker y render.
- Las operaciones de archivo no tienen cancelación; shutdown puede continuar mientras el worker conserva referencias a ventanas.

## P2 — Compatibilidad y robustez

- El parser ANSI pierde private markers como `?`.
- OSC termina incorrectamente ante una barra invertida aislada.
- Faltan secuencias necesarias para afirmar compatibilidad completa con `vim`, `htop`, `mc`, `less` y similares.
- Tab, Shift+Tab, F10 y Ctrl+Q pueden ser consumidos por el shell antes de llegar al programa hijo.
- Windows PTY no aplica `cwd` / `env` y no garantiza cierre explícito del objeto ConPTY.
- XON/XOFF se desactiva, pero no se conserva y restaura el estado original de termios.
- Las coordenadas escalonadas de nuevas ventanas no se limitan al viewport.
- `atomic_write_text()` usa un nombre temporal fijo y no es seguro ante escrituras concurrentes al mismo destino.

## Contradicciones documentales que deben evitarse

Hasta cerrar los hallazgos anteriores, no deben usarse como garantías las siguientes formulaciones:

- “full PTY shell” como sinónimo de emulación completa.
- “vim/htop just work” sin matriz real por terminal y secuencia ANSI.
- “all windows publish lifecycle events” mientras el flujo normal de spawn no use el método del manager.
- “auditoría cerrada” si existen P0 reproducibles en el baseline auditado.
- “suite completa” si CI no ejecuta también los tests pytest.

## Plan recomendado

### Gate P0 antes de certificación v0.9.6

1. Protocolo único de cierre.
2. Inicialización y pruebas de confirmación de Notepad.
3. Circuit breaker / backoff del main loop.
4. Color-pair capability negotiation.
5. Tick de servicios para ventanas minimizadas.
6. Fuente única de verdad para scrollback.
7. Corrección de tabs de RetroNet.
8. CI con unittest + pytest o migración completa a un solo runner.

### Gate P1 antes de declarar feature complete

1. Contrato único de redraw.
2. Generation IDs y límites de red.
3. TLS seguro.
4. Metadata de Trash transaccional.
5. Undo atómico de operaciones compuestas.
6. Workers con ownership, cancelación y entrega de resultados en main thread.

## Evidencia de cierre requerida

Cada item debe cerrarse con:

- prueba de regresión que reproduzca el fallo anterior;
- prueba del nuevo contrato, no de detalles internos accidentales;
- QA automatizado recogido realmente por CI;
- validación manual en la matriz TTY cuando afecte curses, PTY, mouse o ANSI;
- actualización de README, ROADMAP, ARCHITECTURE y CHANGELOG cuando cambie una promesa pública.
