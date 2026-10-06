"""Línea de comandos: init-db, run y resumen."""
import argparse
import logging
from datetime import date
from pathlib import Path

from sqlalchemy import text

from etl.config import database_url
from etl.db import aplicar_sql, crear_engine
from etl.pipeline import ejecutar


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="etl", description="Pipeline ETL de ventas a PostgreSQL")
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("init-db", help="Crea el esquema en la base de datos")
    r = sub.add_parser("run", help="Procesa un fichero CSV")
    r.add_argument("fichero", type=Path)
    r.add_argument("--forzar", action="store_true", help="Procesar aunque ya se haya cargado")
    r.add_argument("--hoy", type=date.fromisoformat, help="Fecha de referencia (AAAA-MM-DD)")
    sub.add_parser("resumen", help="Muestra las últimas ejecuciones")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    args = _parser().parse_args(argv)
    engine = crear_engine(database_url())

    if args.comando == "init-db":
        for nombre in aplicar_sql(engine):
            print(f"Aplicado {nombre}")
        return 0

    if args.comando == "run":
        try:
            r = ejecutar(args.fichero, engine, hoy=args.hoy, forzar=args.forzar)
        except Exception:
            return 1
        print(f"run {r.run_id}: {r.estado} | leídas {r.leidas} | válidas {r.validas} | "
              f"rechazadas {r.rechazadas} | duplicadas {r.duplicadas} | "
              f"insertadas {r.insertadas} | actualizadas {r.actualizadas}")
        return 0

    with engine.connect() as conn:
        consulta = text("SELECT * FROM etl.v_resumen_ejecuciones LIMIT 10")
        filas = conn.execute(consulta).mappings().all()
    print(f"{'run':>4} {'estado':<8} {'fichero':<24} {'leídas':>6} {'válidas':>7} "
          f"{'rechaz.':>7} {'dupl.':>5} {'insert.':>7} {'actual.':>7}")
    for f in filas:
        print(f"{f['run_id']:>4} {f['estado']:<8} {f['fichero']:<24} {f['filas_leidas'] or 0:>6} "
              f"{f['filas_validas'] or 0:>7} {f['filas_rechazadas'] or 0:>7} "
              f"{f['filas_duplicadas'] or 0:>5} {f['ventas_insertadas'] or 0:>7} "
              f"{f['ventas_actualizadas'] or 0:>7}")
    return 0
