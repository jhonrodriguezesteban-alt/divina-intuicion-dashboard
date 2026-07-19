"""
Agrega remisiones por día x sucursal -> reportes/ventas_diarias.json.
Se embebe en el dashboard para que los filtros rápidos de fecha
(Hoy/Ayer/7 días/30 días, rango de fechas, mes) recalculen las cifras en
JS puro, sin volver a tocar Python (patrón de JR ARQUITECTURA_REPLICABLE.md
sección 6).

"composicion_por_dia" (Pago total vs Pendiente de cobro) va aparte de
"por_dia" -a propósito- porque este último se recorre en JS con
Object.keys(dia) para sumar por sucursal (ver filtrarRango en el JS
embebido); mezclar ahí una clave que no es de sucursal rompería esa suma.
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_config

RAW = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_remisiones_completo.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "ventas_diarias.json"


def main():
    df_full = leer_excel_effi(RAW)
    df_full["Fecha de creación"] = pd.to_datetime(df_full["Fecha de creación"])
    df_full["dia"] = df_full["Fecha de creación"].dt.date.astype(str)

    sucursales_cfg = cargar_config("sucursales.json")["sucursales"]
    nombre_map = {s["nombre_effi"]: s["nombre"] for s in sucursales_cfg}
    df_full["sucursal_nombre"] = df_full["Sucursal"].map(nombre_map)

    df_pago = df_full[df_full["Estado CXC"] == "Pago total"]
    df_pendiente = df_full[df_full["Estado CXC"] == "Pendiente de cobro al día"]

    agg = (
        df_pago.groupby(["dia", "sucursal_nombre"])
        .agg(ingreso=("Total neto", "sum"), transacciones=("Total neto", "count"))
        .reset_index()
    )

    por_dia = {}
    for _, r in agg.iterrows():
        por_dia.setdefault(r["dia"], {})[r["sucursal_nombre"]] = {
            "ingreso": round(float(r["ingreso"]), 2),
            "transacciones": int(r["transacciones"]),
        }

    pago_por_dia = df_pago.groupby("dia")["Total neto"].sum()
    pendiente_por_dia = df_pendiente.groupby("dia")["Total neto"].sum()
    dias_composicion = set(pago_por_dia.index) | set(pendiente_por_dia.index)
    composicion_por_dia = {
        dia: {
            "pago_total": round(float(pago_por_dia.get(dia, 0.0)), 2),
            "pendiente_cobro": round(float(pendiente_por_dia.get(dia, 0.0)), 2),
        }
        for dia in dias_composicion
    }

    salida = {
        "sucursales": [s["nombre"] for s in sucursales_cfg],
        "por_dia": por_dia,
        "composicion_por_dia": composicion_por_dia,
    }

    OUT.write_text(json.dumps(salida, ensure_ascii=False), encoding="utf-8")
    print(f"{len(por_dia)} días agregados. Guardado en {OUT}")


if __name__ == "__main__":
    main()
