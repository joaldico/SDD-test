# 1. Intención del Producto (Intent)

> **Fase SDD:** `1/4 — Intent`
> **Estado:** `🟡 Borrador`
> **Versión:** `0.1.0`
> **Última actualización:** _AAAA-MM-DD_
> **Autor(es):** _Nombre / Rol_

---

## 1.1. Declaración de Intención (Elevator Pitch)

> _Describe en 2-3 frases qué se quiere construir y por qué. Esta es la fuente de verdad de más alto nivel: si algo contradice este párrafo, ese algo está mal._

```text
[PENDIENTE DE RELLENAR]
```

---

## 1.2. Problema a Resolver

| Campo | Descripción |
|---|---|
| **Problema central** | _¿Qué dolor existe hoy?_ |
| **Afectados** | _¿Quién sufre este problema? (personas, equipos, sistemas)_ |
| **Costo de no actuar** | _¿Qué pasa si no se resuelve? (técnico, económico, operativo)_ |
| **Soluciones actuales** | _¿Cómo se mitiga hoy y por qué es insuficiente?_ |

---

## 1.3. Visión de la Solución

> _Descripción de alto nivel de la solución propuesta. **Sin detalles de implementación** (eso pertenece a `3_plan.md`)._

- **Qué hará:** _[PENDIENTE]_
- **Qué NO hará (anti-objetivos):** _[PENDIENTE]_
- **Diferenciador clave:** _[PENDIENTE]_

---

## 1.4. Usuarios y Stakeholders

| Actor | Tipo | Necesidad principal | Nivel de impacto |
|---|---|---|---|
| _Ej: Usuario final_ | Primario | _..._ | Alto |
| _Ej: Equipo DevOps_ | Secundario | _..._ | Medio |
| _Ej: Sistema externo X_ | Sistema | _..._ | Bajo |

---

## 1.5. Objetivos de Negocio y Métricas de Éxito

> _Cada objetivo debe ser medible. Si no se puede medir, no es un objetivo: es un deseo._

| ID | Objetivo | Métrica (KPI) | Valor objetivo | Plazo |
|---|---|---|---|---|
| OBJ-01 | _..._ | _..._ | _..._ | _..._ |
| OBJ-02 | _..._ | _..._ | _..._ | _..._ |

---

## 1.6. Restricciones Globales

- **Técnicas:** _Ej: debe ser contenedorizable (Docker/K8s), compatible con el pipeline CI/CD existente._
- **Regulatorias / Cumplimiento:** _Ej: GDPR, cifrado en reposo y en tránsito._
- **Presupuesto / Tiempo:** _[PENDIENTE]_
- **Organizacionales:** _[PENDIENTE]_

---

## 1.7. Supuestos y Riesgos Iniciales

| ID | Tipo | Descripción | Probabilidad | Impacto | Mitigación inicial |
|---|---|---|---|---|---|
| SUP-01 | Supuesto | _..._ | — | — | _Validar con..._ |
| RSK-01 | Riesgo | _..._ | Alta/Media/Baja | Alto/Medio/Bajo | _..._ |

---

## 1.8. Glosario del Dominio

| Término | Definición |
|---|---|
| _..._ | _..._ |

---

## ✅ Criterio de salida de fase (Gate)

- [ ] La declaración de intención cabe en 3 frases y es inequívoca.
- [ ] Todos los stakeholders están identificados y han validado el documento.
- [ ] Cada objetivo tiene una métrica medible asociada.
- [ ] Los anti-objetivos están explícitos.

> **Siguiente fase:** [`2_spec.md`](./2_spec.md) — Especificación funcional y criterios de aceptación BDD.
