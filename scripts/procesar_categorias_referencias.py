"""
Procesa reportes/raw/raw_conceptos.xlsx (detalle por línea/artículo) ->
reportes/categorias_referencias.json

Rentabilidad por categoría + Top de referencias (artículos) por ventas
netas, solo sobre líneas con Estado CXC = "Pago total".
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi

RAW = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_conceptos.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "categorias_referencias.json"

INICIO_ANIO = pd.Timestamp("2026-01-01")


def _resumen(validas: pd.DataFrame) -> dict:
    categorias = (
        validas.groupby("Categoría artículo")
        .agg(ventas_netas=("Precio neto total", "sum"), utilidad=("Utilidad total (costo manual)", "sum"),
             unidades=("Cantidad", "sum"))
        .reset_index()
    )
    categorias["margen"] = (categorias["utilidad"] / categorias["ventas_netas"]).round(4)
    categorias = categorias.sort_values("ventas_netas", ascending=False)

    referencias = (
        validas.groupby(["Cod. artículo", "Descripción artículo"])
        .agg(unidades=("Cantidad", "sum"), ventas_netas=("Precio neto total", "sum"))
        .reset_index()
        .sort_values("ventas_netas", ascending=False)
        .head(20)
    )

    return {
        "unidades_totales": int(validas["Cantidad"].sum()),
        "categorias": [
            {
                "categoria": r["Categoría artículo"],
                "ventas_netas": round(float(r["ventas_netas"]), 2),
                "utilidad": round(float(r["utilidad"]), 2),
                "unidades": int(r["unidades"]),
                "margen": float(r["margen"]) if r["margen"] == r["margen"] else 0,
            }
            for _, r in categorias.iterrows()
        ],
        "top_referencias": [
            {
                "codigo": str(r["Cod. artículo"]),
                "nombre": r["Descripción artículo"],
                "unidades": int(r["unidades"]),
                "ventas_netas": round(float(r["ventas_netas"]), 2),
            }
            for _, r in referencias.iterrows()
        ],
    }


def main():
    df = leer_excel_effi(RAW)
    df["Fecha creación"] = pd.to_datetime(df["Fecha creación"])
    validas = df[df["Estado CXC"] == "Pago total"].copy()
    anio_actual = validas[validas["Fecha creación"] >= INICIO_ANIO]

    salida = {
        "anio_actual": _resumen(anio_actual),
        "historico": _resumen(validas),
    }

    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Año actual: {len(salida['anio_actual']['categorias'])} categorías, "
          f"{salida['anio_actual']['unidades_totales']} unidades")
    print(f"Histórico: {len(salida['historico']['categorias'])} categorías, "
          f"{salida['historico']['unidades_totales']} unidades")
    print(f"Guardado en {OUT}")


if __name__ == "__main__":
    main()
