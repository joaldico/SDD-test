# Fixtures canónicos anonimizados

Estos fixtures fueron generados a partir de los 3 ficheros reales entregados por el cliente y materializan la estructura aprobada en `.specify/2_spec.md`. Se usan como base de regresión para ingesta, mapeo y conciliación.

No contienen datos comerciales directos en campos de negocio: nombres de producto, proveedores, EANs, mensajes descriptivos, campos afectados y SKUs no críticos fueron sustituidos por valores anonimizados deterministas. Los SKUs necesarios para regresión de casos borde se conservan literalmente.

## Archivos

| Archivo | Rol | Formato | Conteo verificable |
|---|---|---|---|
| `occ_top_sales_anonymized.xlsx` | `occ_top` | XLSX, hoja `Hoja1` | 1.232 filas de datos |
| `wavemarket_fullstock_anonymized.csv` | `wm_feed` | CSV UTF-8, delimitador `,` | 4.156 filas de datos |
| `amazon_processing_summary_anonymized.xlsm` | `amazon_report` | XLSM legible como datos, 8 hojas | 8.173 filas en el bloque por SKU |

## Casos borde preservados

- SKUs con ceros a la izquierda en el feed: `03763BAR`, `03763BBS`, `03763BNR`, `03763BRS`.
- SKU con apariencia decimal preservado como texto: `K2.65`.
- Columna sin cabecera en `occ_top_sales_anonymized.xlsx`, con valores `#N/A`.
- Reporte Amazon con 8 hojas y bloque `Errores y advertencias por SKU` localizado por título en la fila 570.
- Cabecera del bloque por SKU en la fila 571 y datos desde la fila 572.
- Hoja `Plantilla` con doble cabecera en filas 4 y 5.
- Fila de ejemplo Amazon `ABC123` en la fila 6 de `Plantilla`.
- Mensajes de error con NBSP (`U+00A0`) en `Resumen de procesamiento`.
- SKU `S01098S3MRN` con 11 errores asociados para pruebas posteriores de cardinalidad 1:N.
- El paquete `.xlsm` real no contiene `xl/vbaProject.bin`; el fixture conserva ese estado real en vez de introducir macros artificiales.

## Regla de uso

Los tests deben abrir estos archivos con los mismos parsers que usará la aplicación. Si un fixture cambia, debe mantenerse el conteo canónico esperado por T-1.2: `1232 / 4156 / 8173`, la lista de 8 hojas del reporte, la doble cabecera de `Plantilla` y el bloque por-SKU desde la fila 572.
