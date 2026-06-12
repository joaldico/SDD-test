# 1. Intención del Producto (Intent) — Módulo 1: Conciliador de Errores de Publicación Marketplace

> **Fase SDD:** `1/4 — Intent`
> **Estado:** `🟡 En revisión — pendiente de aprobación (v1.2.0)`
> **Versión:** `1.2.0` — añade detección de desincronización de catálogo, priorización por stock y gestión de duplicados
> **Última actualización:** 2026-06-11
> **Autor(es):** Josué (Solicitud de Operaciones) / Arquitecto de Soluciones IA & Senior Full Stack Engineer
> **Contexto de plataforma:** Primer módulo de una plataforma SaaS multi-módulo. Las decisiones de este documento sientan las bases (shell de navegación, autenticación, ingesta de ficheros) que reutilizarán los módulos futuros.

---

## 1.1. Declaración de Intención (Elevator Pitch)

```text
Automatizar la conciliación entre el catálogo interno (OCC), el feed enviado a Amazon ES
(WaveMarket) y el reporte de errores de publicación (ListingLoader), sustituyendo los cruces
manuales de Excel por una plataforma web donde un usuario de negocio sube los 3 ficheros,
CONFIRMA QUÉ COLUMNA CONTIENE EL SKU EN CADA UNO, y obtiene un informe auditable y exportable:
errores agregados por tipo, detalle por SKU, SKUs DESINCRONIZADOS entre Amazon y WaveMarket
(priorizados por disponibilidad real de stock) y duplicados detectados. Es el primer módulo
de una plataforma SaaS diseñada para crecer hacia más marketplaces y automatizaciones.
```

---

## 1.2. Problema a Resolver

| Campo | Descripción |
|---|---|
| **Problema central** | Correlación manual de 3 ficheros heterogéneos (`Libro1.xlsx` — top ventas OCC ausentes en Amazon ES; `amazon_ES_fullstock_*` — feed de WaveMarket; `ListingLoader*-processing-summary` — errores de publicación) para identificar qué SKUs enviados fallaron y por qué. Agravantes críticos: (a) **la columna que contiene el SKU no es conocida a priori ni consistente entre ficheros ni entre versiones del mismo fichero**, lo que invalida cualquier cruce automático ciego; (b) **las fuentes pueden estar desincronizadas entre sí**: el fichero procedente de Amazon puede contener SKUs realmente publicados que el feed de WaveMarket ya no incluye (o viceversa), por lo que la ausencia de un SKU en una fuente no implica que no exista en el marketplace; (c) **pueden existir SKUs duplicados** dentro de los ficheros, lo que falsea conteos y cruces si no se detectan antes de conciliar. |
| **Afectados** | Equipos de Operaciones y E-commerce Managers (perfiles no técnicos), y el equipo técnico que hereda peticiones manuales recurrentes. |
| **Costo de no actuar** | Productos de alta rotación fuera de línea durante días (pérdida directa de facturación), horas-persona en cruces VLOOKUP propensos a error, y ausencia de histórico para detectar errores de publicación recurrentes. |
| **Soluciones actuales** | Cruces manuales en Excel (VLOOKUP/XLOOKUP) ejecutados localmente: sin trazabilidad, sin histórico, no escalable y dependiente de que la persona "adivine" la columna de SKU correcta en cada fichero. |

---

## 1.3. Visión de la Solución

Aplicación web desacoplada (frontend SPA + API backend + base de datos relacional) montada sobre un *shell* de navegación multi-módulo: este conciliador es el Módulo 1 y la plataforma debe poder registrar módulos futuros sin rediseño.

- **Qué hará:**
  - **Carga guiada de los 3 ficheros** en un solo flujo (arrastrar y soltar), tolerante a formatos heterogéneos (`.xlsx`, `.csv`, `.txt` delimitado) y codificaciones diversas.
  - **Asistente de mapeo de columnas (paso obligatorio y bloqueante):** tras la carga, el sistema muestra una previsualización de cada fichero (cabeceras + filas de muestra) y el usuario **debe indicar qué columna contiene el SKU en cada fichero** —y, en el feed, **qué columna contiene el stock disponible**— antes de que el proceso continúe. El sistema puede *sugerir* candidatas por heurística, pero la confirmación humana es requisito previo al procesamiento.
  - **Saneamiento previo al cruce — duplicados:** antes de conciliar, el sistema detecta SKUs duplicados dentro de cada fichero (tras normalización), los reporta al usuario con su recuento y filas de origen, y aplica una política explícita de resolución (definida en `2_spec.md`) en lugar de dejar que dupliquen resultados silenciosamente.
  - **Conciliación en dos pasos:** (1) verificar qué SKUs de `Libro1` existen en el feed `fullstock` (= enviados a Amazon); (2) cruzar los enviados contra el `processing-summary` para asignar tipo y descripción de error a cada SKU.
  - **Detección de desincronización de catálogo:** el cruce es bidireccional, no ciego en un solo sentido. Los SKUs presentes en el fichero de Amazon pero ausentes del feed de WaveMarket (y viceversa) se **destacan como desincronizados**, porque la desincronización entre sistemas es en sí misma un hallazgo accionable, no un dato a descartar.
  - **Priorización por stock real:** entre los SKUs desincronizados o con error, se destacan los que **tienen stock disponible** (columna de stock confirmada en el mapeo), pues representan pérdida de venta activa y son los de gestión prioritaria.
  - **Informe en vistas:** Vista/Tab 1 — agregado de SKUs por tipo de error; Vista/Tab 2 — detalle granular (SKU, tipo de error, descripción del error); Vista/Tab 3 — salud de catálogo: SKUs desincronizados Amazon ↔ WaveMarket destacando los que tienen stock, y duplicados detectados por fichero. Todas **exportables** (el entregable original solicitado es un informe, no solo un dashboard).
  - **Persistencia auditable:** cada ejecución de conciliación se guarda (ficheros origen, mapeo confirmado, resultados, desincronizaciones, duplicados, usuario, fecha) para histórico y análisis de recurrencia.
  - **Autenticación robusta** con sesiones renovables de forma transparente (JWT Access + Refresh).
- **Qué NO hará (anti-objetivos del MVP):**
  - No modificará el catálogo en Amazon Seller Central (sin escritura vía SP-API).
  - No habrá detección 100% automática de la columna SKU sin confirmación humana (la heurística solo sugiere, nunca decide).
  - No habrá edición manual de los registros de error desde la interfaz.
  - No habrá multi-tenancy facturable ni gestión de organizaciones (se diseña para no impedirlo, pero no se implementa).
  - No habrá alertas automáticas por email (preparado para módulo futuro).
- **Diferenciador clave:** Convierte un cruce manual frágil en un flujo guiado con validación humana en el punto exacto de mayor incertidumbre (el mapeo de columnas), generando telemetría histórica auditable y dejando la base arquitectónica del resto de la plataforma SaaS.

---

## 1.4. Usuarios y Stakeholders

| Actor | Tipo | Necesidad principal | Nivel de impacto |
|---|---|---|---|
| **Gestor de E-commerce / Operaciones** | Primario | Subir ficheros, confirmar columnas de SKU con una previsualización clara, y obtener/exportar el informe sin tocar Excel. | Crítico |
| **Equipo Técnico / DevOps** | Secundario | Infraestructura reproducible (Docker), despliegues automatizados (CI/CD → AWS EC2) y diseño listo para K8s. | Alto |
| **Plataforma SaaS (módulos futuros)** | Sistema | API REST segura, modelo de datos extensible y shell de navegación que admita nuevos módulos. | Alto |
| **Sistemas de automatización futuros** | Sistema | Telemetría persistida en MySQL consultable para orquestar alertas. | Medio |

---

## 1.5. Objetivos de Negocio y Métricas de Éxito

| ID | Objetivo | Métrica (KPI) | Valor objetivo | Plazo |
|---|---|---|---|---|
| **OBJ-01** | Respuesta inmediata de la UI en la ingesta. | Tiempo entre carga de ficheros y previsualización para mapeo de columnas. | < 3 s (ficheros ≤ 50 MB) | MVP |
| **OBJ-02** | Procesamiento sin bloquear la experiencia. | Tiempo de conciliación completa (asíncrona, con estado visible) para ficheros de hasta 100k filas. | p95 < 30 s | MVP |
| **OBJ-03** | Eliminar cruces erróneos por columna equivocada. | % de ejecuciones con mapeo de SKU confirmado explícitamente por el usuario antes de procesar. | 100% (gate obligatorio) | MVP |
| **OBJ-04** | Centralizar la telemetría de fallos. | % de SKUs con error capturados y persistidos en MySQL por ejecución. | 100% | MVP |
| **OBJ-05** | Continuidad de sesión sin fricción. | Bloqueos de sesión por expiración no renovada. | 0 | MVP |
| **OBJ-06** | Eliminar la dependencia de Excel local. | Tasa de uso de Excel para esta tarea por el equipo operativo. | 0% | 1 mes post-MVP |
| **OBJ-07** | Visibilizar la desincronización de catálogo entre Amazon y WaveMarket. | % de SKUs presentes en una fuente y ausentes en la otra que quedan destacados en el informe, marcando los que tienen stock disponible. | 100% | MVP |
| **OBJ-08** | Garantizar la integridad del cruce frente a duplicados. | % de SKUs duplicados (por fichero, tras normalización) detectados y reportados antes de la conciliación. | 100% | MVP |

---

## 1.6. Restricciones Globales

- **Técnicas:**
  - Backend: Python (FastAPI). Frontend: React (SPA). Base de datos: MySQL.
  - Autenticación: flujo JWT completo (Access Token de corta duración + Refresh Token seguro), alineado con OWASP API Security.
  - Despliegue: contenedores Docker obligatorios (paridad dev local Ubuntu ↔ producción).
  - CI/CD: GitHub Actions con despliegue a instancia AWS EC2.
  - Escalabilidad: separación estricta frontend/backend/datos y servicios *stateless*, preparados para migración a Kubernetes sin refactorización de la lógica de negocio.
  - Procesamiento de datos: la transformación pesada (Pandas) nunca debe ejecutarse en el hilo del event loop de la API.
- **Regulatorias / Cumplimiento:** acceso restringido por autenticación y roles (RBAC vía claims del token firmado); los datos de inventario/errores no se exponen sin autorización.
- **Presupuesto / Tiempo:** enfoque *fast-track* para el MVP, sin comprometer la limpieza arquitectónica (el módulo 1 define los cimientos de toda la plataforma: lo que se ensucie aquí se hereda).

---

## 1.7. Supuestos y Riesgos Iniciales

| ID | Tipo | Descripción | Probabilidad | Impacto | Mitigación inicial |
|---|---|---|---|---|---|
| **RSK-01** | Riesgo | **La columna que contiene el SKU es desconocida e inconsistente entre ficheros y versiones.** Un cruce ciego produciría informes silenciosamente erróneos. | Alta | Crítico | Asistente de mapeo obligatorio: previsualización + confirmación humana de la columna SKU por fichero antes de procesar. Heurística de sugerencia (nombres candidatos, patrones de valores) solo como ayuda. El mapeo confirmado se persiste por ejecución (auditoría) y se ofrece como predeterminado en cargas futuras del mismo tipo de fichero. |
| **RSK-02** | Riesgo | Formatos y codificaciones heterogéneos (`.xlsx`, `.csv`, `.txt`, delimitadores y encodings variables) rompen la ingesta. | Alta | Alto | Capa de ingesta con detección de formato/encoding/delimitador y validación con esquemas estrictos (Pydantic) antes de pasar a transformación; errores de ingesta reportados al usuario en lenguaje claro. |
| **RSK-03** | Riesgo | Ficheros de gran volumen bloquean el event loop de FastAPI durante la transformación con Pandas. | Media | Alto | Procesamiento asíncrono fuera del event loop (workers/threads o `BackgroundTasks`), con estado de progreso consultable desde la UI. El diseño debe permitir sustituirlo por una cola dedicada (p. ej. Celery/Redis) al escalar, sin cambiar el contrato de la API. |
| **RSK-04** | Riesgo | Conexiones MySQL sin cerrar degradan el pool en sesiones largas. | Baja | Medio | Inyección de dependencias de FastAPI con ciclo de vida gestionado (`yield`) y pool con límites configurados. |
| **RSK-05** | Riesgo | **Desincronización entre fuentes:** el fichero de Amazon puede contener SKUs realmente publicados que el feed de WaveMarket no incluye (o al revés). Tratar la ausencia en una fuente como "no enviado" produciría conclusiones falsas y ocultaría el problema real de sincronización. | Alta | Alto | Cruce bidireccional con clasificación explícita de cada SKU (en ambas fuentes / solo Amazon / solo WaveMarket) y vista dedicada de desincronización, destacando los SKUs con stock disponible como gestión prioritaria. |
| **RSK-06** | Riesgo | **SKUs duplicados** dentro de un fichero (filas repetidas, variantes mal exportadas) inflan métricas y generan cruces ambiguos (un SKU casa con N filas). | Media | Alto | Detección de duplicados tras normalización, antes del cruce; reporte al usuario con recuento y filas afectadas; política de resolución explícita definida en `2_spec.md` (nunca resolución silenciosa). |
| **SUP-01** | Supuesto | Los SKUs son comparables entre ficheros tras una normalización ligera (trim, mayúsculas, ceros a la izquierda). | — | — | Validar con muestras reales en la fase de spec; definir reglas de normalización explícitas en `2_spec.md`. |
| **SUP-02** | Supuesto | El `processing-summary` de Amazon contiene columnas identificables de tipo y descripción de error (aunque su posición/nombre varíe). | — | — | El asistente de mapeo cubre también estas columnas, no solo el SKU. |
| **SUP-03** | Supuesto | El feed contiene una columna de stock disponible interpretable numéricamente para priorizar la gestión. | — | — | La columna de stock se confirma en el asistente de mapeo; si no existe o no es numérica, el informe lo indica y la priorización por stock se omite de forma explícita (nunca se infiere). |

---

## 1.8. Glosario del Dominio

| Término | Definición |
|---|---|
| **SKU (Stock Keeping Unit)** | Identificador único de artículo para gestión de inventario; clave de cruce entre los 3 ficheros. |
| **OCC** | Catálogo/canal interno origen de la lista de productos más vendidos (`Libro1.xlsx`). |
| **WaveMarket** | Sistema que genera el feed de producto enviado a Amazon (`amazon_ES_fullstock_*`). |
| **Feed de Producto** | Fichero consolidado de inventario/stock estructurado para envío a un marketplace. |
| **ListingLoader Report (processing-summary)** | Fichero de resultados que emite Amazon tras una publicación masiva, con códigos y descripciones de error por SKU. |
| **Mapeo de columnas** | Asignación explícita y confirmada por el usuario de qué columna de cada fichero contiene cada campo lógico (SKU, stock, tipo de error, descripción). |
| **SKU desincronizado** | SKU presente en una fuente (Amazon o feed WaveMarket) y ausente en la otra tras normalización; evidencia de desfase entre sistemas y hallazgo accionable del informe. |
| **SKU duplicado** | SKU que aparece en más de una fila del mismo fichero tras normalización; debe detectarse y resolverse con política explícita antes del cruce. |
| **Stock disponible** | Cantidad vendible declarada en el feed para un SKU; criterio de priorización de gestión (un SKU desincronizado o con error y con stock > 0 es pérdida de venta activa). |
| **Ejecución de conciliación** | Unidad auditable de trabajo: ficheros cargados + mapeo confirmado + resultados generados (errores, desincronizaciones, duplicados) + usuario + timestamp. |
| **JWT (JSON Web Token)** | Estándar de transmisión de identidad firmada entre cliente y servidor (Access + Refresh). |

---

## ✅ Criterio de salida de fase (Gate)

- [x] La declaración de intención es inequívoca e incluye el paso bloqueante de confirmación de columna SKU.
- [x] Stakeholders identificados, incluida la plataforma SaaS como consumidor futuro de los cimientos del módulo.
- [x] Cada objetivo tiene métrica medible; los objetivos de latencia distinguen respuesta de UI (OBJ-01) de procesamiento asíncrono (OBJ-02), sin contradicción.
- [x] Anti-objetivos explícitos (sin escritura en Amazon, sin auto-detección sin confirmación, sin multi-tenancy facturable, sin alertas email en MVP).
- [x] El riesgo crítico del dominio (columna SKU desconocida) está promovido a requisito de producto, no enterrado como supuesto.
- [x] La desincronización entre fuentes (Amazon ↔ WaveMarket) se trata como hallazgo de primera clase con cruce bidireccional y priorización por stock disponible (OBJ-07, RSK-05, SUP-03).
- [x] La detección de duplicados es un paso previo obligatorio del cruce con política de resolución explícita (OBJ-08, RSK-06).
- [ ] **Aprobación del solicitante de la v1.2.0** (requisito para iniciar `2_spec.md`).

> **Siguiente fase (bloqueada hasta aprobación):** [`2_spec.md`](./2_spec.md) — Especificación funcional: flujo del asistente de mapeo (SKU + stock), reglas de normalización de SKU, política de resolución de duplicados, clasificación de desincronización y criterios de aceptación BDD en Gherkin.
