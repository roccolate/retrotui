# RetroTUI OS Roadmap (Sin X11/Wayland)

## Objetivo
Construir RetroTUI como entorno de usuario completo sobre Linux TTY/fbcon, sin depender de X11 ni Wayland, hasta uso diario.

## Principios
- Priorizar estabilidad y recuperacion de terminal sobre features nuevas.
- Cada fase debe cerrar con criterios de salida verificables.
- Evitar cambios grandes sin medicion (siempre medir antes/despues).

## Fase 0 - Baseline y observabilidad
Estado: `active`

### Tareas
- [ ] Definir metrica base: tiempo de arranque, redraws/segundo, uso CPU en idle, uso RAM.
- [x] Activar logs estructurados bajo `RETROTUI_DEBUG`.
- [x] Agregar un modo de profiling liviano (contadores de loop/eventos/redraw).
- [x] Guardar reportes de baseline en `docs/` (no en raiz).

### Criterios de salida
- [ ] Puedes comparar rendimiento antes/despues de cada optimizacion.
- [ ] Hay evidencia reproducible del baseline en al menos 2 terminales distintas.

## Fase 1 - Hardening de TTY (core de confiabilidad)
Estado: `pending`

### Tareas
- [ ] Manejo explicito de `SIGTERM`, `SIGINT`, `SIGHUP`.
- [ ] Crash handler: log persistente + mensaje legible en consola.
- [ ] Garantizar restauracion de estado TTY en salidas limpias y crashes.
- [ ] Reducir `except Exception` amplios en rutas criticas del core.
- [ ] Testear kill/restart repetidos sin terminal corrupta.

### Criterios de salida
- [ ] 0 corrupciones de terminal en pruebas de stress de senales.
- [ ] Toda salida de error fatal deja log util y terminal recuperada.

## Fase 2 - Session manager (comportamiento tipo sistema)
Estado: `pending`

### Tareas
- [ ] Definir modelo de sesion: ventanas abiertas, posiciones, app activa.
- [ ] Persistir/recuperar sesion en startup/shutdown.
- [ ] Implementar reinicio interno (soft restart) sin matar proceso principal.
- [ ] Separar ciclo de vida: boot -> init servicios -> run desktop -> shutdown.

### Criterios de salida
- [ ] Reiniciar RetroTUI conserva sesion minimamente usable.
- [ ] Startup y shutdown siguen flujo deterministico.

## Fase 3 - Servicios base desacoplados
Estado: `pending`

### Tareas
- [ ] Definir bus de eventos interno (acciones tipadas + payload validado).
- [ ] Encapsular servicios: filesystem, procesos, clipboard, configuracion.
- [ ] Eliminar acoplamientos directos de `app.py` a detalles de ventanas.
- [ ] Integrar `DialogDispatcher` real y remover duplicacion en `app.py`.

### Criterios de salida
- [ ] `retrotui/core/app.py` baja de complejidad y tamano (objetivo inicial: < 600 lineas).
- [ ] Cambios en un servicio no fuerzan cambios transversales en todo el core.

## Fase 4 - Input/Output robusto en consola pura
Estado: `pending`

### Tareas
- [ ] Consolidar estrategia de input para TTY real (teclado/mouse con degradacion elegante).
- [ ] Mejorar fallback cuando no hay capacidades completas de curses.
- [ ] Evaluar backend ANSI directo como plan B (solo si hay bloqueos reales de curses).
- [ ] Testear compatibilidad en terminals: Linux console, tmux, SSH.

### Criterios de salida
- [ ] RetroTUI arranca y funciona en TTY puro sin hacks manuales.
- [ ] Degradacion controlada cuando faltan features de terminal.

## Fase 5 - UX de daily driver
Estado: `pending`

### Tareas
- [ ] Pulir apps esenciales: terminal, file manager, notepad, settings, monitor sistema.
- [ ] Mejorar recuperacion de errores por app (sin tirar todo el entorno).
- [ ] Definir politicas de recursos (limites y watchdog de operaciones largas).
- [ ] Atajos y flujos de productividad consistentes.

### Criterios de salida
- [ ] Puedes pasar una sesion diaria de trabajo basica sin salir de RetroTUI.
- [ ] Errores de una app no derriban el entorno completo.

## Fase 6 - Boot como entorno principal (sin X11/Wayland)
Estado: `pending`

### Tareas
- [ ] Crear unidad `systemd` para lanzar RetroTUI en `tty1`.
- [ ] Definir modo usuario dedicado (autologin opcional).
- [ ] Script de instalacion para host limpio (dependencias minimas).
- [ ] Procedimiento de rollback seguro.

### Criterios de salida
- [ ] El sistema bootea directo a RetroTUI de forma estable.
- [ ] Hay proceso de instalacion y reversa documentado.

## Fase 7 - Distribucion e imagen reproducible
Estado: `pending`

### Tareas
- [ ] Elegir base (Debian/Alpine minimal) y generar imagen reproducible.
- [ ] Pipeline de release con smoke tests en consola.
- [ ] Versionado de compatibilidad para plugins/servicios.

### Criterios de salida
- [ ] Cualquier persona del equipo puede recrear una imagen funcional.
- [ ] Release candidate valida en hardware/VM objetivo.

## Backlog tecnico inmediato (sprint propuesto)
- [ ] Integrar `DialogDispatcher` en runtime y eliminar duplicado en `app.py`.
- [ ] Reemplazar delegacion `__getattr__` de file ops por wrappers explicitos.
- [ ] Afinar loop de redraw con metrica de eventos reales.
- [ ] Normalizar manejo de errores del core (tipos concretos + logs).

## Definicion de Done por tarea
- [ ] Codigo implementado.
- [ ] Tests unitarios/regresion en verde.
- [ ] Validacion manual en TTY documentada.
- [ ] Cambio registrado en changelog o release notes.

## Riesgos principales
- Complejidad accidental en `app.py` al agregar features sin extraer servicios.
- Fragilidad de terminales no homogeneas (SSH/tmux/consola Linux).
- Falta de metricas objetivas para decisiones de rendimiento.

## Regla operativa
No abrir una fase nueva si la anterior no cumple criterios de salida.

## Plan 2 Semanas (Ejecucion)
Objetivo del sprint: cerrar base de confiabilidad + arquitectura minima para iterar rapido sin degradar rendimiento.

### Prioridades
- `P0`: bloquea vision "sistema" o puede romper sesion TTY.
- `P1`: mejora fuerte de mantenibilidad/rendimiento.
- `P2`: mejora incremental, no bloqueante.

### Semana 1
#### Dia 1
- [ ] `P0` Definir y registrar baseline de metricas (arranque, redraw, CPU idle, RAM).
- [ ] `P0` Activar bandera de profiling por `RETROTUI_DEBUG`.
- Entregable: reporte baseline en `docs/`.

#### Dia 2
- [ ] `P0` Manejar `SIGTERM/SIGINT/SIGHUP` con salida limpia.
- [ ] `P0` Verificar restauracion de terminal tras kill.
- Entregable: tests de senales + checklist manual TTY.

#### Dia 3
- [ ] `P0` Crash handler con log persistente.
- [ ] `P1` Pantalla de error fatal legible para usuario final.
- Entregable: log reproducible de crash y salida limpia.

#### Dia 4
- [ ] `P1` Integrar `DialogDispatcher` real en runtime.
- [ ] `P1` Eliminar duplicacion de dispatch en `app.py`.
- Entregable: `app.py` mas corto y tests en verde.

#### Dia 5
- [ ] `P1` Reemplazar `__getattr__` de file ops por wrappers explicitos.
- [ ] `P1` Mantener compatibilidad de tests existentes.
- Entregable: interfaces explicitas para file ops.

### Semana 2
#### Dia 6
- [ ] `P1` Auditar `except Exception` del core y tipar excepciones reales.
- [ ] `P1` Mejorar logs con contexto (modulo/accion/payload).
- Entregable: reduccion de capturas genericas en rutas criticas.

#### Dia 7
- [ ] `P1` Pulir event loop: menos redraws espurios con metrica real.
- [ ] `P2` Ajustar thresholds de invalidacion `_dirty`.
- Entregable: comparativa before/after de redraw ratio.

#### Dia 8
- [ ] `P0` Implementar esqueleto de session manager (save/restore minimo).
- [ ] `P1` Persistir ventanas basicas (tipo, pos, tamano, activa).
- Entregable: restauracion basica funcional tras reinicio.

#### Dia 9
- [ ] `P0` Soft restart interno (`run loop` reiniciable).
- [ ] `P1` Flujo boot -> init -> run -> shutdown bien separado.
- Entregable: reinicio sin matar proceso principal.

#### Dia 10
- [ ] `P0` Hardening final en TTY real (pruebas manuales).
- [ ] `P1` Documentar operacion + rollback.
- Entregable: release candidate interno del sprint.

## Exit Criteria del Sprint (obligatorio)
- [ ] No corrupcion de terminal en pruebas de senales y crashes.
- [ ] Baseline y post-optimizacion comparables con evidencia.
- [ ] `app.py` reduce complejidad y elimina duplicaciones criticas.
- [ ] Session save/restore minimo funcionando.
- [ ] Suite de tests core relevante en verde.

## Orden de implementacion recomendado
1. Confiabilidad TTY (`P0`).
2. Eliminacion de deuda estructural en `core/app.py` (`P1`).
3. Optimizaciones con metrica (`P1`).
4. Session manager + soft restart (`P0/P1`).

## Backlog de Optimizacion Core (Analisis Actual)
Estado: `active`

### `P0` Rendimiento inmediato
- [ ] Optimizar `DragDropManager.set_drag_target` para no recorrer todas las ventanas si el target no cambia.
- [ ] Actualizar highlight solo en ventana previa/nueva, no en lista completa.
- [ ] Calcular tamaño terminal (`h,w`) una vez por frame y pasarlo a rendering helpers.
- [ ] Reducir trabajo de `draw_statusbar`/`draw_taskbar` con datos cacheados del window manager.

### `P1` Estructura y hot paths
- [ ] Integrar `DialogDispatcher` en runtime y eliminar dispatch duplicado en `core/app.py`.
- [ ] Reducir trabajo en `handle_window_mouse` cerrando solo menu activo (no escanear todas las ventanas por click).
- [ ] Revisar doble `poll_background_operation()` por iteracion y simplificar a una ruta deterministica.
- [ ] Sustituir rutas con `except Exception` en hot paths por excepciones concretas.

### `P0` Input para modo "sistema"
- [ ] Definir politica de `Ctrl+C` en sesion normal (no expulsar a TTY).
- [ ] Implementar captura/mapeo robusto de `SIGINT` y/o modo input adecuado.
- [ ] Añadir capa de normalizacion de eventos mouse por backend (SGR vs GPM).
- [ ] Corregir click derecho y drag en GPM con pruebas dedicadas.

### `P1` Observabilidad para optimizacion
- [ ] Exponer metricas de loop (`events`, `redraws`, `redraw_ratio`) bajo `RETROTUI_DEBUG`.
- [ ] Guardar comparativas baseline vs post-optimizacion por sprint.

### Criterios de salida de esta linea de optimizacion
- [ ] Menos redraws sin perdida funcional (medido).
- [ ] Drag-and-drop mantiene comportamiento y reduce trabajo por evento.
- [ ] En GPM: click derecho y drag operativos en ventanas/desktop.
- [ ] `core/app.py` baja complejidad y elimina duplicaciones criticas.

## Plan de Arquitectura Evolutiva (Sin Big-Bang)
Estado: `active`

Objetivo: transformar RetroTUI hacia entorno tipo sistema, manteniendo compatibilidad y velocidad de entrega.

### Principios de refactor
- [ ] Refactor incremental en vertical slices (no migraciones masivas).
- [ ] Cada cambio arquitectonico debe traer tests + metrica.
- [ ] Mantener adaptadores de compatibilidad hasta cerrar fase.

### Hito A - Orquestador minimo en `core/app.py`
Prioridad: `P0`

#### Tareas
- [ ] Convertir `core/app.py` en coordinador (menos logica de dominio).
- [ ] Extraer dispatch de resultados/dialogos a servicio runtime unico.
- [ ] Eliminar duplicaciones de rutas de accion y manejo de dialogos.

#### Criterio de salida
- [ ] `core/app.py` con menor complejidad ciclomatica y responsabilidades claras.

### Hito B - Servicios de dominio (`core/services/`)
Prioridad: `P1`

#### Tareas
- [ ] Crear `session_service` (save/restore + soft restart hooks).
- [ ] Crear `input_service` (policy de atajos, `Ctrl+C`, conflictos globales).
- [ ] Crear `window_service` (estado/counters/caches para rendering).
- [ ] Crear `action_service` (dispatch tipado y registro de acciones/apps).

#### Criterio de salida
- [ ] Las rutas criticas dependen de interfaces de servicio, no de detalles internos.

### Hito C - Capa de plataforma (`core/platform/`)
Prioridad: `P0`

#### Tareas
- [ ] Introducir normalizador de eventos de entrada para backends (`SGR`, `GPM`, fallback).
- [ ] Estabilizar contrato de mouse (`click`, `drag`, `right_click`, `scroll`) cross-backend.
- [ ] Encapsular diferencias TTY/Linux console para no contaminar el core.

#### Criterio de salida
- [ ] Mismo comportamiento funcional en entornos con backend de mouse distinto.

### Hito D - Contratos y versionado de apps
Prioridad: `P1`

#### Tareas
- [ ] Definir contrato comun de app/plugin (`id`, `version`, `capabilities`).
- [ ] Mostrar version de app en UI (About/Properties/contexto).
- [ ] Validar compatibilidad de plugins contra version de contrato.

#### Criterio de salida
- [ ] Todas las apps core exponen metadata consistente y visible.

### Hito E - Estructura destino (referencia)
Prioridad: `P2`

```
retrotui/
  core/
    app.py
    services/
      session_service.py
      input_service.py
      window_service.py
      action_service.py
    platform/
      mouse_backend.py
      tty_capabilities.py
      signal_manager.py
    contracts/
      actions.py
      app_manifest.py
      events.py
  apps/
  plugins/
```

### Riesgos y mitigacion
- Riesgo: sobre-refactor sin valor inmediato.
  Mitigacion: cada PR debe incluir mejora medible o deuda eliminada concreta.
- Riesgo: ruptura de comportamiento en apps existentes.
  Mitigacion: adapters temporales + tests de regresion por modulo.
- Riesgo: divergencia entre backends de mouse.
  Mitigacion: test matrix dedicada `SGR/GPM/fallback`.

### Exit criteria de arquitectura
- [ ] `core/app.py` queda como orquestador y no concentra logica de negocio.
- [ ] Servicios principales aislados y testeados.
- [ ] Capa de plataforma unifica eventos de input.
- [ ] Compatibilidad funcional mantenida en tests core y pruebas manuales TTY.

## Requisitos Criticos (No Negociables)
Estado: `active`

### Input/UX
- [ ] `P0` Copy/Paste y drag-and-drop consistentes entre apps.
- [ ] `P0` Mapeo de atajos universales y politica de conflictos (`Ctrl+C`, `Ctrl+Q`, etc.).
- [ ] `P0` Evitar salida accidental a TTY por combinaciones globales.

### Mouse en consola Linux (GPM)
- [ ] `P0` Mejorar soporte GPM para drag de ventanas (mover/redimensionar).
- [ ] `P0` Habilitar click derecho funcional bajo GPM.
- [ ] `P1` Compatibilidad de comportamiento entre GPM y terminals con mouse SGR.

### Versionado de apps
- [ ] `P1` Definir `app_version` por app/plugin visible en UI.
- [ ] `P1` Mostrar version en About/Propiedades/contexto de app.

### Criterios de salida especificos
- [ ] `P0` En GPM: click izquierdo, derecho y drag operan en ventanas y desktop.
- [ ] `P0` `Ctrl+C` no expulsa al usuario de RetroTUI durante sesion normal.
- [ ] `P0` Copy/Paste y arrastre se comportan igual en apps core principales.
