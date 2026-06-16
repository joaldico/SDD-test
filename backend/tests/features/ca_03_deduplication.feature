# language: es
Característica: Detección y resolución explícita de duplicados
  Como gestor de operaciones
  Quiero que los duplicados se detecten, se resuelvan con una política conocida y se reporten
  Para que el informe nunca infle métricas en silencio

  Escenario: Filas idénticas en el feed se colapsan y se reportan
    Dado que el feed contiene 3 filas idénticas para el SKU "K570" con stock 1
    Cuando finaliza el procesamiento
    Entonces "K570" aparece una sola vez en los resultados con stock 1
    Y la Vista 3 registra el hallazgo "K570: 3 ocurrencias, resolución collapsed_identical"

  Escenario: Stock en conflicto en el feed — nunca se suma
    Dado que el feed contiene el SKU "TWA85XL" con stock 5 en una fila y stock 2 en otra
    Cuando finaliza el procesamiento
    Entonces "TWA85XL" queda con stock 5 y stock_conflict verdadero
    Y la Vista 3 muestra los valores en conflicto "5" y "2"
    Y en ningún caso el stock resultante es 7

  Escenario: Duplicado en Libro1 conserva la primera ocurrencia
    Dado que "Libro1" contiene el SKU "OCC20326" en la fila 3 con proveedor "OCC QUIMICOS"
    Y el mismo SKU en la fila 900 con proveedor "OTRO PROVEEDOR"
    Cuando finaliza el procesamiento
    Entonces los datos asociados a "OCC20326" son los de la fila 3
    Y la Vista 3 registra "OCC20326: 2 ocurrencias, resolución kept_first" con la fila descartada

  Escenario: Múltiples errores por SKU no se tratan como duplicados
    Dado que el reporte de Amazon contiene 8 filas de error distintas para "S00126941BMBI"
    Cuando finaliza el procesamiento
    Entonces "S00126941BMBI" conserva sus 8 errores asociados
    Y no figura en el reporte de duplicados
