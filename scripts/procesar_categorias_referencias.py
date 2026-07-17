"""
Procesa reportes/raw/raw_conceptos.xlsx (detalle por línea/artículo) ->
reportes/categorias_referencias.json

Rentabilidad por categoría + Top de referencias (artículos) por ventas
netas, solo sobre líneas con Estado CXC = "Pago total".
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_config

RAW = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_conceptos.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "categorias_referencias.json"

INICIO_ANIO = pd.Timestamp("2026-01-01")
TOP_N = 10


def _resumen(validas: pd.DataFrame, nombre_map: dict) -> dict:
    validas = validas.copy()
    validas["sucursal_nombre"] = validas["Sucursal"].map(nombre_map)

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

    # detalle por sucursal, solo para las referencias top que se muestran expandibles.
    # "Cod. artículo" NO es único por sí solo (Effi reutiliza el mismo código para
    # variantes/artículos distintos) — hay que combinarlo con la descripción para
    # no mezclar productos distintos en el mismo detalle.
    top_refs = referencias.head(TOP_N)[["Cod. artículo", "Descripción artículo"]].values.tolist()
    por_sucursal_ref = {}
    for cod, nombre in top_refs:
        sub = (
            validas[(validas["Cod. artículo"] == cod) & (validas["Descripción artículo"] == nombre)]
            .groupby("sucursal_nombre")
            .agg(unidades=("Cantidad", "sum"), ventas_netas=("Precio neto total", "sum"))
            .reset_index()
            .sort_values("ventas_netas", ascending=False)
        )
        clave = f"{cod}::{nombre}"
        por_sucursal_ref[clave] = [
            {"sucursal": r["sucursal_nombre"], "unidades": int(r["unidades"]), "ventas_netas": round(float(r["ventas_netas"]), 2)}
            for _, r in sub.iterrows()
        ]

    # top productos dentro de cada una de las categorías top, para el expandible de rentabilidad
    top_categorias = categorias.head(TOP_N)["Categoría artículo"].tolist()
    productos_por_categoria = {}
    for cat in top_categorias:
        sub = (
            validas[validas["Categoría artículo"] == cat]
            .groupby(["Cod. artículo", "Descripción artículo"])
            .agg(unidades=("Cantidad", "sum"), ventas_netas=("Precio neto total", "sum"))
            .reset_index()
            .sort_values("ventas_netas", ascending=False)
            .head(5)
        )
        productos_por_categoria[cat] = [
            {"codigo": str(r["Cod. artículo"]), "nombre": r["Descripción artículo"],
             "unidades": int(r["unidades"]), "ventas_netas": round(float(r["ventas_netas"]), 2)}
            for _, r in sub.iterrows()
        ]

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
        "top_referencias_por_sucursal": por_sucursal_ref,
        "productos_por_categoria": productos_por_categoria,
    }


def main():
    df = leer_excel_effi(RAW)
    df["Fecha creación"] = pd.to_datetime(df["Fecha creación"])
    validas = df[df["Estado CXC"] == "Pago total"].copy()
    anio_actual = validas[validas["Fecha creación"] >= INICIO_ANIO]

    sucursales_cfg = cargar_config("sucursales.json")["sucursales"]
    nombre_map = {s["nombre_effi"]: s["nombre"] for s in sucursales_cfg}

    salida = {
        "anio_actual": _resumen(anio_actual, nombre_map),
        "historico": _resumen(validas, nombre_map),
    }

    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Año actual: {len(salida['anio_actual']['categorias'])} categorías, "
          f"{salida['anio_actual']['unidades_totales']} unidades")
    print(f"Histórico: {len(salida['historico']['categorias'])} categorías, "
          f"{salida['historico']['unidades_totales']} unidades")
    print(f"Guardado en {OUT}")


if __name__ == "__main__":
    main()
