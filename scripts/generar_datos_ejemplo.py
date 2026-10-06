"""Genera dos CSV de ventas con datos sucios a propósito, de forma reproducible (semilla fija).

El segundo día incluye correcciones de ventas del primero, para probar la carga incremental.
Uso:  python scripts/generar_datos_ejemplo.py
"""
import csv
import random
from pathlib import Path

DESTINO = Path(__file__).resolve().parent.parent / "data" / "sample"
CABECERA = ["id_venta", "fecha", "cliente_email", "cliente_nombre", "producto",
            "categoria", "cantidad", "precio_unitario", "estado"]

PRODUCTOS = [
    ("Portátil", "Informática", 899.00), ("Ratón", "Informática", 19.90),
    ("Teclado", "Informática", 44.50), ("Monitor", "Informática", 189.00),
    ("Silla", "Hogar", 119.00), ("Lámpara", "Hogar", 29.90),
    ("Auriculares", "Audio", 59.00), ("Altavoz", "Audio", 79.00),
]
CLIENTES = [
    ("ana.ruiz@mail.com", "Ana Ruiz"), ("luis.gil@mail.com", "Luis Gil"),
    ("marta.soto@mail.com", "Marta Soto"), ("pablo.vega@mail.com", "Pablo Vega"),
    ("sara.leon@mail.com", "Sara León"), ("raul.nieto@mail.com", "Raúl Nieto"),
    ("lucia.mora@mail.com", "Lucía Mora"), ("diego.sanz@mail.com", "Diego Sanz"),
    ("elena.rey@mail.com", "Elena Rey"), ("hugo.cano@mail.com", "Hugo Cano"),
]
ESTADOS = ["pendiente", "pagado", "enviado", "cancelado"]


def venta(rng: random.Random, n: int, fecha: str) -> list:
    producto, categoria, precio = rng.choice(PRODUCTOS)
    email, nombre = rng.choice(CLIENTES)
    return [f"V{n:06d}", fecha, email, nombre, producto, categoria,
            rng.randint(1, 4), f"{precio:.2f}", rng.choice(ESTADOS)]


def escribir(nombre: str, filas: list[list]) -> None:
    DESTINO.mkdir(parents=True, exist_ok=True)
    with (DESTINO / nombre).open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CABECERA)
        w.writerows(filas)


def main() -> None:
    rng = random.Random(42)

    # ---- día 1: 40 ventas correctas y varios errores típicos
    dia1 = [venta(rng, n, "2026-10-01") for n in range(1, 41)]
    dia1[2][2] = "  ANA.RUIZ@Mail.com "                     # espacios y mayúsculas: se normaliza
    dia1[2][3] = "ana ruiz"
    dia1 += [
        ["V000041", "2026-10-01", "pablo-vega.mail.com", "Pablo Vega", "Ratón", "Informática",
         1, "19.90", "pagado"],                                    # email inválido
        ["V000042", "2026-10-01", "luis.gil@mail.com", "Luis Gil", "Teclado", "Informática",
         -2, "44.50", "pagado"],                                   # cantidad negativa
        ["V000043", "2026-13-45", "marta.soto@mail.com", "Marta Soto", "Silla", "Hogar",
         1, "119.00", "pendiente"],                                # fecha imposible
        ["", "2026-10-01", "sara.leon@mail.com", "Sara León", "Lámpara", "Hogar",
         1, "29.90", "pagado"],                                    # sin id
    ]
    repetida = list(dia1[4])
    repetida[8] = "enviado"        # V000005 repetida: gana la última
    dia1.append(repetida)
    escribir("ventas_2026-10-01.csv", dia1)

    # ---- día 2: 25 ventas nuevas, correcciones de ventas del día 1 y errores
    dia2 = [venta(rng, n, "2026-10-02") for n in range(50, 75)]
    for n, nuevo_estado in [(3, "enviado"), (7, "cancelado"), (12, "pagado"), (15, "enviado")]:
        corregida = list(dia1[n - 1])
        corregida[8] = nuevo_estado                                 # cambia el estado
        dia2.append(corregida)
    for n in (20, 25, 30):
        corregida = list(dia1[n - 1])
        corregida[6] = int(corregida[6]) + 1                        # corrige la cantidad
        dia2.append(corregida)
    dia2 += [
        ["V000090", "2026-10-02", "hugo.cano@mail.com", "Hugo Cano", "Monitor", "Informática",
         1, "abc", "pagado"],                                       # precio no numérico
        ["V000091", "2026-10-02", "elena.rey@mail.com", "Elena Rey", "Altavoz", "Audio",
         1, "79.00", "devuelto"],                                   # estado desconocido
        ["V000092", "2026-10-02", "diego.sanz@mail.com", "Diego Sanz", "", "Hogar",
         1, "29.90", "pagado"],                                     # producto vacío
        ["V000093", "2099-01-01", "raul.nieto@mail.com", "Raúl Nieto", "Ratón", "Informática",
         2, "19.90", "pendiente"],                                  # fecha futura
    ]
    escribir("ventas_2026-10-02.csv", dia2)
    print("Generados:", *sorted(p.name for p in DESTINO.glob("*.csv")))


if __name__ == "__main__":
    main()
