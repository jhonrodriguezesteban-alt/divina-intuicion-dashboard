"""
Procesa reportes/raw/raw_remisiones.xlsx -> reportes/ventas_procesado.json

Regla de negocio (JR ARQUITECTURA_REPLICABLE.md 5.3): el ingreso real se mide
por remisiones con Estado CXC = "Pago total". Se excluyen anuladas.
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_config

RAW = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_remisiones.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "ventas_procesado.json"


def main():
    df = leer_excel_effi(RAW)
    df["Fecha de creación"] = pd.to_datetime(df["Fecha de creación"])
    df["dia"] = df["Fecha de creación"].dt.date.astype(str)

    ventas = df[df["Estado CXC"] == "Pago total"].copy()
    anuladas = df[df["Estado CXC"] == "Anulado"]

    sucursales_cfg = cargar_config("sucursales.json")["sucursales"]
    nombre_a_codigo = {s["nombre_effi"]: s["codigo"] for s in sucursales_cfg}

    ventas["codigo_sucursal"] = ventas["Sucursal"].map(nombre_a_codigo)

    kpis = {
        "ingreso_total": round(float(ventas["Total neto"].sum()), 2),
        "num_transacciones": int(len(ventas)),
        "ticket_promedio": round(float(ventas["Total neto"].mean()), 2) if len(ventas) else 0,
        "utilidad_total_costo_promedio": round(float(ventas["Utilidad (costo promedio)"].sum()), 2),
        "margen_promedio": round(float(ventas["Margen de utilidad (costo promedio)"].mean()), 4) if len(ventas) else 0,
        "num_anuladas": int(len(anuladas)),
        "rango_fechas": {
            "desde": ventas["dia"].min() if len(ventas) else None,
            "hasta": ventas["dia"].max() if len(ventas) else None,
        },
    }

    por_sucursal = (
        ventas.groupby(["codigo_sucursal", "Sucursal"])
        .agg(ingreso=("Total neto", "sum"), transacciones=("Total neto", "count"),
             utilidad=("Utilidad (costo promedio)", "sum"))
        .reset_index()
        .to_dict(orient="records")
    )

    por_dia_sucursal = (
        ventas.groupby(["dia", "codigo_sucursal"])
        .agg(ingreso=("Total neto", "sum"), transacciones=("Total neto", "count"))
        .reset_index()
        .to_dict(orient="records")
    )

    salida = {
        "kpis": kpis,
        "por_sucursal": por_sucursal,
        "por_dia_sucursal": por_dia_sucursal,
    }

    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Procesado: {len(ventas)} ventas válidas, {len(anuladas)} anuladas. Guardado en {OUT}")
    print(json.dumps(kpis, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
