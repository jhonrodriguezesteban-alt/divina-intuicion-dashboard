"""
Procesa reportes/raw/raw_conceptos.xlsx (detalle por línea/artículo) ->
reportes/categorias_referencias.json

Rentabilidad por categoría + Top de referencias (artículos) por ventas
netas, solo sobre líneas con Estado CXC = "Pago total".

Se agrupa por REFERENCIA (nombre sin talla, ver common.procesamiento.
referencia_base) — igual que en el módulo de reorden: sin esto, un mismo
diseño en varias tallas ("SET JEAN SOL T8" / "SET JEAN SOL T10") aparece
repetido como si fueran productos distintos, diluyendo su ranking real.

Devuelve TODAS las categorías y referencias (no solo un top N) — el
dashboard las muestra en una tarjeta con scroll, no recortadas.
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import cargar_conceptos_combinados, cargar_config, referencia_base, talla_de

OUT = Path(__file__).resolve().parent.parent / "reportes" / "categorias_referencias.json"

_HOY = pd.Timestamp.now().normalize()
INICIO_ANIO = pd.Timestamp(year=_HOY.year, month=1, day=1)
INICIO_MES = pd.Timestamp(year=_HOY.year, month=_HOY.month, day=1)


def _resumen(validas: pd.DataFrame, nombre_map: dict) -> dict:
    validas = validas.copy()
    validas["sucursal_nombre"] = validas["Sucursal"].map(nombre_map)
    validas["referencia"] = validas["Descripción artículo"].apply(referencia_base)

    categorias = (
        validas.groupby("Categoría artículo")
        .agg(ventas_netas=("Precio neto total", "sum"), utilidad=("Utilidad total (costo manual)", "sum"),
             unidades=("Cantidad", "sum"))
        .reset_index()
    )
    categorias["margen"] = (categorias["utilidad"] / categorias["ventas_netas"]).round(4)
    categorias = categorias.sort_values("ventas_netas", ascending=False)

    referencias = (
        validas.groupby("referencia")
        .agg(unidades=("Cantidad", "sum"), ventas_netas=("Precio neto total", "sum"))
        .reset_index()
        .sort_values("ventas_netas", ascending=False)
    )

    # detalle por sucursal, para cada referencia (ya expandible en el dashboard) -- y dentro de
    # cada sucursal, el detalle por talla/color (variantes reales que Effi trae como filas
    # separadas y que referencia_base() agrupó), para el segundo nivel de expandible.
    por_sucursal_ref = {}
    for ref in referencias["referencia"]:
        sub_ref = validas[validas["referencia"] == ref]
        sub = (
            sub_ref.groupby("sucursal_nombre")
            .agg(unidades=("Cantidad", "sum"), ventas_netas=("Precio neto total", "sum"))
            .reset_index()
            .sort_values("ventas_netas", ascending=False)
        )
        filas_sucursal = []
        for _, r in sub.iterrows():
            suc_nombre = r["sucursal_nombre"]
            sub_variantes = (
                sub_ref[sub_ref["sucursal_nombre"] == suc_nombre]
                .groupby("Descripción artículo")
                .agg(unidades=("Cantidad", "sum"), ventas_netas=("Precio neto total", "sum"))
                .reset_index()
                .sort_values("ventas_netas", ascending=False)
            )
            variantes = [
                {
                    "nombre": talla_de(vr["Descripción artículo"], ref),
                    "unidades": int(vr["unidades"]),
                    "ventas_netas": round(float(vr["ventas_netas"]), 2),
                }
                for _, vr in sub_variantes.iterrows()
            ]
            filas_sucursal.append({
                "sucursal": suc_nombre,
                "unidades": int(r["unidades"]),
                "ventas_netas": round(float(r["ventas_netas"]), 2),
                "variantes": variantes,
            })
        por_sucursal_ref[ref] = filas_sucursal

    # top productos (ya agrupados por referencia) dentro de cada categoría, para el expandible de rentabilidad
    productos_por_categoria = {}
    for cat in categorias["Categoría artículo"]:
        sub = (
            validas[validas["Categoría artículo"] == cat]
            .groupby("referencia")
            .agg(unidades=("Cantidad", "sum"), ventas_netas=("Precio neto total", "sum"))
            .reset_index()
            .sort_values("ventas_netas", ascending=False)
            .head(8)
        )
        productos_por_categoria[cat] = [
            {"nombre": r["referencia"], "unidades": int(r["unidades"]), "ventas_netas": round(float(r["ventas_netas"]), 2)}
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
                "nombre": r["referencia"],
                "unidades": int(r["unidades"]),
                "ventas_netas": round(float(r["ventas_netas"]), 2),
            }
            for _, r in referencias.iterrows()
        ],
        "top_referencias_por_sucursal": por_sucursal_ref,
        "productos_por_categoria": productos_por_categoria,
    }


def main():
    df = cargar_conceptos_combinados()
    df["Fecha creación"] = pd.to_datetime(df["Fecha creación"])
    validas = df[df["Estado CXC"] == "Pago total"].copy()
    anio_actual = validas[validas["Fecha creación"] >= INICIO_ANIO]
    mes_actual = validas[validas["Fecha creación"] >= INICIO_MES]

    sucursales_cfg = cargar_config("sucursales.json")["sucursales"]
    nombre_map = {s["nombre_effi"]: s["nombre"] for s in sucursales_cfg}

    salida = {
        "anio_actual": _resumen(anio_actual, nombre_map),
        "mes_actual": {"unidades_totales": int(mes_actual["Cantidad"].sum())},
        "historico": _resumen(validas, nombre_map),
    }

    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Año actual: {len(salida['anio_actual']['categorias'])} categorías, "
          f"{len(salida['anio_actual']['top_referencias'])} referencias, "
          f"{salida['anio_actual']['unidades_totales']} unidades")
    print(f"Mes actual: {salida['mes_actual']['unidades_totales']} unidades")
    print(f"Histórico: {len(salida['historico']['categorias'])} categorías, "
          f"{len(salida['historico']['top_referencias'])} referencias")
    print(f"Guardado en {OUT}")


if __name__ == "__main__":
    main()
