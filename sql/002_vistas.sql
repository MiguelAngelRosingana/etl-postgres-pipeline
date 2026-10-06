-- Vistas de consulta. Power BI o cualquier herramienta puede leer de aquí.

CREATE VIEW core.v_ventas_mensuales AS
SELECT date_trunc('month', v.fecha)::date AS mes,
       v.categoria,
       COUNT(*)                           AS pedidos,
       SUM(v.cantidad)                    AS unidades,
       SUM(v.total)                       AS importe
FROM core.ventas v
WHERE v.estado <> 'cancelado'
GROUP BY 1, 2;

CREATE VIEW etl.v_resumen_ejecuciones AS
SELECT run_id, fichero, estado, inicio,
       round(extract(epoch FROM (fin - inicio))::numeric, 2) AS segundos,
       filas_leidas, filas_validas, filas_rechazadas, filas_duplicadas,
       ventas_insertadas, ventas_actualizadas, mensaje
FROM etl.ejecuciones
ORDER BY run_id DESC;
