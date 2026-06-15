# 4. Desglose de Tareas (Tasks) — Módulo 1: Conciliador de Errores de Publicación Marketplace

> **Fase SDD:** `4/4 — Task Breakdown`
> **Estado:** `🔵 En ejecución — Hito M3 cerrado (2026-06-15)`
> **Versión:** `1.1.0`
> **Última actualización:** 2026-06-15
> **Trazabilidad:** ejecuta [`3_plan.md`](./3_plan.md) v1.0.0 (🟢 Aprobado), verifica contra [`2_spec.md`](./2_spec.md) v1.1.0 (🟢 Aprobado)
> **Rol de autoría:** Technical Lead / Scrum Master
> **Uso previsto:** backlog para sesiones cortas de programación asistida por agente. Cada tarea está dimensionada para completarse (con sus tests) en una sesión. **Las tareas se ejecutan en orden estricto dentro de cada hito**; las dependencias entre hitos están explícitas.

---

## 4.1. Convenciones de Trabajo

- **ID:** `T-<hito>.<secuencia>`. El orden de secuencia ES el orden de ejecución.
- **Metodología TDD obligatoria:** cada tarea comienza escribiendo el test (unitario, integración o BDD) que la define; la tarea termina cuando ese test pasa. Los escenarios Gherkin CA-01..CA-05 de `2_spec.md` se implementan **literalmente** con `pytest-bdd` y son los gates de los hitos funcionales.
- **Fixtures canónicos:** versiones anonimizadas de los 3 ficheros reales del cliente (`Libro1`, `fullstock`, `processing-summary`) se incorporan en `tests/fixtures/` en T-1.2 y son la base de todos los tests de ingesta y conciliación.
- **Estimaciones:** `S` ≤ media sesión · `M` 1 sesión · `L` 1 sesión larga (si una tarea crece más, se parte antes de empezarla).

### Definition of Done (DoD) global — aplica a TODA tarea además de su DoD propio

- [ ] Test escrito ANTES de la implementación y en verde al cerrar (TDD: rojo → verde → refactor).
- [ ] `ruff` + `mypy --strict` sin errores (backend) / `eslint` + `tsc --noEmit` sin errores (frontend).
- [ ] Sin imports que crucen fronteras de módulo hexagonal (ADR-001).
- [ ] CI del PR en verde; cobertura del módulo tocado ≥ 80%.
- [ ] Si la implementación se desvía de la spec o el plan, **se actualiza primero el documento SDD** y luego el código.

---

## 4.2. Hitos (Milestones)

| Hito | Nombre | Objetivo verificable al cierre | Gate BDD |
|---|---|---|---|
| **M1** | Fundaciones e Infraestructura | `docker compose up` levanta web+api+mysql con esquema completo y seeds; CI en verde sobre un PR de prueba | — (gate técnico) |
| **M2** | Autenticación y Shell SaaS | Login/refresh/logout funcionales E2E con rotación y detección de reutilización; layout multi-módulo navegable | — (tests ADR-003) |
| **M3** | Ingesta y Asistente de Mapeo | Los 3 ficheros reales se cargan, previsualizan y mapean con gate bloqueante | **CA-01, CA-04 verdes** |
| **M4** | Motor de Conciliación | Pipeline completo asíncrono sobre los ficheros reales con resultados persistidos | **CA-02, CA-03 verdes** |
| **M5** | Informe, Exportación e Histórico | 3 vistas + export xlsx/csv + histórico de runs | **CA-05 verde** |
| **M6** | Endurecimiento y Producción | Desplegado en EC2 con seguridad, observabilidad y rendimiento validados; UAT con el cliente | RNF-01/02/04 medidos |

Dependencias entre hitos: M1 → M2 → M3 → M4 → M5 → M6 (estrictamente secuenciales; M2 puede solaparse con el final de M1 solo en frontend).

---

## 4.3. Backlog de Tareas

### M1 — Fundaciones e Infraestructura

| ID | Estado | Tarea | Traza a | Dep. | Est. | DoD específico (además del global) |
|---|---|---|---|---|---|---|
| T-1.1 | ✅ | Monorepo `backend/` + `frontend/` con tooling completo: ruff, mypy --strict, pytest, pytest-bdd; eslint, tsc, vitest; lockfiles; pre-commit | ADR-001 | — | M | `pytest` y `vitest` corren (0 tests) sin error; lint/type-check en verde sobre esqueleto vacío |
| T-1.2 | ✅ | Fixtures canónicos: anonimizar los 3 ficheros reales y colocarlos en `tests/fixtures/` con un README de su estructura (incluye casos `03763BAR`, `K2.65`, fila ejemplo `ABC123`, bloque por-SKU en fila 572, NBSP) | spec 2.2 | T-1.1 | S | Test trivial que abre los 3 fixtures y verifica conteos de filas conocidos (1232 / 4156 / 8173) |
| T-1.3 | ✅ | Esqueleto FastAPI hexagonal: paquetes `auth`, `ingestion`, `mapping`, `reconciliation`, `reporting`, `platform`; endpoint `/api/v1/health`; settings 12-factor | ADR-001, plan 3.7 | T-1.1 | M | Test de integración: `GET /health` → 200 `{status, db}`; lint de arquitectura (import-linter) configurado y en verde |
| T-1.4 | ✅ | Dockerfiles multi-stage (api y web según plan 3.8.1) + `docker-compose.dev.yml` con MySQL 8 (`utf8mb4`, healthcheck) | plan 3.8.1/3.8.2, RNF-06 | T-1.3 | M | `docker compose up` deja `GET /health` → 200 con `db: ok`; imagen api corre como non-root |
| T-1.5 | ✅ | Alembic inicializado + migración 1: `users`, `refresh_tokens` (tipos exactos del plan 3.6) | plan 3.6, ADR-003 | T-1.4 | S | Test de migración up/down contra MySQL efímero; collations verificadas en test (`utf8mb4`) |
| T-1.6 | ✅ | Migración 2: `reconciliation_runs`, `source_files`, `column_mappings` con uniques (`run_id+role`, `source_file_id+logical_field`) | plan 3.6, RF-10 | T-1.5 | S | Test: insertar duplicado de unique falla; enums correctos |
| T-1.7 | ✅ | Migración 3: `error_families` + `error_codes` con **seeds** (7 familias, 53 códigos mapeados) + `run_items`, `item_errors`, `duplicate_findings` (índice `(run_id, sync_status, feed_stock DESC)`, `utf8mb4_bin` en claves de cruce) | spec 2.8, plan 3.6, RF-14 | T-1.6 | M | Test: seed presente tras migrar (7 familias, 53 códigos, ninguno `SIN_CLASIFICAR`); `EXPLAIN` del query de Vista 3 usa el índice compuesto |
| T-1.8 | ⏳ | CI GitHub Actions (on: pull_request): lint + type-check + tests + cobertura ≥ 80% + build de imágenes | plan 3.8.3 | T-1.4 | M | PR de prueba muestra los checks en verde; un type-error intencional rompe el pipeline |
> **⚠️ DIFERIDO:** El pipeline CI/CD de GitHub Actions se pospone temporalmente por decisión estratégica (core funcional primero). Se retoma antes del Hito M6. Los checks de lint y tests se ejecutan localmente hasta entonces. |
| T-1.9 | ✅ | Esqueleto React: Vite + router + **layout shell multi-módulo** (menú lateral preparado para módulos futuros) servido por nginx del contenedor `web` | intent 1.3, ADR-001 | T-1.4 | M | `docker compose up` sirve el shell en `:80`; test de render del layout en vitest |

### M2 — Autenticación y Shell SaaS (ADR-003)

> **⚠️ HITO DIFERIDO:** Por decisión estratégica para alcanzar un core funcional (M3–M5) de forma rápida, M2 queda pospuesto al final del proyecto, antes de M6. Durante M3–M5 se usa un bypass de autenticación simulado (ver nota en M3). Se retoma y completa en su totalidad previo al endurecimiento de producción.

| ID | Estado | Tarea | Traza a | Dep. | Est. | DoD específico |
|---|---|---|---|---|---|---|
| T-2.1 | ⏳ | Dominio usuario: hashing **Argon2id** (parámetros calibrados, fronteras `bytes/str` estrictas) + repositorio + comando seed de usuario admin | RNF-04, plan 3.9 | M1 | S | Tests: hash/verify round-trip; verify en tiempo constante (misma rama de código para fallo); mypy estricto sin `Any` en el módulo crypto |
| T-2.2 | ⏳ | Emisión y verificación de **Access JWT RS256**: par de claves por settings, claims (`sub`, `role`, `jti`, `iss`, `aud`, `exp` 15 min), dependencia FastAPI `require_role` | ADR-003, RF-11 | T-2.1 | M | Tests: token expirado → 401; firma inválida → 401; claim `role` aplica RBAC; clave privada nunca en respuesta ni logs |
| T-2.3 | ⏳ | `POST /auth/login`: credenciales → access + **cookie refresh** (`HttpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`), refresh opaco 256-bit persistido como SHA-256 con `family_id` | ADR-003, plan 3.7 | T-2.2 | M | Test de integración: login feliz; 401 genérico (mismo mensaje y timing usuario inexistente vs contraseña errónea); cookie con todos los atributos |
| T-2.4 | ⏳ | `POST /auth/refresh` con **rotación** + **detección de reutilización** (refresh ya rotado ⇒ revocar familia completa) y `POST /auth/logout` | ADR-003, OBJ-05 | T-2.3 | M | Tests: rotación emite par nuevo y marca `replaced_by`; reutilización del viejo → 401 y TODA la familia revocada; logout revoca familia |
| T-2.5 | ⏳ | Frontend auth: pantalla de login + almacenamiento del access en memoria + **interceptor de renovación transparente** (401 por expiración → refresh → reintento, sin interacción) + guardas de ruta | OBJ-05, RF-11 | T-2.4, T-1.9 | M | Test E2E (Playwright): sesión sigue viva tras expirar el access sin que el usuario perciba nada; logout limpia estado |

### M3 — Ingesta y Asistente de Mapeo Dinámico (gate: CA-01 y CA-04 verdes)

> **🔧 BYPASS DE AUTH ACTIVO:** Dado que M2 está diferido, todos los endpoints de M3 (y M4/M5) usan la dependencia FastAPI `get_current_user` que devuelve un usuario `admin` dummy quemado en código. Un usuario equivalente se inserta en la BD mediante script de seed (`scripts/seed_dummy_user.py`) para satisfacer las FK de `reconciliation_runs` y `source_files`. Este bypass se reemplaza por la implementación real de M2 antes de M6.

| ID | Estado | Tarea | Traza a | Dep. | Est. | DoD específico |
|---|---|---|---|---|---|---|
| T-3.1 | ✅ | **Normalización de SKU** RN-01..RN-06 como función pura + manejo de inválidos (`#N/A`…) | spec 2.5, RF-04 | M1 | S | Tests de tabla: `" twa85xl\u00a0"`→`TWA85XL`, `03763BAR` intacto, `K2.65` intacto como string, `#N/A` → inválido contabilizado |
| T-3.2 | ✅ | Puerto `SourceParser` + **parser CSV/TXT**: cascada de encoding (UTF-8→cp1252→latin-1), sniffing de delimitador, `dtype=str` universal | ADR-004, RF-01, RNF-03 | T-3.1 | M | Test con fixture fullstock real: 4.156 filas, `03763BAR` byte a byte; test con CSV cp1252 sintético |
| T-3.3 | ✅ | **Parser Excel** (`.xlsx`/`.xlsm`) en modo solo-lectura: listado de hojas, lectura como texto, macros jamás evaluadas | ADR-004, RF-02, EB-06 | T-3.2 | M | Test con fixture Libro1: columna D `(sin nombre)` con `#N/A`; test con fixture `.xlsm`: 8 hojas listadas |
| T-3.4 | ✅ | **Localizador de bloques por título** ("Errores y advertencias por SKU") + doble cabecera de `Plantilla` + descarte de fila ejemplo de Amazon | EB-02/03/04, ADR-004 | T-3.3 | M | Tests con fixture reporte: bloque hallado en fila 572 con SKU en última columna; fila `ABC123` descartada y contada en `discarded_rows`; sin título → error pedible al usuario (fallback EB-03) |
| T-3.5 | ✅ | **Heurística de sugerencia de columnas** (nombres candidatos + perfil de valores: unicidad, patrón) con `confidence` y `reason` explicables | OBJ-03, plan 3.7 | T-3.4 | M | Tests: sugiere `sku`/`stock` correctos en los 3 fixtures; nunca devuelve confianza sin `reason`; la heurística NO confirma nada por sí sola |
| T-3.6 | ✅ | Endpoints `POST /runs`, `POST /runs/{id}/files` (multipart + role, SHA-256, staging en volumen, metadatos detectados) | RF-01, plan 3.7, RNF-05 | T-3.3, M2 | M | Tests de integración: subir los 3 fixtures crea `source_files` con sha256 y unique `(run_id, role)`; >50 MB → 413 |
| T-3.7 | ✅ | Endpoint `GET .../preview` con el **contrato exacto** del plan 3.7 (hojas, bloque, cabeceras, muestra, sugerencias, warnings) | RF-03, plan 3.7 | T-3.5, T-3.6 | M | Test de contrato contra los 3 fixtures: respuesta valida contra JSON Schema del plan; lo mostrado proviene del mismo parser (sin doble implementación) |
| T-3.8 | ✅ | Endpoint `PUT .../mapping` + **validación en muestra** (stock numérico, unicidad razonable de SKU) + persistencia `column_mappings` con `confirmed_by` | RF-03, OBJ-03 | T-3.7 | M | **BDD CA-04 verde** (columna no numérica → warnings → degradación explícita); mapeo sin confirmar → `POST /process` responde 409 |
| T-3.9 | ✅ | Frontend: **wizard de mapeo pasos 1–4** (carga triple, selección de hoja, mapeo con previsualización y sugerencias marcadas, resumen) con gate bloqueante del botón Procesar | spec 2.9, RNF-08 | T-3.7, T-2.5 | L | Test E2E: flujo completo con los 3 fixtures; botón Procesar deshabilitado hasta mapeo completo (RNF-08) |
| T-3.10 | ✅ | **Gate del hito:** suite BDD CA-01 completa (3 escenarios) implementada con pytest-bdd sobre la API real | CA-01 | T-3.8 | S | **CA-01 y CA-04 100% verdes en CI**; los Gherkin del spec se ejecutan literalmente, sin reescritura |

### M4 — Motor de Conciliación (gate: CA-02 y CA-03 verdes)

| ID | Tarea | Traza a | Dep. | Est. | DoD específico |
|---|---|---|---|---|---|
| T-4.1 | Puerto **`TaskRunner`** + adaptador BackgroundTasks/ThreadPool: semáforo (máx. 2), estado de fases en MySQL, recuperación al arranque (`processing` → `failed: restart_during_processing`) | ADR-002, RF-06 | M3 | M | Tests: el event loop responde `/health` durante un job pesado simulado; 3er job concurrente espera; reinicio simulado marca la run como `failed` con causa |
| T-4.2 | Etapa **Deduplicación** según política spec 2.6: idénticas→colapso, Libro1→primera, feed→`MAX(stock)`+`stock_conflict`, errores 1:N exentos; persistencia en `duplicate_findings` | spec 2.6, RF-05, OBJ-08 | T-4.1 | M | **BDD CA-03 verde** (4 escenarios, incluido "nunca se suma" y "1:N no es duplicado") |
| T-4.3 | Etapa **Cruce de 3 vías**: outer-join sobre `sku_norm`, asignación de `sync_status` (5 estados spec 2.7), flags `in_occ/in_feed/in_amazon_report`, stocks con signo | spec 2.7, RF-06, OBJ-07 | T-4.2 | M | **BDD CA-02 verde** (escenario parametrizado de clasificación + cruce insensible a suciedad NBSP/case); cruce de los fixtures reproduce los números medidos: 524 enviados, 708 `NOT_SENT`, 62 `DESYNC_FEED_ONLY` |
| T-4.4 | Etapa **Errores y familias**: join 1:N de errores por SKU, clasificación por `error_codes.family_code`, **alta automática de códigos desconocidos en `SIN_CLASIFICAR`** con `first_seen_at` | spec 2.8, RF-07, RF-14, EB-10 | T-4.3 | M | Tests: `S01098S3MRN` conserva 11 errores; código `99999` inyectado → alta en catálogo + familia `SIN_CLASIFICAR`; NBSP normalizado en mensajes |
| T-4.5 | Etapa **Persistencia por lotes** transaccional (`run_items` + `item_errors`) + `summary_metrics` JSON + transición `completed` | RF-10, plan 3.4 | T-4.4 | M | Test: fallo a mitad de escritura → rollback completo, run `failed`, sin filas huérfanas; run completa de fixtures persiste 4.094+ items en < 30 s (pre-validación RNF-02) |
| T-4.6 | Endpoints `POST /runs/{id}/process` (202 / 409 por gate) y `GET /runs/{id}/status` (fase, progreso, conteos) + frontend paso 5 (pantalla de progreso con polling) | RF-06, plan 3.5/3.7 | T-4.5, T-3.9 | M | Test de integración del flujo 202→polling→completed; E2E: barra de progreso refleja las fases del pipeline 3.4 |

### M5 — Informe, Exportación e Histórico (gate: CA-05 verde)

| ID | Tarea | Traza a | Dep. | Est. | DoD específico |
|---|---|---|---|---|---|
| T-5.1 | Endpoint **Vista 1** `GET .../report/families` (agregado por familia con drill-down a códigos y de ahí a SKUs) | RF-08, RF-14 | M4 | M | Test contra run de fixtures: familia `AUTORIZACION_MARCA` agrega 18299+18749+…; familia vacía no aparece; `SIN_CLASIFICAR` visible con aviso si tiene contenido |
| T-5.2 | Endpoints **Vista 2** `sku-detail` (filtros family/code/sync_status, paginación) y **Vista 3** `catalog-health` (desync orden `stock DESC`, not_sent, duplicates) | RF-08, OBJ-07/08 | T-5.1 | M | Tests: orden por stock desc verificado; paginación estable; filtros combinables |
| T-5.3 | **Exportación** `GET .../export?format=xlsx|csv`: libro con 3 pestañas replicando las vistas | RF-09 | T-5.2 | M | **BDD CA-05 verde completo** (incluido el escenario de exportación); xlsx de fixtures abre con 3 pestañas y conteos correctos |
| T-5.4 | Frontend: **dashboard de informe en 3 tabs** con drill-down familia→código→SKUs y botones de export | RF-08, spec 2.1 | T-5.3 | L | E2E: flujo completo upload→mapeo→proceso→informe→descarga sobre fixtures reales |
| T-5.5 | **Histórico**: `GET /runs` paginado + reapertura de informe de runs pasadas + **mapeo recordado** por huella de cabeceras ofrecido como predeterminado | RF-12, RF-13 | T-5.4 | M | Tests: segunda run con mismos ficheros pre-rellena el mapeo (marcado como sugerencia, sigue exigiendo confirmación — OBJ-03); informe de run antigua accesible |
| T-5.6 | **Admin de taxonomía**: `GET /error-families`, `PATCH /error-codes/{code}` (reasignar familia, solo `admin`) + UI mínima | RF-14, EB-10 | T-5.5 | S | Tests: `operator` → 403; reasignación se refleja en la Vista 1 de la siguiente consulta sin redespliegue |

### M6 — Endurecimiento y Producción

| ID | Tarea | Traza a | Dep. | Est. | DoD específico |
|---|---|---|---|---|---|
| T-6.1 | Seguridad perimetral: nginx con TLS/HSTS/CSP, CORS restringido, rate limiting en `/auth/*`, límite de upload 50 MB en nginx y FastAPI | plan 3.9, RNF-04 | M5 | M | Tests: rate limit dispara 429; headers presentes en E2E; subida de 51 MB → 413 en ambas capas |
| T-6.2 | Observabilidad: logs JSON con `run_id`/`request_id` en todo el pipeline + métricas Prometheus (duración por fase, acierto de heurística `was_suggested`, refresh reuse detectado) | RNF-07, plan 3.10 | T-6.1 | M | Test: toda línea de log de una conciliación contiene `run_id`; endpoint de métricas expone las series definidas |
| T-6.3 | **Validación de rendimiento**: dataset sintético de 100k filas; medición RNF-01 (preview < 3 s) y RNF-02 (conciliación p95 < 30 s) en hardware equivalente a producción | RNF-01/02, OBJ-01/02 | T-6.2 | M | Informe de medición versionado junto al código; si falla, se activa el análisis de los disparadores del ADR-002 antes de continuar |
| T-6.4 | CD a producción: job de deploy (SSH a EC2, `compose pull && up -d`, migraciones Alembic, smoke test, rollback automático) + Trivy/gitleaks como gates + backups diarios `mysqldump` → S3 | plan 3.8.3, RT-02 | T-6.3 | L | Deploy real en EC2 verde con smoke test; rollback probado con una imagen rota a propósito; backup restaurable verificado una vez |
| T-6.5 | **UAT con el cliente**: ejecución guiada con sus 3 ficheros reales, validación del naming de familias (cierre fino de pregunta #2) y del informe exportado | spec 2.13, OBJ-06 | T-6.4 | M | Acta de UAT; ajustes de naming aplicados vía datos (no código); aceptación formal del MVP |

---

## 4.4. Matriz de Trazabilidad (Spec → Plan → Tasks)

| Requisito (Spec) | Criterio BDD | Componente (Plan) | Tareas | Cobertura |
|---|---|---|---|---|
| RF-01 (carga 3 ficheros) | CA-01 | `ingestion` / contratos 3.7 | T-3.2, T-3.3, T-3.6 | ✅ M3 |
| RF-02 (multi-hoja) | CA-01 | `ingestion` (ADR-004) | T-3.3, T-3.4 | ✅ M3 |
| RF-03 (mapeo confirmado bloqueante) | CA-01, CA-04 | `mapping` / preview 3.7 | T-3.5, T-3.7, T-3.8, T-3.9 | ✅ M3 |
| RF-04 (normalización SKU) | CA-02, CA-03 | RN-01..06 / `ingestion` | T-3.1 | ✅ M3 |
| RF-05 (duplicados) | CA-03 | `reconciliation` / política 2.6 | T-4.2 | ⏳ |
| RF-06 (conciliación asíncrona) | CA-02 | `TaskRunner` (ADR-002) | T-4.1, T-4.3, T-4.6 | ⏳ |
| RF-07 (errores 1:N) | CA-02 | `reconciliation` / `item_errors` | T-4.4 | ⏳ |
| RF-08 (informe 3 vistas) | CA-02, CA-05 | `reporting` / contratos 3.7 | T-5.1, T-5.2, T-5.4 | ⏳ |
| RF-09 (exportación) | CA-05 | `reporting` | T-5.3 | ⏳ |
| RF-10 (persistencia íntegra) | — | modelo físico 3.6 | T-1.6, T-1.7, T-4.5 | ⏳ |
| RF-11 (JWT) | — | ADR-003 | T-2.1..T-2.5 | ⏳ |
| RF-12 (mapeo recordado) | — | `mapping` | T-5.5 | ⏳ |
| RF-13 (histórico) | — | `reporting` | T-5.5 | ⏳ |
| RF-14 (familias de error) | CA-05 | taxonomía 2.8 / seeds 3.6 | T-1.7, T-4.4, T-5.1, T-5.6 | ⏳ |
| RNF-01/02 (latencias) | — | presupuesto 3.11 | T-4.5, T-6.3 | ⏳ |
| RNF-03 (SKU como texto) | CA-01 | ADR-004 | T-3.1, T-3.2 | ✅ M3 |
| RNF-04 (seguridad OWASP) | — | ADR-003 / 3.9 | T-2.1..T-2.4, T-6.1 | ⏳ |
| RNF-05 (trazabilidad sha256) | — | `source_files` 3.6 | T-3.6 | ⏳ |
| RNF-06 (contenedores) | — | 3.8 | T-1.4, T-6.4 | ⏳ |
| RNF-07 (observabilidad) | — | 3.10 | T-6.2 | ⏳ |
| RNF-08 (gate bloqueante UI) | CA-01 | wizard 2.9 | T-3.8, T-3.9 | ✅ M3 |

> Verificación de completitud: los 14 RF y los 8 RNF tienen tareas asignadas; ninguna tarea carece de traza. Los 5 CA actúan como gates de hito (M3: CA-01/04 · M4: CA-02/03 · M5: CA-05).

---

## 4.5. Dependencias Externas y Bloqueos

| ID | Dependencia | Afecta a | Responsable | Estado |
|---|---|---|---|---|
| DEP-01 | Instancia AWS EC2 provisionada (Docker, Security Group 443 + SSH restringido) y bucket S3 de backups | T-6.4 | DevOps / Cliente | ⏳ |
| DEP-02 | Secrets de producción: par de claves JWT, credenciales MySQL, clave SSH de deploy en GitHub Secrets | T-6.4 | Tech Lead | ⏳ |
| DEP-03 | Autorización del cliente para usar los ficheros reales anonimizados como fixtures de test | T-1.2 | Cliente | ⏳ |
| DEP-04 | Disponibilidad del cliente para la sesión de UAT | T-6.5 | Cliente | ⏳ |

---

## 4.6. Plan de Verificación

| Tipo de prueba | Alcance | Criterios cubiertos | En CI |
|---|---|---|---|
| Unitarias (TDD) | Normalización, heurística, crypto, parsers | RN-01..06, ADR-003/004 | ☑ cada PR |
| Integración | Endpoints contra MySQL efímero, migraciones up/down | RF-01..14, modelo 3.6 | ☑ cada PR |
| **BDD (pytest-bdd)** | **Gherkin CA-01..CA-05 literales del spec** | Gates de M3/M4/M5 | ☑ cada PR |
| E2E (Playwright) | Wizard completo, refresh transparente, dashboard | RNF-08, OBJ-05 | ☑ cada PR (suite reducida) / completa en main |
| Regresión de datos | Fixtures reales: conteos 524/708/62, `03763BAR`, `K2.65`, 11 errores de `S01098S3MRN` | RNF-03, spec 2.2.4 | ☑ cada PR |
| Rendimiento | Dataset 100k filas | RNF-01/02 | ☐ manual en T-6.3 (y antes de cada release mayor) |
| Seguridad | Trivy, gitleaks, rate limiting, headers | RNF-04 | ☑ en main |

---

## ✅ Criterio de salida de fase (Gate)

- [x] Toda tarea traza a requisito, criterio BDD o decisión del plan; orden de ejecución estricto y dependencias explícitas.
- [x] Infraestructura completa (Docker, CI/CD, base de datos con seeds) concentrada en M1, antes de cualquier funcionalidad.
- [x] Cada tarea tiene DoD propio orientado a TDD; los Gherkin del spec son gates de hito ejecutados literalmente.
- [x] Matriz de trazabilidad sin requisitos huérfanos ni tareas sin origen.
- [x] Dependencias externas identificadas con responsable.
- [x] **Aprobación del solicitante** (2026-06-12). El ciclo de planificación SDD queda cerrado; la implementación puede comenzar por T-1.1.

> **Fin del ciclo de especificación.** A partir de aquí comienza la implementación: cada sesión de programación toma la siguiente tarea pendiente en orden, empieza por su test y termina con su DoD completo. Cualquier desviación se refleja primero en estos documentos — la spec sigue siendo la fuente de verdad.
