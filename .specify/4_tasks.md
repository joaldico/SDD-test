# 4. Desglose de Tareas (Tasks)

> **Fase SDD:** `4/4 — Task Breakdown`
> **Estado:** `🟡 Borrador`
> **Versión:** `0.1.0`
> **Última actualización:** _AAAA-MM-DD_
> **Trazabilidad:** ejecuta [`3_plan.md`](./3_plan.md), verifica contra [`2_spec.md`](./2_spec.md)

---

## 4.1. Convenciones

- **Formato de ID:** `T-<hito>.<secuencia>` (ej: `T-1.2`).
- **Toda tarea debe trazar** a un requisito (`RF-xx` / `RNF-xx`) o componente del plan (`ADR-xxx`, servicio).
- **Definition of Done (DoD) global:**
  - [ ] Código con tipado estricto y lint en verde.
  - [ ] Tests que cubren los criterios BDD asociados (`CA-xx`).
  - [ ] Imagen de contenedor construida y publicada por el pipeline.
  - [ ] Documentación/spec actualizada si hubo desviación (la spec es la fuente de verdad).
  - [ ] Revisión de código aprobada.

---

## 4.2. Hitos (Milestones)

| Hito | Nombre | Objetivo del hito | Entregable verificable | Fecha objetivo |
|---|---|---|---|---|
| M1 | _Ej: Fundaciones_ | _Esqueleto de servicios, CI/CD, entorno local_ | _Pipeline en verde, "hello service" desplegado_ | _..._ |
| M2 | _Ej: Núcleo funcional_ | _..._ | _..._ | _..._ |
| M3 | _Ej: Endurecimiento_ | _Seguridad, observabilidad, rendimiento_ | _..._ | _..._ |

---

## 4.3. Backlog de Tareas

### M1 — _[Nombre del hito]_

| ID | Tarea | Traza a | Dependencias | Estimación | Responsable | Estado |
|---|---|---|---|---|---|---|
| T-1.1 | _..._ | RF-01 / ADR-001 | — | _S/M/L_ | _..._ | ⬜ Pendiente |
| T-1.2 | _..._ | RNF-06 | T-1.1 | _S/M/L_ | _..._ | ⬜ Pendiente |

### M2 — _[Nombre del hito]_

| ID | Tarea | Traza a | Dependencias | Estimación | Responsable | Estado |
|---|---|---|---|---|---|---|
| T-2.1 | _..._ | _..._ | _..._ | _..._ | _..._ | ⬜ Pendiente |

### M3 — _[Nombre del hito]_

| ID | Tarea | Traza a | Dependencias | Estimación | Responsable | Estado |
|---|---|---|---|---|---|---|
| T-3.1 | _..._ | _..._ | _..._ | _..._ | _..._ | ⬜ Pendiente |

> **Leyenda de estado:** ⬜ Pendiente · 🔵 En progreso · 🟢 Completada · 🔴 Bloqueada

---

## 4.4. Matriz de Trazabilidad (Spec → Plan → Tasks)

> _Garantiza que ningún requisito queda sin tarea y ninguna tarea existe sin requisito._

| Requisito | Criterio BDD | Componente (plan) | Tareas | Estado de cobertura |
|---|---|---|---|---|
| RF-01 | CA-01 | _svc-..._ | T-1.1 | ⏳ |
| RNF-01 | — | _..._ | _..._ | ⏳ |

---

## 4.5. Dependencias Externas y Bloqueos

| ID | Dependencia / Bloqueo | Afecta a | Responsable de resolver | Estado |
|---|---|---|---|---|
| DEP-01 | _Ej: acceso a clúster K8s / API key de proveedor_ | T-1.2 | _..._ | ⏳ |

---

## 4.6. Plan de Verificación

| Tipo de prueba | Alcance | Criterios cubiertos | Automatizada en CI |
|---|---|---|---|
| Unitarias | _Por servicio_ | _..._ | ☑ |
| Integración | _Contratos entre servicios_ | _..._ | ☑ |
| BDD / E2E | _Escenarios Gherkin de `2_spec.md`_ | CA-01, CA-02, ... | ☑ |
| Carga / Rendimiento | _RNF de latencia y throughput_ | RNF-01, RNF-02 | ☐ |
| Seguridad | _SAST / DAST / escaneo de imágenes_ | RNF-03 | ☑ |

---

## ✅ Criterio de salida de fase (Gate)

- [ ] Toda tarea traza a un requisito o decisión arquitectónica.
- [ ] La matriz de trazabilidad no tiene requisitos sin cobertura.
- [ ] Las dependencias externas están identificadas con responsable.
- [ ] El plan de verificación cubre todos los criterios BDD.

> **Fin del ciclo de especificación.** A partir de aquí comienza la implementación: el código debe escribirse **contra** estos documentos, y cualquier desviación debe actualizarse primero en la spec (fuente de verdad).
