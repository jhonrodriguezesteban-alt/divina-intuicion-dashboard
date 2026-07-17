"""
Procesa reportes/raw/raw_articulos.xlsx -> reportes/inventario_procesado.json

v1: resumen general de inventario (aún sin cruce con ventas por SKU, así que
el índice de cobertura por artículo queda pendiente para la siguiente
iteración — ver config/inventario_config.json).
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_config

RAW = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_articulos.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "inventario_procesado.json"

COL_STOCK_POR_SUCURSAL = {
    "144": "Stock bodega: DIVINA INTUCION 144 (Sucursal: DIVINA INTUCION 144)",
    "433": "Stock bodega: DIVINA INTUICION 433 (Sucursal: DIVINA INTUCION 433)",
    "107": "Stock bodega: DIVINA ACCESORIOS (Sucursal: DIVINA ACCESORIOS)",
}


def main():
    df = leer_excel_effi(RAW)

    for col in ["Stock total empresa", "Costo manual", *COL_STOCK_POR_SUCURSAL.values()]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["valor_costo"] = df["Costo manual"] * df["Stock total empresa"]

    sucursales_cfg = {s["codigo"]: s["nombre"] for s in cargar_config("sucursales.json")["sucursales"]}

    stock_por_sucursal = {
        sucursales_cfg[codigo]: int(df[col].sum())
        for codigo, col in COL_STOCK_POR_SUCURSAL.items()
    }

    top_categorias = (
        df.groupby("Categoría")
        .agg(articulos=("ID", "count"), stock_total=("Stock total empresa", "sum"), valor_costo=("valor_costo", "sum"))
        .reset_index()
        .sort_values("valor_costo", ascending=False)
        .head(8)
        .to_dict(orient="records")
    )

    resumen = {
        "total_articulos": int(len(df)),
        "articulos_sin_stock": int((df["Stock total empresa"] == 0).sum()),
        "unidades_totales": int(df["Stock total empresa"].sum()),
        "valor_total_costo": round(float(df["valor_costo"].sum()), 2),
        "stock_por_sucursal": stock_por_sucursal,
        "top_categorias_por_valor": top_categorias,
    }

    OUT.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nGuardado en {OUT}")


if __name__ == "__main__":
    main()
