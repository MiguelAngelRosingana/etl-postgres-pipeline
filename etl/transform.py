"""Transformación y validación. Funciones puras: no tocan la base de datos, así se testean fácil."""
from dataclasses import dataclass
from datetime import date

import pandas as pd

COLUMNAS = [
    "id_venta", "fecha", "cliente_email", "cliente_nombre",
    "producto", "categoria", "cantidad", "precio_unitario", "estado",
]
ESTADOS = {"pendiente", "pagado", "enviado", "cancelado"}
RE_ID = r"^V\d{6}$"
RE_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


@dataclass
class Resultado:
    validas: pd.DataFrame       # filas listas para cargar (sin duplicados)
    rechazadas: pd.DataFrame    # filas que no pasan la validación, con su motivo
    n_leidas: int
    n_duplicadas: int           # filas válidas descartadas por repetir id_venta

    @property
    def n_validas(self) -> int:
        return len(self.validas)

    @property
    def n_rechazadas(self) -> int:
        return len(self.rechazadas)

    def cuadra(self) -> bool:
        """Reconciliación: todo lo leído está cargado, rechazado o descartado por duplicado."""
        return self.n_leidas == self.n_validas + self.n_rechazadas + self.n_duplicadas


def transformar(raw: pd.DataFrame, hoy: date | None = None) -> Resultado:
    hoy = hoy or date.today()
    df = raw.copy()
    df.insert(0, "linea", range(2, len(df) + 2))   # línea 1 es la cabecera
    originales = df.copy()                          # para guardar las rechazadas tal cual llegaron

    # --- normalización
    for col in COLUMNAS:
        df[col] = df[col].str.strip()
    df["cliente_email"] = df["cliente_email"].str.lower()
    df["cliente_nombre"] = df["cliente_nombre"].str.title()
    df["estado"] = df["estado"].str.lower()

    fecha = pd.to_datetime(df["fecha"], format="%Y-%m-%d", errors="coerce")
    cantidad = pd.to_numeric(df["cantidad"], errors="coerce")
    precio = pd.to_numeric(df["precio_unitario"], errors="coerce")

    # --- reglas de validación: (filas que fallan, motivo)
    reglas = [
        (~df["id_venta"].str.match(RE_ID), "id_venta inválido"),
        (fecha.isna(), "fecha inválida"),
        (fecha > pd.Timestamp(hoy), "fecha futura"),
        (~df["cliente_email"].str.match(RE_EMAIL), "email inválido"),
        (df["cliente_nombre"] == "", "nombre de cliente vacío"),
        (df["producto"] == "", "producto vacío"),
        (cantidad.isna() | (cantidad <= 0) | (cantidad % 1 != 0), "cantidad inválida"),
        (precio.isna() | (precio < 0), "precio inválido"),
        (~df["estado"].isin(ESTADOS), "estado no válido"),
    ]
    motivos = pd.Series("", index=df.index)
    for falla, texto in reglas:
        motivos[falla] = motivos[falla].map(lambda m, t=texto: f"{m}; {t}" if m else t)

    ok = motivos == ""
    validas = df[ok].copy()
    validas["fecha"] = fecha[ok].dt.date
    validas["cantidad"] = cantidad[ok].astype(int)
    validas["precio_unitario"] = precio[ok].round(2)
    validas["categoria"] = validas["categoria"].replace("", None)

    # --- deduplicación: si un id_venta aparece varias veces, gana la última línea del fichero
    antes = len(validas)
    validas = validas.sort_values("linea").drop_duplicates("id_venta", keep="last")
    n_duplicadas = antes - len(validas)

    rechazadas = originales[~ok].assign(motivo=motivos[~ok])
    return Resultado(
        validas=validas.reset_index(drop=True),
        rechazadas=rechazadas.reset_index(drop=True),
        n_leidas=len(df),
        n_duplicadas=n_duplicadas,
    )
