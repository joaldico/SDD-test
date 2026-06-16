# language: es
Característica: Informe agregado por familias de error
  Como gestor de operaciones
  Quiero ver los errores agrupados por familia de negocio en una pestaña dedicada
  Para dimensionar el impacto de cada problema (ej. autorización de marca) de un vistazo

  Escenario: La familia de marca agrega todos sus códigos
    Dado que la conciliación produjo 1786 errores con código "18299"
    Y 118 errores con código "18749"
    Y ambos códigos pertenecen a la familia "AUTORIZACION_MARCA"
    Cuando abro la Vista 1 "Errores por familia"
    Entonces veo la familia "Autorización de marca" con el total de SKUs únicos afectados
    Y al desplegarla veo el desglose por código: "18299" y "18749" con sus recuentos
    Y al seleccionar un código veo la lista de SKUs afectados con la descripción del error

  Escenario: Un código desconocido nunca desaparece del informe
    Dado que el reporte de Amazon contiene el código "99999" que no existe en el catálogo
    Cuando finaliza la conciliación
    Entonces el código "99999" se registra en el catálogo asignado a la familia "SIN_CLASIFICAR"
    Y la Vista 1 muestra la familia "Sin clasificar" con un aviso visible
    Y los SKUs afectados por "99999" conservan su detalle completo en la Vista 2

  Escenario: La exportación replica la estructura de pestañas
    Dado que la conciliación está completada
    Cuando exporto el informe a formato xlsx
    Entonces el libro contiene una pestaña con la agregación por familia y código
    Y otra pestaña con el detalle SKU, código de error y descripción
    Y otra pestaña con la salud de catálogo
