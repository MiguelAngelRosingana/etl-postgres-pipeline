"""Carga: staging -> clientes -> ventas, todo con SQL basado en conjuntos."""
import json
import logging

from sqlalchemy import Connection, text

from etl.transform import Resultado

log = logging.getLogger(__name__)

COLUMNAS_STG = [
    "linea", "id_venta", "fecha", "cliente_email", "cliente_nombre",
    "producto", "categoria", "cantidad", "precio_unitario", "estado",
]

# Si el cliente ya existe, solo se actualiza el nombre cuando ha cambiado
SQL_UPSERT_CLIENTES = """
INSERT INTO core.clientes AS c (email, nombre)
SELECT DISTINCT ON (cliente_email) cliente_email, cliente_nombre
FROM stg.ventas
ORDER BY cliente_email, linea DESC
ON CONFLICT (email) DO UPDATE
    SET nombre = EXCLUDED.nombre
    WHERE c.nombre IS DISTINCT FROM EXCLUDED.nombre
"""

# Upsert idempotente. Solo toca las filas que realmente cambian.
# RETURNING (xmax = 0) distingue las insertadas (true) de las actualizadas (false).
SQL_UPSERT_VENTAS = """
WITH up AS (
    INSERT INTO core.ventas AS v
        (id_venta, fecha, cliente_id, producto, categoria, cantidad, precio_unitario, estado)
    SELECT s.id_venta, s.fecha, c.cliente_id, s.producto, s.categoria,
           s.cantidad, s.precio_unitario, s.estado
    FROM stg.ventas s
    JOIN core.clientes c ON c.email = s.cliente_email
    ON CONFLICT (id_venta) DO UPDATE
        SET fecha = EXCLUDED.fecha,
            cliente_id = EXCLUDED.cliente_id,
            producto = EXCLUDED.producto,
            categoria = EXCLUDED.categoria,
            cantidad = EXCLUDED.cantidad,
            precio_unitario = EXCLUDED.precio_unitario,
            estado = EXCLUDED.estado,
            actualizado_en = now()
        WHERE (v.fecha, v.cliente_id, v.producto, v.categoria,
               v.cantidad, v.precio_unitario, v.estado)
              IS DISTINCT FROM
              (EXCLUDED.fecha, EXCLUDED.cliente_id, EXCLUDED.producto, EXCLUDED.categoria,
               EXCLUDED.cantidad, EXCLUDED.precio_unitario, EXCLUDED.estado)
    RETURNING (xmax = 0) AS insertada
)
SELECT COUNT(*) FILTER (WHERE insertada)     AS insertadas,
       COUNT(*) FILTER (WHERE NOT insertada) AS actualizadas
FROM up
"""


def cargar_staging(conn: Connection, resultado: Resultado) -> None:
    conn.execute(text("TRUNCATE stg.ventas"))
    resultado.validas[COLUMNAS_STG].to_sql(
        "ventas", conn, schema="stg", if_exists="append", index=False,
        method="multi", chunksize=1000,
    )


def guardar_rechazadas(conn: Connection, run_id: int, resultado: Resultado) -> None:
    if resultado.rechazadas.empty:
        return
    filas = [
        {
            "run_id": run_id,
            "linea": int(r["linea"]),
            "motivo": r["motivo"],
            "datos": json.dumps({c: r[c] for c in resultado.rechazadas.columns
                                 if c not in ("linea", "motivo")}, ensure_ascii=False),
        }
        for _, r in resultado.rechazadas.iterrows()
    ]
    conn.execute(
        text("INSERT INTO etl.filas_rechazadas (run_id, linea, motivo, datos) "
             "VALUES (:run_id, :linea, :motivo, CAST(:datos AS JSONB))"),
        filas,
    )


def cargar(conn: Connection, run_id: int, resultado: Resultado) -> tuple[int, int]:
    """Carga un resultado ya validado. Devuelve (insertadas, actualizadas)."""
    cargar_staging(conn, resultado)
    conn.execute(text(SQL_UPSERT_CLIENTES))
    insertadas, actualizadas = conn.execute(text(SQL_UPSERT_VENTAS)).one()
    guardar_rechazadas(conn, run_id, resultado)
    log.info("Ventas insertadas: %d | actualizadas: %d", insertadas, actualizadas)
    return insertadas, actualizadas
