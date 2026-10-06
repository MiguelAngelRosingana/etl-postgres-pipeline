"""Orquestación: control de ejecuciones, transacción única y reconciliación."""
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy import Engine, text

from etl.extract import extraer, sha256_fichero
from etl.load import cargar
from etl.transform import transformar

log = logging.getLogger(__name__)


@dataclass
class Resumen:
    run_id: int
    estado: str
    leidas: int = 0
    validas: int = 0
    rechazadas: int = 0
    duplicadas: int = 0
    insertadas: int = 0
    actualizadas: int = 0


def _iniciar_run(engine: Engine, fichero: str, sha: str) -> int:
    # Transacción propia: el registro de la ejecución sobrevive aunque la carga haga rollback
    with engine.begin() as conn:
        return conn.execute(
            text("INSERT INTO etl.ejecuciones (fichero, sha256, estado) "
                 "VALUES (:f, :s, 'en_curso') RETURNING run_id"),
            {"f": fichero, "s": sha},
        ).scalar_one()


def _cerrar_run(conn, run_id: int, estado: str, mensaje: str | None = None, **cifras) -> None:
    conn.execute(
        text("""UPDATE etl.ejecuciones SET fin = now(), estado = :estado, mensaje = :mensaje,
                    filas_leidas = :leidas, filas_validas = :validas,
                    filas_rechazadas = :rechazadas, filas_duplicadas = :duplicadas,
                    ventas_insertadas = :insertadas, ventas_actualizadas = :actualizadas
                WHERE run_id = :run_id"""),
        {"run_id": run_id, "estado": estado, "mensaje": mensaje,
         "leidas": None, "validas": None, "rechazadas": None, "duplicadas": None,
         "insertadas": None, "actualizadas": None, **cifras},
    )


def _ya_procesado(engine: Engine, sha: str) -> bool:
    with engine.connect() as conn:
        return conn.execute(
            text("SELECT EXISTS (SELECT 1 FROM etl.ejecuciones "
                 "WHERE sha256 = :s AND estado = 'ok')"),
            {"s": sha},
        ).scalar_one()


def ejecutar(ruta: Path, engine: Engine, hoy: date | None = None, forzar: bool = False) -> Resumen:
    """Procesa un fichero. Si algo falla, no queda nada a medias."""
    sha = sha256_fichero(ruta)
    run_id = _iniciar_run(engine, ruta.name, sha)

    if not forzar and _ya_procesado(engine, sha):
        log.warning("%s ya se procesó con el mismo contenido: se omite", ruta.name)
        with engine.begin() as conn:
            _cerrar_run(conn, run_id, "omitido", "Fichero ya procesado (mismo SHA-256)")
        return Resumen(run_id, "omitido")

    try:
        resultado = transformar(extraer(ruta), hoy)
        if not resultado.cuadra():   # no debería pasar nunca; si pasa, mejor parar
            raise RuntimeError("La reconciliación de filas no cuadra")
        log.info("Válidas: %d | rechazadas: %d | duplicadas: %d",
                 resultado.n_validas, resultado.n_rechazadas, resultado.n_duplicadas)

        # Una sola transacción: datos y cierre de la ejecución se confirman juntos, o ninguno
        with engine.begin() as conn:
            insertadas, actualizadas = cargar(conn, run_id, resultado)
            _cerrar_run(
                conn, run_id, "ok",
                leidas=resultado.n_leidas, validas=resultado.n_validas,
                rechazadas=resultado.n_rechazadas, duplicadas=resultado.n_duplicadas,
                insertadas=insertadas, actualizadas=actualizadas,
            )
        return Resumen(run_id, "ok", resultado.n_leidas, resultado.n_validas,
                       resultado.n_rechazadas, resultado.n_duplicadas, insertadas, actualizadas)
    except Exception as e:
        log.exception("ETL fallida: %s", ruta.name)
        with engine.begin() as conn:    # la carga ya hizo rollback; esto deja constancia del error
            _cerrar_run(conn, run_id, "error", str(e)[:500])
        raise
