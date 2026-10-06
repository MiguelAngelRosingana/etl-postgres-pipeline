"""Tests de integración: necesitan PostgreSQL (TEST_DATABASE_URL)."""
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

import etl.load
from etl.extract import extraer
from etl.pipeline import ejecutar
from etl.transform import transformar

pytestmark = pytest.mark.integracion

MUESTRA = Path(__file__).resolve().parent.parent / "data" / "sample"
DIA1 = MUESTRA / "ventas_2026-10-01.csv"
DIA2 = MUESTRA / "ventas_2026-10-02.csv"
HOY = date(2026, 10, 6)


def valor(engine, sql: str, **params):
    with engine.connect() as conn:
        return conn.execute(text(sql), params).scalar_one()


def test_primera_carga_del_dia_1(bd_limpia):
    r = ejecutar(DIA1, bd_limpia, hoy=HOY)
    assert (r.estado, r.leidas, r.validas, r.rechazadas, r.duplicadas) == (
        "ok", 45, 40, 4, 1,
    )
    assert (r.insertadas, r.actualizadas) == (40, 0)
    assert valor(bd_limpia, "SELECT COUNT(*) FROM core.ventas") == 40
    esperados = transformar(extraer(DIA1), HOY).validas["cliente_email"].nunique()
    assert valor(bd_limpia, "SELECT COUNT(*) FROM core.clientes") == esperados
    # V000005 aparece dos veces en el fichero: gana la última versión
    estado = valor(bd_limpia, "SELECT estado FROM core.ventas WHERE id_venta = 'V000005'")
    assert estado == "enviado"


def test_el_mismo_fichero_no_se_procesa_dos_veces(bd_limpia):
    ejecutar(DIA1, bd_limpia, hoy=HOY)
    r2 = ejecutar(DIA1, bd_limpia, hoy=HOY)
    assert r2.estado == "omitido"
    assert valor(bd_limpia, "SELECT COUNT(*) FROM core.ventas") == 40
    assert valor(bd_limpia, "SELECT COUNT(*) FROM etl.ejecuciones WHERE estado = 'omitido'") == 1


def test_forzar_la_recarga_es_idempotente(bd_limpia):
    ejecutar(DIA1, bd_limpia, hoy=HOY)
    r2 = ejecutar(DIA1, bd_limpia, hoy=HOY, forzar=True)
    assert (r2.estado, r2.insertadas, r2.actualizadas) == ("ok", 0, 0)
    assert valor(bd_limpia, "SELECT COUNT(*) FROM core.ventas") == 40


def test_el_dia_2_inserta_lo_nuevo_y_actualiza_las_correcciones(bd_limpia):
    ejecutar(DIA1, bd_limpia, hoy=HOY)
    q = "SELECT cantidad FROM core.ventas WHERE id_venta = 'V000020'"
    antes = valor(bd_limpia, q)
    r2 = ejecutar(DIA2, bd_limpia, hoy=HOY)
    assert r2.estado == "ok"
    assert (r2.leidas, r2.validas, r2.rechazadas) == (36, 32, 4)
    assert r2.insertadas == 25                      # las 25 ventas nuevas
    assert r2.actualizadas >= 3                     # al menos las 3 correcciones de cantidad
    assert valor(bd_limpia, "SELECT COUNT(*) FROM core.ventas") == 65
    assert valor(bd_limpia, q) == antes + 1
    # la columna generada se recalcula sola con el cambio
    assert valor(bd_limpia, "SELECT total = cantidad * precio_unitario "
                            "FROM core.ventas WHERE id_venta = 'V000020'")


def test_las_filas_rechazadas_se_guardan_con_su_motivo(bd_limpia):
    r = ejecutar(DIA1, bd_limpia, hoy=HOY)
    n = valor(bd_limpia, "SELECT COUNT(*) FROM etl.filas_rechazadas WHERE run_id = :r", r=r.run_id)
    assert n == 4
    motivo = valor(
        bd_limpia,
        "SELECT motivo FROM etl.filas_rechazadas "
        "WHERE run_id = :r AND datos->>'id_venta' = 'V000041'",
        r=r.run_id,
    )
    assert motivo == "email inválido"


def test_si_la_carga_falla_no_queda_nada_a_medias(bd_limpia, monkeypatch):
    def falla(*args, **kwargs):
        raise RuntimeError("fallo simulado al final de la carga")

    monkeypatch.setattr(etl.load, "guardar_rechazadas", falla)
    with pytest.raises(RuntimeError):
        ejecutar(DIA1, bd_limpia, hoy=HOY)
    # ventas y clientes ya se habían escrito dentro de la transacción: deben haberse deshecho
    assert valor(bd_limpia, "SELECT COUNT(*) FROM core.ventas") == 0
    assert valor(bd_limpia, "SELECT COUNT(*) FROM core.clientes") == 0
    # pero la ejecución sí queda registrada como error
    assert valor(bd_limpia, "SELECT estado FROM etl.ejecuciones") == "error"
    assert "fallo simulado" in valor(bd_limpia, "SELECT mensaje FROM etl.ejecuciones")


def test_un_fichero_sin_las_columnas_esperadas_se_registra_como_error(bd_limpia, tmp_path):
    malo = tmp_path / "malo.csv"
    malo.write_text("id_venta,fecha\nV000001,2026-10-01\n", encoding="utf-8")
    with pytest.raises(ValueError):
        ejecutar(malo, bd_limpia, hoy=HOY)
    assert valor(bd_limpia, "SELECT estado FROM etl.ejecuciones") == "error"


def test_la_clave_foranea_impide_borrar_un_cliente_con_ventas(bd_limpia):
    ejecutar(DIA1, bd_limpia, hoy=HOY)
    with pytest.raises(IntegrityError), bd_limpia.begin() as conn:
        conn.execute(text("DELETE FROM core.clientes"))


def test_una_categoria_vacia_se_guarda_como_nulo_en_la_base_de_datos(bd_limpia, tmp_path):
    f = tmp_path / "ventas.csv"
    f.write_text(
        "id_venta,fecha,cliente_email,cliente_nombre,producto,categoria,cantidad,"
        "precio_unitario,estado\n"
        "V000001,2026-10-01,ana@mail.com,Ana Ruiz,Ratón,,1,19.90,pagado\n",
        encoding="utf-8",
    )
    ejecutar(f, bd_limpia, hoy=HOY)
    assert valor(bd_limpia, "SELECT categoria IS NULL FROM core.ventas")
