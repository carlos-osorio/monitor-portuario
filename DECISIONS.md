# Bitácora de decisiones — monitor-portuario

Registro de decisiones de diseño y fallas instructivas. Formato: lo más
reciente arriba. Complementa al README (qué es y cómo se opera el sistema);
aquí vive el *porqué* de lo no evidente.

---
## 2026-07-17 — Regla de piso: red de seguridad contra la ceguera del z

**Problema:** en series de alta dispersión acotadas en cero (Barranquilla-expo,
MAD/mediana ≈ 0,5), el z de choque no puede alcanzar -3 ni ante un colapso total
—el piso en cero está a ~1,3 MAD de la mediana—. El z dio -1,19 ("normal") ante
una caída del 94% real (semana 2026-07-05, percentil 1-2 histórico).

**Regla:** si la semana cae bajo el percentil 1 móvil (ventana 52 sem, solo
pasado) del puerto, se emite advertencia —independiente del z—. Aplica a impo y
expo; suspendida en semanas festivas.

**Calibración (backtest, notebook 05):** P1 caza la semana 2026-07-05 de
Barranquilla-expo; tasa ~4,5/año (impo) y ~6/año (expo); >95% de sus alertas
son invisibles al z (complementa, no duplica). P2/P3 saturan. Sin condición de
magnitud en v1: la regla solo advierte, el costo de una alerta de más es bajo y
el de perder un colapso es justo el agujero que cierra. Condición de magnitud
(caída ≥40% además de bajo piso) queda para v1.5 si resulta ruidosa en operación.

---
## 2026-07-10 - Recalculo de topes impo/expo/portcalls

**Contexto:** Topes iniciales calibrados contra percentil e intuición quedaron al filo del máximo histórico; recalibrados a máx × 1.5 (portcalls 40, import 370.000, export 320.000). 

**Lección:** umbrales de advertencia se anclan al extremo observado, no al valor típico


---

## 2026-07-06 — Confusión Rerun jobs con Run workflow

**Contexto:** eRe-run jobs re-ejecuta el commit original de la corrida, no el estado actual de main; tres 'fallas' consecutivas eran la versión pre-arreglo repitiéndose.

**Lección:** antes de diagnosticar 'el arreglo no funcionó', verificar contra qué commit corrió — el hash está en el encabezado de la corrida

---


## 2026-07-06 — Convención de fechas de los snapshots: [UTC / hora Bogotá]

**Contexto:** el workflow corre en máquinas de GitHub Actions, que viven en UTC
(UTC−5 respecto a Bogotá). Una corrida disparada un lunes 7 pm de Bogotá genera
el snapshot con fecha del martes.

**Decisión:** Forzar Bogotá

**Porqué:** Los análisis y lecturas están dirigidos para potenciales usuarios en Colombia

---

## 2026-07-06 — Falla instructiva: push rechazado por condición de carrera

**Qué pasó:** la corrida manual falló en rojo con `! [rejected] main -> main`.
Mientras la máquina de Actions trabajaba sobre su clon del repo, entró un commit
desde la interfaz web (edición del workflow); al intentar el push, git rechazó
correctamente empujar sobre un remoto más nuevo.

**Corrección:** se añadió `git pull --rebase origin main` antes del push.

**Lección:** dos actores escribiendo sobre el mismo repositorio sin coordinarse
chocan (condición de carrera). El rechazo fue una falla *ruidosa* — visible y
diagnosticable el mismo día — que es el comportamiento deseado.

---

## 2026-07-06 — Falso diagnóstico: "no veo el commit del bot"

**Qué pasó:** el commit del snapshot parecía no existir; el diagnóstico inicial
(falla silenciosa en el guardado) se construyó sin leer los logs. El log mostró
commit y push exitosos; el commit aparecía bajo el autor "actions-user" porque
GitHub asocia la cuenta por el correo configurado, no por el `user.name`.

**Lección:** el reporte de un humano ("no lo veo") no es un hecho del sistema;
el log y el hash del commit sí. Verificar por contenido y hash, no por nombre.

---

## 2026-07-05 — Guardado del caso "sin cambios" con `if` explícito, no con `||`

**Contexto:** `git commit` falla por diseño cuando no hay nada que guardar
(caso benigno: snapshot idéntico al existente). La versión inicial usaba
`git commit ... || echo "..."`, que traga *cualquier* causa de fallo.

**Decisión:** preguntar explícitamente si hay cambios (`git diff --cached
--quiet`) y bifurcar: mensaje benigno, o commit+push sin red de seguridad.

**Porqué:** en un pipeline sin humano en el bucle, los errores no anticipados
deben ser ruidosos (fail fast). Un `||` genérico convierte fallas malignas en
silencio verde.

---

## 2026-07-05 — Snapshots dentro del repo, no en almacenamiento externo

**Contexto:** cada corrida semanal guarda un CSV (~480 KB → ~25 MB/año).

**Decisión:** los snapshots viven en `data/` dentro del repositorio.

**Porqué:** a esta escala, git da historial y diffs gratis, sin infraestructura
adicional (restricción de costo mínimo del proyecto). Se migrará a
almacenamiento externo si el peso del repo lo exige; esa migración se
documentará aquí.

---

## 2026-07-05 — Indicadores con roles asimétricos: tonelaje alerta, port calls contextualiza

**Contexto:** en la exploración, el paro nacional de 2021 no se vio en port
calls pero colapsó el tonelaje estimado de Buenaventura: las llegadas miden el
lado marítimo; el tonelaje, el flujo de comercio.

**Decisión:** el tonelaje import/export es el único indicador que dispara
alertas; los port calls acompañan como contexto diagnóstico (tonelaje cae y
llegadas no → fricción terrestre; caen ambos → disrupción marítima).

**Porqué:** dos sistemas de alertas en paralelo duplican mantenimiento y falsas
alarmas; la asimetría captura la lógica de dominio con la mínima superficie.
