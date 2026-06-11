# 3. Plan Técnico y Diseño de Arquitectura (Plan)

> **Fase SDD:** `3/4 — Technical Plan`
> **Estado:** `🟡 Borrador`
> **Versión:** `0.1.0`
> **Última actualización:** _AAAA-MM-DD_
> **Trazabilidad:** implementa [`2_spec.md`](./2_spec.md)

---

## 3.1. Resumen de la Solución Técnica

> _Párrafo de síntesis: estilo arquitectónico elegido (microservicios / micro-frontends), runtime, y cómo satisface los RNF críticos._

```text
[PENDIENTE DE RELLENAR]
```

---

## 3.2. Decisiones de Arquitectura (ADRs)

> _Cada decisión debe incluir justificación técnica basada en **escalabilidad**, alternativas descartadas y trade-offs._

### ADR-001 — _[Título de la decisión]_

| Campo | Contenido |
|---|---|
| **Estado** | Propuesta / Aceptada / Reemplazada |
| **Contexto** | _¿Qué problema fuerza esta decisión?_ |
| **Decisión** | _¿Qué se decidió?_ |
| **Justificación (escalabilidad)** | _¿Por qué escala mejor que las alternativas?_ |
| **Alternativas descartadas** | _Opción B (motivo), Opción C (motivo)_ |
| **Consecuencias** | _Positivas y negativas asumidas_ |

---

## 3.3. Arquitectura Lógica (Componentes y Microservicios)

> _Vista de componentes: servicios, responsabilidades y contratos entre ellos._

| Componente / Servicio | Responsabilidad única | Stack propuesto | Expone | Consume |
|---|---|---|---|---|
| _Ej: api-gateway_ | _Enrutado, authn/authz_ | _..._ | _REST/gRPC_ | _..._ |
| _Ej: svc-core_ | _..._ | _..._ | _..._ | _..._ |

### Diagrama de arquitectura de componentes

```mermaid
%% [PENDIENTE] Diagrama de componentes/microservicios
%% Sugerencia: flowchart LR con subgraphs por dominio (frontend, backend, datos, IA)
flowchart LR
    %% TODO: definir nodos y relaciones
```

---

## 3.4. Flujo de Datos

> _Cómo viaja la información entre componentes: origen, transformaciones, persistencia y salida. Si hay módulos de IA (LLM, RAG, voz), detallar latencia esperada y gestión del contexto por tramo._

```mermaid
%% [PENDIENTE] Diagrama de flujo de datos (DFD)
%% Sugerencia: flowchart TD mostrando origen → procesamiento → persistencia → consumo
flowchart TD
    %% TODO: definir flujo de datos
```

### Presupuesto de latencia (si aplica IA / tiempo real)

| Tramo | Operación | Latencia objetivo (p95) | Notas (contexto, tokens, caché) |
|---|---|---|---|
| _..._ | _..._ | _... ms_ | _..._ |

---

## 3.5. Diagramas de Secuencia (flujos críticos)

### SEQ-01 — _[Nombre del flujo crítico, ej: autenticación / inferencia RAG]_

```mermaid
%% [PENDIENTE] Diagrama de secuencia del flujo crítico SEQ-01
sequenceDiagram
    %% TODO: definir participantes y mensajes
```

### SEQ-02 — _[Nombre del flujo de error/compensación]_

```mermaid
%% [PENDIENTE] Diagrama de secuencia del flujo SEQ-02
sequenceDiagram
    %% TODO: definir participantes y mensajes
```

---

## 3.6. Modelo de Datos Físico

| Almacén | Tecnología | Datos que persiste | Estrategia de escalado |
|---|---|---|---|
| _..._ | _..._ | _..._ | _Réplicas / sharding / particionado_ |

```mermaid
%% [PENDIENTE] Diagrama entidad-relación
erDiagram
    %% TODO: definir entidades y relaciones
```

---

## 3.7. Contratos de API (visión general)

| Endpoint / Tópico | Método / Patrón | Request | Response | Auth |
|---|---|---|---|---|
| _Ej: /api/v1/..._ | _GET / POST / evento_ | _..._ | _..._ | _JWT / mTLS_ |

---

## 3.8. Arquitectura de Despliegue (Contenedores y Orquestación)

> _Toda la solución debe ser contenedorizable (Docker) y orquestable (Kubernetes)._

| Servicio | Imagen base | Réplicas (min/max) | Recursos (req/lim) | Estrategia de escalado |
|---|---|---|---|---|
| _..._ | _..._ | _..._ | _CPU/RAM_ | _HPA por CPU / colas / custom metrics_ |

```mermaid
%% [PENDIENTE] Diagrama de despliegue (clúster K8s, namespaces, ingress, servicios externos)
flowchart TB
    %% TODO: definir topología de despliegue
```

---

## 3.9. Pipeline CI/CD

| Etapa | Herramienta | Acción | Gate de calidad |
|---|---|---|---|
| Build | _..._ | _Compilación + build de imagen OCI_ | _Lint, type-check estricto_ |
| Test | _..._ | _Unit + integración + BDD (de `2_spec.md`)_ | _Cobertura ≥ X%_ |
| Seguridad | _..._ | _SAST, escaneo de imagen, secretos_ | _0 vulnerabilidades críticas_ |
| Deploy | _..._ | _Despliegue progresivo (canary/blue-green)_ | _SLOs en verde_ |

```mermaid
%% [PENDIENTE] Diagrama del pipeline CI/CD
flowchart LR
    %% TODO: definir etapas del pipeline
```

---

## 3.10. Seguridad

- **Autenticación / Autorización:** _[PENDIENTE]_
- **Cifrado en tránsito y en reposo:** _[PENDIENTE — especificar algoritmos y gestión de claves; tipado estricto en lógica de cifrado/hashing, sin conversiones de formato inseguras]_
- **Gestión de secretos:** _[PENDIENTE]_
- **Modelo de amenazas (resumen):** _[PENDIENTE]_

---

## 3.11. Observabilidad

| Pilar | Herramienta | Qué se captura |
|---|---|---|
| Logs | _..._ | _Estructurados (JSON), correlación por trace-id_ |
| Métricas | _..._ | _RED/USE + métricas de negocio_ |
| Trazas | _..._ | _Distribuidas entre microservicios_ |
| Alertas | _..._ | _Basadas en SLOs de `2_spec.md`_ |

---

## 3.12. Módulos de IA (si aplica)

> _Rellenar solo si la solución integra LLMs, RAG o interfaces de voz._

| Aspecto | Definición |
|---|---|
| **Modelo(s)** | _Local (ej: vLLM/Ollama) o nube (proveedor, versión)_ |
| **Flujo de datos** | _Entrada → preprocesado → contexto → inferencia → postprocesado_ |
| **Gestión del contexto** | _Ventana, truncado, memoria, estrategia de chunking (RAG)_ |
| **Latencia objetivo** | _p95 end-to-end y por etapa_ |
| **Privacidad de datos** | _¿Salen datos del perímetro? Anonimización/redacción_ |
| **Evaluación** | _Métricas de calidad (groundedness, exactitud) y datasets de eval_ |

---

## 3.13. Riesgos Técnicos y Deuda Asumida

| ID | Riesgo / Deuda | Impacto | Plan de mitigación |
|---|---|---|---|
| RT-01 | _..._ | _..._ | _..._ |

---

## ✅ Criterio de salida de fase (Gate)

- [ ] Todos los diagramas Mermaid están completados (componentes, datos, secuencia, despliegue, CI/CD).
- [ ] Cada ADR incluye justificación de escalabilidad y alternativas descartadas.
- [ ] Cada RNF de `2_spec.md` tiene una respuesta arquitectónica explícita en este documento.
- [ ] La estrategia de contenedorización y el pipeline CI/CD están definidos.

> **Siguiente fase:** [`4_tasks.md`](./4_tasks.md) — Desglose de tareas ejecutables.
