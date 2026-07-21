# RetroTUI — Estabilización pre-v0.9.6

**Estado:** completada  
**Fecha de cierre técnico:** 2026-07-21  
**Baseline de auditoría:** julio de 2026  
**Siguiente milestone:** v0.9.6, certificación cross-terminal

## Propósito

Las auditorías de julio identificaron fallos que hacían prematuro interpretar una prueba manual de terminal como certificación del producto. Antes de probar emuladores, TTY, SSH, tmux, screen y ConPTY reales, era necesario cerrar ownership, lifecycle, redraw, PTY y CI.

Este documento registra qué se corrigió, cuál es el contrato vigente y qué queda fuera de este gate.

Los documentos de auditoría originales se preservan como evidencia histórica:

- [TECHNICAL_AUDIT_2026-07.md](TECHNICAL_AUDIT_2026-07.md)
- [CORE_AUDIT_2026-07.md](CORE_AUDIT_2026-07.md)

No deben editarse para aparentar que nunca existieron los hallazgos. Este informe es la capa de resolución.

## Resultado ejecutivo

- Todos los P0 definidos para el gate fueron cerrados.
- Los P1 seleccionados para estabilización del core fueron cerrados.
- La matriz permanente ejecuta seis combinaciones de OS/Python.
- Cada combinación ejecuta chequeos del repositorio, `unittest` y pytest.
- La matriz final terminó verde.
- No quedaron workflows de escritura, diagnósticos ni parcheadores temporales.
- La arquitectura conserva compatibilidad de plugins en límites explícitos en vez de duplicar contratos dentro del core.

## Matriz automatizada

| OS | Python | QA | unittest | pytest |
|---|---:|---:|---:|---:|
| Ubuntu | 3.10 | ✅ | ✅ | ✅ |
| Ubuntu | 3.12 | ✅ | ✅ | ✅ |
| Ubuntu | 3.14 | ✅ | ✅ | ✅ |
| Windows | 3.10 | ✅ | ✅ | ✅ |
| Windows | 3.12 | ✅ | ✅ | ✅ |
| Windows | 3.14 | ✅ | ✅ | ✅ |

Comandos del gate:

```bash
python tools/qa.py --skip-tests
python -m unittest discover -s tests -v
python -m pytest tests -q
```

## P0 completados

### 1. Spawn único mediante WindowManager

**Problema:** algunas rutas insertaban ventanas directamente y podían omitir focus, suscripción al EventBus o eventos de lifecycle.

**Contrato final:** toda ventana entra por el spawn autoritativo de `WindowManager`.

El manager:

- incorpora la ventana al z-order;
- establece la ventana activa;
- llama `subscribe_to_bus()` cuando existe;
- publica `window.opened`;
- mantiene el cache de ventana activa.

### 2. EventBus determinístico

**Problema:** código consumidor consultaba atributos privados opcionales y el bus podía no existir en el momento esperado.

**Contrato final:** el EventBus se crea y expone mediante el contrato público del app. Los publishers no deben inferir su existencia mediante `_event_bus`.

### 3. Cierre transaccional

**Problema:** distintas rutas cerraban ventanas con criterios diferentes; aplicaciones con datos dirty podían perder contenido.

**Contrato final:**

1. El cierre se solicita a `WindowManager`.
2. El manager consulta `window.request_close()`.
3. La ventana acepta, veta o solicita confirmación.
4. Solo después se ejecuta cleanup y se elimina la ventana.
5. `force=True` queda reservado para cleanup controlado.

### 4. Notepad protegido

Notepad usa el mismo protocolo para:

- botón de cierre;
- cierre desde taskbar/manager;
- salida de aplicación;
- abrir otro archivo con buffer dirty;
- confirmaciones de guardar, descartar o cancelar.

La confirmación captura la ventana fuente y no depende de cuál tenga foco al responder.

### 5. Terminal sigue drenando minimizada

**Problema:** el servicio PTY dependía de render o visibilidad.

**Contrato final:** `TerminalWindow.tick_when_hidden = True`. La sesión continúa leyendo, escribiendo y verificando el proceso mientras la ventana está minimizada.

El servicio oculto no fuerza redraw continuo; `tick()` invalida solo cuando cambia estado visual.

### 6. Contrato único de redraw

Se separaron tres conceptos:

- `wants_periodic_tick`: necesita cadence periódica;
- `tick_when_hidden`: necesita servicio oculta;
- retorno de `tick()`: cambió algo visible este ciclo.

El loop dejó de inspeccionar flags privados como `_animated` o `needs_redraw`.

La compatibilidad para plugins antiguos vive en `RetroApp`, no en el loop.

### 7. Circuit breaker del event loop

Los errores de hooks se contabilizan por separado.

- `tick()` y `draw()` tienen rachas independientes.
- Un hook se aísla después de fallos consecutivos.
- Un éxito reinicia la racha de ese hook.
- Los fallos de renderer usan backoff.
- Se conserva la primera causa útil para diagnóstico.

Una ventana o plugin defectuoso no debe derribar el escritorio completo.

### 8. Pares de color negociados

**Problema:** los IDs lógicos históricos podían exceder la capacidad real de `curses.COLOR_PAIRS`.

**Contrato final:**

- se conservan roles/IDs lógicos;
- se asignan pares físicos dentro de la capacidad;
- combinaciones idénticas se compactan;
- pair `0` sirve como degradación segura;
- redefinir un rol no corrompe otros roles que comparten par físico.

### 9. Scrollback sin duplicación

**Problema:** filas visibles podían agregarse manualmente y también por el scroll sink.

**Contrato final:**

- el grid normal es la fuente de verdad para el viewport;
- solo `scroll_up()` entrega filas expulsadas al deque;
- un newline dentro del viewport no duplica historial;
- `_scroll_lines` es una vista legacy calculada;
- reemplazar el deque requiere volver a enlazar el sink.

### 10. Tabs de RetroNet sin NameError

La geometría de click usa el mismo ancho real que el render. Se cubren:

- cambio de tab;
- cierre;
- creación;
- sidebar visible/oculto;
- límites del contenido.

### 11. CI recoge unittest y pytest

**Problema:** el gate ejecutaba solo una parte de la suite y pytest podía quedar invisible o saltarse tras un fallo de unittest.

**Contrato final:**

- `pytest` está en el extra de test;
- QA, unittest y pytest son pasos separados;
- pytest corre salvo cancelación del job;
- el gate cubre Ubuntu y Windows;
- Python 3.10, 3.12 y 3.14 están en la matriz;
- `windows-curses` y `pywinpty` son dependencias marcadas para Windows.

Durante el cierre del gate se corrigieron además diferencias de rutas Windows, mocks dependientes de versión, clipboard Unicode y ownership de SQLite expuestas por la matriz completa.

## P1 de estabilización completados

### 1. Workflows de diálogo tipados

Los diálogos dejaron de resolverse por títulos y texto visible.

Cada binding puede llevar:

- `workflow_id` estable;
- `source_window`;
- `source_window_id`;
- `on_accept`;
- `on_cancel`.

El dispatcher verifica que la ventana fuente todavía esté registrada. Un cambio de foco no redirige el resultado.

`dialog.callback` se conserva como alias de compatibilidad.

### 2. Precedencia de drag-and-drop

Orden autoritativo:

1. `accept_dropped_path()`;
2. `open_path()` solo como fallback.

Esto evita que un drop sobre File Manager se convierta en navegación en lugar de copia/move al directorio activo.

Si el handler específico falla, el fallback genérico no se ejecuta silenciosamente.

### 3. Presupuesto de lectura PTY

`TerminalSession.read()` limita por defecto el total agregado a 8 KiB por ciclo.

- POSIX puede hacer varias lecturas hasta el total.
- Los bytes restantes permanecen en el PTY.
- El decoder incremental recompone UTF-8 partido.
- presupuesto `0` no toca el backend;
- `None` permite drenaje ilimitado solo de forma explícita;
- ConPTY usa una lectura limitada equivalente.

### 4. Escrituras PTY parciales

`TerminalSession` mantiene una cola FIFO de bytes pendientes.

- `write()` acepta el payload completo en ownership de la sesión.
- `flush_pending_writes()` envía hasta 8 KiB por ciclo.
- una escritura corta elimina solo el prefijo confirmado;
- retorno `0`, `BlockingIOError` y `EAGAIN` preservan el sufijo;
- `tick()` flushea antes de leer salida;
- cierre exitoso descarta la cola de esa sesión.

### 5. Paridad del backend Windows

#### Spawn

ConPTY recibe:

- `cwd` solicitado;
- entorno heredado de `os.environ`;
- overrides/extensiones de `extra_env`;
- bloque de entorno separado por NUL.

Se soportan tres variantes de API:

1. keywords actuales;
2. argumentos posicionales;
3. argumento bytes legacy.

#### Cierre verificable

Eliminar la referencia Python ya no cuenta como cierre.

La secuencia:

1. intenta `close(force=True)`;
2. soporta `close()` sin keyword;
3. usa `cancel_io()` para backend raw;
4. envía SIGTERM por PID;
5. escala a señal forzada;
6. comprueba `isalive()` entre etapas.

Si no puede verificar la salida:

- `close()` devuelve false;
- conserva `_win_pty`;
- conserva la cola de entrada;
- mantiene estado coherente para que el caller reporte el fallo.

## Compatibilidad preservada

Se conservaron adaptadores donde retirar comportamiento habría sido un breaking change innecesario:

- `dialog.callback` como alias;
- flags de periodicidad de plugins traducidos en `RetroApp`;
- variantes legacy de `pywinpty.spawn()`;
- IDs lógicos históricos de colores;
- `_scroll_lines` como vista calculada.

La regla es que la compatibilidad viva en el borde y no reintroduzca una segunda autoridad dentro del core.

## Regresiones permanentes añadidas o ampliadas

La suite incluye contratos enfocados para:

- lifecycle de ventanas;
- close/request_close;
- EventBus;
- redraw y servicio oculto;
- circuit breaker;
- color capabilities;
- scrollback;
- tabs de RetroNet;
- dialog dispatch;
- drag-and-drop;
- presupuesto de lectura PTY;
- escrituras parciales;
- Windows spawn/cwd/env;
- Windows close y escalación;
- diferencias de Python y Windows expuestas por CI.

## Qué no certifica este gate

El gate automatizado no demuestra por sí solo:

- soporte universal de Unicode width;
- mouse correcto en cada emulador;
- comportamiento idéntico en GPM, SGR y multiplexers;
- compatibilidad completa de todas las secuencias ANSI;
- uso real de `vim`, `nano`, `mc`, `htop` o similares;
- calidad visual de cada tema en todas las paletas;
- comportamiento de SSH, tmux o screen;
- comportamiento de ConPTY en cada host Windows.

Esos puntos forman v0.9.6 y deben registrarse en [TTY_TEST_MATRIX.md](TTY_TEST_MATRIX.md).

## Deuda fuera de este gate

La auditoría contiene temas que no se seleccionaron como blockers del gate o pertenecen a milestones posteriores, por ejemplo:

- generation IDs y límites de respuesta de RetroNet;
- política TLS más estricta;
- ownership/cancelación general de background tasks;
- schema versionado y preservación de configuración desconocida;
- session restore;
- primer inicio;
- recuperación de plugins;
- feature freeze hacia 1.0.

No deben mezclarse retroactivamente con este gate. Deben entrar en el milestone correspondiente con alcance y regresiones propias.

## Reglas para no regresar

1. No insertar ventanas directamente en `app.windows`.
2. No cerrar aplicaciones dirty fuera de `request_close()`.
3. No hacer I/O de servicio dentro de `draw()`.
4. No añadir otro flag de redraw al loop.
5. No resolver diálogos por textos visibles.
6. No redirigir callbacks a la ventana activa actual.
7. No tratar `open_path()` como handler específico de drop.
8. No drenar PTY sin presupuesto desde el main loop.
9. No asumir que `os.write()` consume todo.
10. No declarar cerrado ConPTY sin una señal verificable.
11. No asumir una cantidad fija de pares de color.
12. No considerar protegido un test que CI no recoge.

## Siguiente paso

El trabajo debe continuar en v0.9.6 con pruebas reales y pequeñas correcciones basadas en evidencia.

Handoff operativo: [CODEX_NEXT_STEPS.md](CODEX_NEXT_STEPS.md).
