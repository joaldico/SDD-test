# language: es
Característica: Asistente de Mapeo Dinámico
  Como gestor de operaciones
  Quiero confirmar qué columna contiene el SKU y el stock en cada fichero
  Para garantizar que la conciliación cruza los datos correctos

  Antecedentes:
    Dado que estoy autenticado como "operator"
    Y he cargado "Libro1.xlsx" como "Top ventas OCC"
    Y he cargado "amazon_ES_fullstock.csv" como "Feed WaveMarket"
    Y he cargado "ListingLoader-processing-summary.xlsm" como "Reporte Amazon"

  Escenario: Confirmación del mapeo sugerido de SKU y stock
    Dado que el sistema detectó el CSV como "UTF-8" con delimitador ","
    Y el sistema localizó el bloque "Errores y advertencias por SKU" del reporte
    Cuando abro el paso de mapeo del fichero "Feed WaveMarket"
    Entonces veo una previsualización con las cabeceras "sku, stock, site, condition" y 5 filas de muestra
    Y la columna "sku" aparece preseleccionada como SKU con la marca "sugerencia"
    Y la columna "stock" aparece preseleccionada como Stock con la marca "sugerencia"
    Cuando confirmo el mapeo de los 3 ficheros
    Entonces el botón "Procesar" pasa a estar habilitado
    Y el mapeo confirmado queda persistido con mi usuario y marca de tiempo

  Escenario: El procesamiento es inalcanzable sin confirmación humana
    Dado que la heurística sugirió columnas SKU en los 3 ficheros
    Pero no he confirmado el mapeo del fichero "Reporte Amazon"
    Cuando intento iniciar el procesamiento
    Entonces el sistema lo rechaza indicando "mapeo pendiente de confirmación"
    Y ningún dato de la ejecución se persiste como procesado

  Escenario: Los SKUs sobreviven intactos a la ingesta
    Dado que el feed contiene los SKUs "03763BAR" y "K2.65"
    Cuando confirmo el mapeo y finaliza el procesamiento
    Entonces el campo sku_raw almacenado para ambos es exactamente "03763BAR" y "K2.65"
    Y ningún SKU fue convertido a número ni perdió ceros a la izquierda
