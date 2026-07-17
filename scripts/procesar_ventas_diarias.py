"""
Agrega remisiones por día x sucursal -> reportes/ventas_diarias.json.
Se embebe en el dashboard para que los filtros rápidos de fecha
(Hoy/Ayer/7 días/30 días) recalculen las cifras en JS puro, sin volver a
tocar Python (patrón de JR ARQUITECTURA_REPLICABLE.md sección 6).
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_config

RAW = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_remisiones_completo.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "ventas_diarias.json"


def main():
    df = leer_excel_effi(RAW)
    df = df[df["Estado CXC"] == "Pago total"].copy()
    df["Fecha de creación"] = pd.to_datetime(df["Fecha de creación"])
    df["dia"] = df["Fecha de creación"].dt.date.astype(str)

    sucursales_cfg = cargar_config("sucursales.json")["sucursales"]
    nombre_map = {s["nombre_effi"]: s["nombre"] for s in sucursales_cfg}
    df["sucursal_nombre"] = df["Sucursal"].map(nombre_map)

    agg = (
        df.groupby(["dia", "sucursal_nombre"])
        .agg(ingreso=("Total neto", "sum"), transacciones=("Total neto", "count"))
        .reset_index()
    )

    por_dia = {}
    for _, r in agg.iterrows():
        por_dia.setdefault(r["dia"], {})[r["sucursal_nombre"]] = {
            "ingreso": round(float(r["ingreso"]), 2),
            "transacciones": int(r["transacciones"]),
        }

    salida = {
        "sucursales": [s["nombre"] for s in sucursales_cfg],
        "por_dia": por_dia,
    }

    OUT.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    print(f"{len(por_dia)} días agregados. Guardado en {OUT}")


if __name__ == "__main__":
    main()
