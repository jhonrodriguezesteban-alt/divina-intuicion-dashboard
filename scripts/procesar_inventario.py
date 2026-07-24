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

    # Effi puede renombrar/reorganizar bodegas (ya pasó: la columna de
    # DIVINA ACCESORIOS desapareció y salió una "BODEGA PRINCIPAL" nueva) --
    # sin este chequeo, una columna faltante tumbaba todo el cierre en vez
    # de solo dejar esa sucursal en 0 y avisar.
    cols_presentes = {c: col for c, col in COL_STOCK_POR_SUCURSAL.items() if col in df.columns}
    cols_faltantes = [col for c, col in COL_STOCK_POR_SUCURSAL.items() if c not in cols_presentes]
    if cols_faltantes:
        print(f"AVISO: no se encontraron estas columnas de stock por bodega en Effi "
              f"(¿se renombró o reorganizó la bodega?): {cols_faltantes}")
        otras_bodegas = [c for c in df.columns if c.startswith("Stock bodega:") and c not in COL_STOCK_POR_SUCURSAL.values()]
        if otras_bodegas:
            print(f"Columnas de bodega presentes sin mapear a ninguna sucursal: {otras_bodegas}")

    for col in ["Stock total empresa", "Costo manual", *cols_presentes.values()]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["valor_costo"] = df["Costo manual"] * df["Stock total empresa"]

    sucursales_cfg = {s["codigo"]: s["nombre"] for s in cargar_config("sucursales.json")["sucursales"]}

    stock_por_sucursal = {
        sucursales_cfg[codigo]: (int(df[cols_presentes[codigo]].sum()) if codigo in cols_presentes else 0)
        for codigo in COL_STOCK_POR_SUCURSAL
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
