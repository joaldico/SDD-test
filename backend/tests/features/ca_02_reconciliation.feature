# language: es
Característica: Conciliación de 3 vías con detección de desincronización
  Como gestor de operaciones
  Quiero ver qué SKUs están desincronizados entre WaveMarket y Amazon, priorizados por stock
  Para gestionar primero la pérdida de venta activa

  Antecedentes:
    Dado que existe una ejecución con mapeo confirmado de los 3 ficheros

  Escenario: SKU enviado con errores múltiples
    Dado que el SKU "S01098S3MRN" está en el feed con stock 4
    Y el reporte de Amazon contiene 11 filas de error para "S01098S3MRN"
    Cuando finaliza la conciliación
    Entonces "S01098S3MRN" tiene sync_status "SENT_WITH_ERROR"
    Y tiene exactamente 11 errores asociados con código, categoría, mensaje y campo afectado
    Y aparece en la Vista 2 con una fila por error

  Esquema del escenario: Clasificación bidireccional de sincronización
    Dado que el SKU "<sku>" está <en_occ> en OCC, <en_feed> en el feed y <en_amazon> en el reporte
    Cuando finaliza la conciliación
    Entonces el SKU "<sku>" recibe sync_status "<estado>"

    Ejemplos:
      | sku      | en_occ   | en_feed  | en_amazon | estado             |
      | AAA111   | ausente  | presente | ausente   | DESYNC_FEED_ONLY   |
      | BBB222   | ausente  | ausente  | presente  | DESYNC_AMAZON_ONLY |
      | CCC333   | presente | ausente  | ausente   | NOT_SENT           |
      | DDD444   | ausente  | presente | presente  | SENT_OK            |

  Escenario: Priorización por stock disponible en la vista de salud de catálogo
    Dado que los SKUs "AAA111" con stock 25 y "AAA222" con stock 1 son "DESYNC_FEED_ONLY"
    Cuando abro la Vista 3 "Salud de catálogo"
    Entonces "AAA111" aparece antes que "AAA222"
    Y ambos muestran un distintivo de "stock disponible"

  Escenario: Cruce insensible a suciedad de formato
    Dado que el feed contiene el SKU "TWA85XL"
    Y el reporte de Amazon contiene el SKU " twa85xl " con espacio NBSP final
    Cuando finaliza la conciliación
    Entonces ambos registros se cruzan como el mismo SKU "TWA85XL"
    Y no se genera ningún falso desincronizado
