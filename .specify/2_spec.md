# 2. Especificación Funcional (Spec)

> **Fase SDD:** `2/4 — Specification`
> **Estado:** `🟡 Borrador`
> **Versión:** `0.1.0`
> **Última actualización:** _AAAA-MM-DD_
> **Trazabilidad:** deriva de [`1_intent.md`](./1_intent.md)

---

## 2.1. Alcance (Scope)

### Dentro del alcance (In-Scope)

- _[PENDIENTE]_

### Fuera del alcance (Out-of-Scope)

> _Tan importante como lo que entra. Lo que no esté aquí ni en In-Scope se considera fuera por defecto._

- _[PENDIENTE]_

---

## 2.2. Requisitos Funcionales (RF)

> _Cada requisito debe ser atómico, verificable y trazable a un objetivo de `1_intent.md`._

| ID | Requisito | Prioridad (MoSCoW) | Objetivo asociado | Criterio BDD |
|---|---|---|---|---|
| RF-01 | _El sistema debe..._ | Must | OBJ-01 | CA-01 |
| RF-02 | _El sistema debe..._ | Should | OBJ-02 | CA-02 |

---

## 2.3. Requisitos No Funcionales (RNF)

| ID | Categoría | Requisito | Métrica verificable |
|---|---|---|---|
| RNF-01 | Rendimiento | _Ej: latencia p95 < X ms_ | _..._ |
| RNF-02 | Escalabilidad | _Ej: soportar N req/s con escalado horizontal_ | _..._ |
| RNF-03 | Seguridad | _Ej: cifrado TLS 1.3, hashing Argon2id con tipado estricto_ | _..._ |
| RNF-04 | Disponibilidad | _Ej: SLO 99.9%_ | _..._ |
| RNF-05 | Observabilidad | _Ej: trazas distribuidas, métricas y logs estructurados_ | _..._ |
| RNF-06 | Portabilidad | _Ej: despliegue 100% contenedorizado (OCI)_ | _..._ |

---

## 2.4. Historias de Usuario

> _Formato: **Como** [actor], **quiero** [acción], **para** [beneficio]._

### HU-01 — _[Título de la historia]_

- **Como** _[actor]_
- **Quiero** _[acción]_
- **Para** _[beneficio]_
- **Requisitos asociados:** RF-01

---

## 2.5. Criterios de Aceptación (BDD — Gherkin)

> _Cada criterio es ejecutable conceptualmente: si no se puede transformar en un test automatizado, debe reescribirse._

### CA-01 — _[Nombre del escenario]_ `(cubre RF-01)`

```gherkin
Característica: [Nombre de la funcionalidad]

  Antecedentes:
    Dado que [estado inicial común a los escenarios]

  Escenario: [Caso feliz]
    Dado que [contexto / precondición]
    Cuando [acción del actor]
    Entonces [resultado observable y verificable]
    Y [postcondición adicional]

  Escenario: [Caso de error]
    Dado que [contexto / precondición]
    Cuando [acción inválida o fallo]
    Entonces [comportamiento de error esperado]
    Y [el sistema mantiene un estado consistente]

  Esquema del escenario: [Caso parametrizado]
    Dado que [contexto con <parametro>]
    Cuando [acción con <entrada>]
    Entonces [resultado <esperado>]

    Ejemplos:
      | parametro | entrada | esperado |
      | ...       | ...     | ...      |
```

### CA-02 — _[Nombre del escenario]_ `(cubre RF-02)`

```gherkin
Característica: [PENDIENTE]

  Escenario: [PENDIENTE]
    Dado que [PENDIENTE]
    Cuando [PENDIENTE]
    Entonces [PENDIENTE]
```

---

## 2.6. Reglas de Negocio

| ID | Regla | Fuente / Justificación |
|---|---|---|
| RN-01 | _..._ | _..._ |

---

## 2.7. Modelo de Datos Conceptual (entidades del dominio)

> _Solo entidades y relaciones a nivel de dominio. El modelo físico pertenece a `3_plan.md`._

| Entidad | Descripción | Atributos clave | Relaciones |
|---|---|---|---|
| _..._ | _..._ | _..._ | _..._ |

---

## 2.8. Casos Borde y Manejo de Errores

| ID | Escenario borde | Comportamiento esperado |
|---|---|---|
| EB-01 | _Ej: entrada vacía / payload malformado_ | _..._ |
| EB-02 | _Ej: dependencia externa caída_ | _..._ |

---

## 2.9. Preguntas Abiertas

| # | Pregunta | Responsable | Fecha límite | Resolución |
|---|---|---|---|---|
| 1 | _..._ | _..._ | _..._ | ⏳ Pendiente |

---

## ✅ Criterio de salida de fase (Gate)

- [ ] Todo RF tiene al menos un criterio BDD asociado (trazabilidad RF → CA).
- [ ] Todos los RNF tienen métricas verificables.
- [ ] No quedan preguntas abiertas bloqueantes.
- [ ] El Out-of-Scope ha sido validado por los stakeholders.

> **Siguiente fase:** [`3_plan.md`](./3_plan.md) — Diseño técnico y arquitectura.
