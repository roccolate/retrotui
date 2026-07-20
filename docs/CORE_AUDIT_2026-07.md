# RetroTUI — Auditoría profunda de `retrotui/core/`

**Baseline:** `f84d4ac0514533d5ff6fe9068798e2429d4e7d2e`  
**Fecha:** 2026-07-19  
**Alcance:** `retrotui/core/`, más los límites necesarios con `ui/window.py` y las aplicaciones que implementan los contratos del core.

## Resumen ejecutivo

El core ya está dividido por responsabilidades y contiene mejoras reales de rendimiento: puntero de ventana activa, caches por ciclo de render, input timeout adaptable, separación de routers y managers, y aislamiento defensivo de plugins y callbacks.

El problema principal no es falta de módulos. Es que existen varios caminos paralelos para realizar la misma operación y no todos conservan los mismos invariantes.

Los contratos más frágiles son:

- spawn y cierre de ventanas;
- dirty/redraw/tick;
- propiedad del estado asíncrono;
- source window de acciones y diálogos;
- inicialización lazy del EventBus;
- captura global de teclado;
- límites de recursos externos;
- degradación de errores.

## Arquitectura observada

```text
RetroTUI (facade/state owner)
├── WindowManager       z-order, focus, close, taskbar
├── FileOperationManager dialogs + one background operation
├── DialogDispatcher    ActionResult -> app/dialog action
├── DragDropManager     file-path drag state
├── IconPositionManager icon persistence and drag
├── EventBus            synchronous pub/sub
├── IPCRouter           direct window delivery + bus observation
├── NotificationManager toast queue
├── event_loop           tick, draw, input and cleanup
├── key_router           global keyboard policy
├── mouse_router         capture and hit-test policy
├── rendering            shell chrome
└── plugin_manager       discovery registry and instantiation
```

La división es útil, pero `RetroTUI` sigue siendo el verdadero coordinador y conserva múltiples implementaciones de operaciones que también existen en los managers.

# Hallazgos del core

## C1 — `RetroTUI._spawn_window()` evita el ciclo de vida de `WindowManager`

`WindowManager._spawn_window()`:

1. agrega la ventana;
2. marca layers dirty;
3. publica `window.opened`;
4. llama `subscribe_to_bus()`;
5. activa la ventana.

Pero el método facade `RetroTUI._spawn_window()` solo hace append + `set_active_window()`.

La mayoría de acciones y plugins llaman al facade, no al método del manager.

### Impacto

- `window.opened` no se publica por el flujo normal;
- ventanas como Clipboard Viewer no reciben `subscribe_to_bus()`;
- la documentación describe un ciclo de vida que no ejecuta el runtime;
- futuras extensiones pueden depender de eventos que nunca ocurren.

### Corrección

```python
# app.py
def _spawn_window(self, win):
    return self.window_mgr._spawn_window(win)
```

Después, eliminar cualquier append manual restante o documentarlo como bootstrap especial.

**Severidad:** P0.

---

## C2 — EventBus lazy + acceso directo a `_event_bus`

El facade crea el bus al acceder a `app.event_bus`. Managers como WindowManager y FileOperationManager consultan directamente `app._event_bus` y no fuerzan su creación.

### Impacto

El comportamiento depende del orden accidental de uso:

- si alguna feature accedió al bus antes, se publican eventos;
- si no, los eventos se omiten silenciosamente;
- el mismo flujo puede comportarse distinto en tests y runtime.

### Corrección

Crear EventBus durante `RetroTUI.__init__` o usar siempre la propiedad pública. El costo de crear un bus vacío es despreciable y elimina una fuente de no determinismo.

**Severidad:** P0 cuando se combina con C1; P1 de forma aislada.

---

## C3 — No existe protocolo transaccional de cierre

WindowManager considera `close()` un hook de limpieza que no puede rechazar la operación. Mouse, acciones, cleanup y cierre de Notepad usan rutas distintas.

### Contrato recomendado

```python
class Window:
    def request_close(self) -> ActionResult | bool | None:
        """True/None: cerrar; ActionResult: resolver antes; False: cancelar."""

    def close(self):
        """Liberación final, sin UI ni posibilidad de veto."""
```

`WindowManager` debe ser la única autoridad que remueve ventanas.

**Severidad:** P0 por pérdida de datos.

---

## C4 — Contrato de actualización dividido

El core usa cuatro conceptos solapados:

- `app._dirty`: necesita frame completo;
- retorno de `tick()`: ocurrió un cambio;
- `_animated`: requiere polling periódico;
- `needs_redraw`: nombre usado por Window/plugins/previews.

`_tick_and_probe_windows()` consulta `_animated`, mientras `_has_animated_windows()` consulta `needs_redraw`.

### Corrección

Separar explícitamente:

```python
changed = window.tick(now)             # cambio puntual
periodic = window.wants_periodic_tick  # necesita cadencia baja
service = window.tick_when_hidden      # debe seguir vivo minimizado
```

El loop convierte esos resultados a `_dirty` e input timeout. No debe inspeccionar atributos privados con nombres alternativos.

**Severidad:** P0 para Terminal minimizado; P1 para previews y plugins.

---

## C5 — Las ventanas ocultas no ejecutan servicios

El filtro `visible` se aplica antes de `tick()`. Esto mezcla dos decisiones distintas:

- si la ventana debe dibujarse;
- si su servicio interno debe progresar.

Terminal, workers con colas, watchers y futuras conexiones no pueden detenerse solo porque la ventana fue minimizada.

### Corrección

Ejecutar tick en todas las ventanas y permitir opt-out explícito. Los probes de animación/render sí deben considerar visibilidad.

**Severidad:** P0.

---

## C6 — Error global sin circuit breaker

El catch global del loop mantiene viva la aplicación, pero no distingue error recuperable de error determinista. Si falla `draw_frame()` o un tick que se repite, el loop reintenta inmediatamente.

### Corrección

- contador de errores consecutivos por componente;
- desactivar ventana/plugin que falla repetidamente;
- backoff corto para error global;
- abortar limpiamente si el renderer central falla N veces;
- conservar el primer traceback como causa principal.

**Severidad:** P0.

---

## C7 — `ActionResult` es tipado solo en apariencia

`ActionResult.type` está anotado como `ActionType`, pero el dispatcher acepta cualquier objeto con atributos `type` y `payload`. El payload es `Any` y mezcla:

- strings;
- paths;
- diccionarios sin schema;
- callbacks ejecutables;
- AppAction;
- datos de proceso.

### Impacto

- validación tardía;
- excepciones por payload mal formado;
- contratos difíciles de probar;
- callbacks cierran sobre objetos vivos y complican ownership.

### Dirección recomendada

Usar payloads dataclass por familia o métodos de fábrica:

```python
ActionResult.open_file(path)
ActionResult.execute(AppAction.NOTEPAD)
ActionResult.confirm_discard(callback_id)
```

Los callbacks no deberían viajar como datos cuando puede usarse un ID de operación almacenado por el manager.

**Severidad:** P1.

---

## C8 — DialogDispatcher identifica workflows por texto visible

`resolve_dialog_result()` diferencia Exit y Discard comparando `dialog.title` y el texto del botón.

### Impacto

- cambiar copy o traducir la UI rompe lógica;
- dos diálogos con el mismo título colisionan;
- tests tienden a proteger strings en vez del protocolo.

Además, el resultado del callback se despacha usando `get_active_window()` al terminar, no necesariamente la ventana que abrió el diálogo.

### Corrección

Cada diálogo debe tener:

```python
workflow_id
source_window_id
on_accept
on_cancel
```

El source debe capturarse al crear el diálogo y validarse antes de entregar el resultado.

**Severidad:** P1; P0 en workflows destructivos.

---

## C9 — Background operations sin cancelación ni ownership final

FileOperationManager mantiene una sola operación global y usa thread daemon. Durante cleanup espera cinco segundos; si sigue vivo, continúa cerrando ventanas y limpiando buses.

### Riesgos

- el worker conserva `source_win` después del cierre;
- puede modificar estado de una ventana ya removida;
- no existe cancel token;
- no hay progreso real ni bytes transferidos;
- un worker colgado continúa tras cleanup hasta terminar el proceso.

### Corrección

Modelar una operación con ID, estado y cancel event. El worker debe producir datos inmutables; solo el main thread modifica ventanas. Shutdown debe cancelar primero y decidir si espera, abandona o bloquea el cierre.

**Severidad:** P1.

---

## C10 — NotificationManager acepta valores que pueden envenenar el loop

Los eventos de notification pueden proporcionar `duration` de cualquier tipo. `Toast.expired` realiza aritmética/comparación sin coerción. Un string o valor no numérico puede hacer fallar `tick()` en cada iteración; combinado con C6 produce un loop de errores.

### Corrección

Normalizar en `notify()`:

```python
duration = max(0.0, float(duration))
message = str(message)
title = str(title)
level = normalized_level(level)
```

**Severidad:** P0 por composición con el catch global; P1 aislado.

---

## C11 — Drag-and-drop elige el handler incorrecto para File Manager

Un target se considera válido si implementa `open_path()` o `accept_dropped_path()`. Al despachar, el manager prueba primero `open_path()`.

File Manager implementa ambos:

- `open_path()` navega a directorios;
- `accept_dropped_path()` copia el archivo al directorio activo.

Por tanto, un file drop sobre File Manager puede llamar la ruta de navegación y no copiar nada.

### Corrección

Priorizar el handler específico:

```python
if callable(accept_path):
    result = accept_path(path)
elif callable(open_path):
    result = open_path(path)
```

O declarar capabilities explícitas por ventana.

**Severidad:** P1.

---

## C12 — Política global de teclado invade Terminal

El router consume antes de la ventana activa:

- F10;
- Escape cuando hay menús;
- Ctrl+Q;
- Tab;
- Shift+Tab.

No existe modo de captura general del teclado. `handle_tab_key()` es una excepción puntual, no un protocolo.

### Corrección

Agregar una política por ventana:

```python
window.keyboard_capture_mode
window.reserved_global_keys
window.handle_global_key_override(key)
```

Terminal debe poder alternar entre modo escritorio y modo raw/captured.

**Severidad:** P1.

---

## C13 — `key_router.py` usa `LOGGER` sin definirlo

La ruta defensiva de `cycle_focus()` intenta registrar un fallo con `LOGGER.debug()`, pero el módulo no importa logging ni crea logger.

El error secundario puede ocultar el error original del WindowManager.

**Severidad:** P1.

---

## C14 — `TerminalSession.read()` no limita el total drenado por tick

`max_bytes` es el tamaño de cada `os.read()`, no un presupuesto total. El método sigue leyendo mientras reciba chunks completos.

Con un productor continuo, un solo tick puede monopolizar el main thread y degradar input/render.

### Corrección

Agregar `max_total_bytes` o `max_reads` por llamada. El resto queda en el PTY para el siguiente tick.

**Severidad:** P1, potencial P0 bajo salida extrema.

---

## C15 — Escrituras PTY pueden ser parciales

POSIX `os.write()` puede escribir menos bytes que el payload. El método devuelve el count, pero el contrato no garantiza reintento. Un paste grande puede truncarse si el caller ignora el resultado parcial.

### Corrección

Implementar una cola de salida y flush no bloqueante con presupuesto por tick.

**Severidad:** P1.

---

## C16 — Backend Windows no conserva paridad con POSIX

La ruta Windows no aplica `cwd` ni `extra_env`, y `close()` depende de eliminar la referencia al PTY en lugar de ejecutar un cierre explícito verificable.

### Corrección

Crear una interfaz backend con contratos comunes:

```python
start(shell, cwd, env, cols, rows)
read_budgeted(limit)
write_all_or_queue(data)
resize(cols, rows)
terminate(grace)
close()
```

**Severidad:** P1 para paridad; condicionada a Windows.

---

## C17 — Spawn y geometría no tienen una autoridad única

ActionRunner limita dimensiones para algunas apps, pero:

- special cases usan tamaños fijos;
- plugins usan tamaños del manifest;
- `_next_window_offset()` no hace wrap ni clamp;
- WindowManager acepta activar una ventana que no estaba registrada.

### Corrección

Todos los spawns deben pasar por un factory/manager que:

1. valide dimensiones;
2. limite coordenadas;
3. aplique cascading con wrap;
4. registre lifecycle;
5. active la ventana.

**Severidad:** P1.

---

## C18 — Persistencia sin schema ni preservación de extensiones

Config normaliza campos conocidos y `save_config()` vuelve a serializar únicamente `[ui]` e `[icons]`. Secciones desconocidas pueden perderse al guardar preferencias.

El fallback parser también convierte TOML inválido en una configuración parcial sin avisar al usuario.

### Corrección

- agregar `config_version`;
- migraciones explícitas;
- preservar secciones desconocidas o separar archivos por subsystem;
- renombrar config corrupta y crear defaults, en vez de reinterpretarla silenciosamente.

**Severidad:** P1 antes de congelar formato para 1.0.

---

## C19 — Flow control se modifica sin snapshot de restauración

Bootstrap elimina IXON/IXOFF, pero cleanup solo desactiva mouse y restaura señales. No conserva los atributos termios originales.

### Corrección

`disable_flow_control()` debe devolver un token/snapshot, almacenado en app y restaurado durante cleanup.

**Severidad:** P1; dependiente del terminal padre.

---

## C20 — Pares ANSI exceden capacidades de curses

La matriz foreground/background necesita IDs hasta 121. La inicialización no negocia `COLOR_PAIRS`.

### Corrección

Introducir `TerminalCapabilities` durante bootstrap:

```python
colors
color_pairs
can_change_palette
unicode
mouse_backend
supports_extended_colors
```

Los themes y ANSI deben degradar según capacidades.

**Severidad:** P0 para backends limitados.

# Fortalezas que conviene conservar

- `EventBus.publish()` copia listas antes de iterar y aísla callbacks.
- WindowManager mantiene un puntero activo O(1) con fallback defensivo.
- Rendering reutiliza el tamaño de frame y caches por ciclo.
- FileOperationManager publica el resultado y `done` bajo el mismo lock.
- Signal handlers difieren el trabajo al loop principal.
- La separación `TerminalScreenBuffer` / `TerminalScreen` permite probar lógica sin curses.
- Los routers están suficientemente separados para introducir protocolos sin reescribir aplicaciones.

# Refactor mínimo recomendado

No convertir todo el core en un framework nuevo. Introducir cuatro contratos pequeños:

## 1. `WindowLifecycle`

```text
spawn -> subscribe -> focus -> request_close -> close -> unsubscribe
```

## 2. `WindowUpdatePolicy`

```text
tick_when_hidden
wants_periodic_tick
tick() -> changed
```

## 3. `DialogWorkflow`

```text
workflow_id
source_window_id
accept/cancel callbacks
payload validado
```

## 4. `BackgroundTask`

```text
id
owner_window_id
cancel_event
immutable result
main-thread completion
```

# Orden de implementación

1. Unificar spawn.
2. Crear EventBus determinísticamente.
3. Unificar cierre.
4. Corregir event loop: hidden ticks, redraw policy y circuit breaker.
5. Tipar workflows de diálogo.
6. Corregir DnD precedence.
7. Añadir presupuestos de I/O PTY.
8. Normalizar notifications.
9. Añadir capability negotiation.
10. Versionar config.

# Pruebas de regresión mínimas

- abrir Clipboard Viewer y verificar que recibe `clipboard.changed`;
- cada spawn publica exactamente un `window.opened`;
- `[×]` sobre Notepad modificado no destruye el buffer;
- Terminal minimizado sigue drenando una salida controlada;
- un `tick()` que falla repetidamente es aislado y no crea busy loop;
- notification con duration inválido no rompe el loop;
- drop a File Manager llama `accept_dropped_path()`;
- respuesta de diálogo se entrega a la ventana fuente aunque cambie el foco;
- PTY read respeta presupuesto por iteración;
- config desconocida no se pierde o la política de pérdida se declara explícitamente;
- inicio con `COLOR_PAIRS < 122` degrada sin fallar.

## Criterio de salida del core

El core puede considerarse listo para congelación de API cuando:

- existe una sola ruta de spawn y cierre;
- todos los servicios tienen política explícita para estado oculto;
- los diálogos no dependen de strings visibles;
- ningún worker modifica UI directamente;
- los límites externos están acotados;
- CI ejecuta todas las pruebas relevantes;
- la documentación pública describe capacidades verificadas, no aspiraciones.
