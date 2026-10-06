from datetime import date

import pandas as pd
import pytest

from etl.transform import COLUMNAS, transformar

HOY = date(2026, 10, 6)


def fila(**cambios) -> dict:
    base = {
        "id_venta": "V000001", "fecha": "2026-10-01", "cliente_email": "ana@mail.com",
        "cliente_nombre": "Ana Ruiz", "producto": "Ratón", "categoria": "Informática",
        "cantidad": "2", "precio_unitario": "19.90", "estado": "pagado",
    }
    base.update(cambios)
    return base


def df(*filas: dict) -> pd.DataFrame:
    return pd.DataFrame(list(filas), columns=COLUMNAS, dtype=str)


def test_fila_valida_pasa_y_se_tipa():
    r = transformar(df(fila()), HOY)
    assert r.n_validas == 1 and r.n_rechazadas == 0
    v = r.validas.iloc[0]
    assert v["fecha"] == date(2026, 10, 1)
    assert v["cantidad"] == 2
    assert v["precio_unitario"] == pytest.approx(19.90)


def test_normaliza_email_nombre_y_estado():
    sucia = fila(cliente_email="  ANA@Mail.COM ", cliente_nombre="ana ruiz", estado="PAGADO")
    r = transformar(df(sucia), HOY)
    v = r.validas.iloc[0]
    assert v["cliente_email"] == "ana@mail.com"
    assert v["cliente_nombre"] == "Ana Ruiz"
    assert v["estado"] == "pagado"


@pytest.mark.parametrize(("campo", "valor", "motivo"), [
    ("id_venta", "", "id_venta inválido"),
    ("id_venta", "X1", "id_venta inválido"),
    ("fecha", "2026-13-45", "fecha inválida"),
    ("fecha", "01/10/2026", "fecha inválida"),
    ("fecha", "2099-01-01", "fecha futura"),
    ("cliente_email", "sin-arroba.com", "email inválido"),
    ("cliente_nombre", "  ", "nombre de cliente vacío"),
    ("producto", "", "producto vacío"),
    ("cantidad", "0", "cantidad inválida"),
    ("cantidad", "-2", "cantidad inválida"),
    ("cantidad", "1.5", "cantidad inválida"),
    ("cantidad", "dos", "cantidad inválida"),
    ("precio_unitario", "abc", "precio inválido"),
    ("precio_unitario", "-1", "precio inválido"),
    ("estado", "devuelto", "estado no válido"),
])
def test_rechaza_con_su_motivo(campo, valor, motivo):
    r = transformar(df(fila(**{campo: valor})), HOY)
    assert r.n_validas == 0 and r.n_rechazadas == 1
    assert motivo in r.rechazadas.iloc[0]["motivo"]


def test_acumula_varios_motivos():
    r = transformar(df(fila(cliente_email="mal", cantidad="-1")), HOY)
    motivo = r.rechazadas.iloc[0]["motivo"]
    assert "email inválido" in motivo and "cantidad inválida" in motivo


def test_la_rechazada_conserva_la_fila_original_y_su_linea():
    r = transformar(df(fila(), fila(id_venta="V000002", cliente_email=" MAL ")), HOY)
    rech = r.rechazadas.iloc[0]
    assert rech["linea"] == 3                      # cabecera = línea 1; esta es la segunda fila
    assert rech["cliente_email"] == " MAL "        # sin normalizar: tal como llegó


def test_si_un_id_se_repite_gana_la_ultima_linea():
    r = transformar(df(fila(estado="pendiente"), fila(estado="enviado")), HOY)
    assert r.n_validas == 1 and r.n_duplicadas == 1
    assert r.validas.iloc[0]["estado"] == "enviado"


def test_fecha_futura_depende_de_la_fecha_de_referencia():
    fila_futura = fila(fecha="2026-10-10")
    assert transformar(df(fila_futura), date(2026, 10, 6)).n_rechazadas == 1
    assert transformar(df(fila_futura), date(2026, 10, 10)).n_rechazadas == 0


def test_categoria_vacia_se_guarda_como_nulo():
    r = transformar(df(fila(categoria="")), HOY)
    assert pd.isna(r.validas.iloc[0]["categoria"])


def test_la_reconciliacion_cuadra_con_datos_mezclados():
    r = transformar(df(
        fila(), fila(id_venta="V000002", cantidad="x"),
        fila(estado="enviado"), fila(id_venta="V000003"),
    ), HOY)
    assert (r.n_leidas, r.n_validas, r.n_rechazadas, r.n_duplicadas) == (4, 2, 1, 1)
    assert r.cuadra()
