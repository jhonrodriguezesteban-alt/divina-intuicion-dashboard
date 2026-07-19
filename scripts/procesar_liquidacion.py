"""
Analiza qué referencias de ROPA están rotando este año vs cuáles no --
para identificar candidatas a liquidar. Los accesorios no entran aquí por
referencia (ver config/categorias_accesorios.json): tienen demasiada
variedad de SKU, se analizan por categoría en procesar_reorden.py.

Tres grupos, no dos, para no arriesgar marcar mercancía recién comprada
como "liquidar" solo porque todavía no se ha vendido:
- Activa: se vendió al menos una vez este año.
- Inactiva: se vendió antes (histórico), pero nada este año -- candidata
  real a liquidar.
- Nueva / nunca vendida: sin ninguna venta histórica -- podría ser
  referencia reciente que aún no ha tenido tiempo de rotar. Requiere
  evaluación manual, no se asume liquidación automática.
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_conceptos_combinados, cargar_config, referencia_base

RAW_ARTICULOS = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_articulos.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "liquidacion.json"

HOY = pd.Timestamp.now().normalize()
INICIO_ANIO = pd.Timestamp(year=HOY.year, month=1, day=1)


def main():
    categorias_accesorios = set(cargar_config("categorias_accesorios.json")["categorias"])

    articulos = leer_excel_effi(RAW_ARTICULOS)
    articulos["Stock total empresa"] = pd.to_numeric(articulos["Stock total empresa"], errors="coerce").fillna(0)
    articulos["Costo manual"] = pd.to_numeric(articulos["Costo manual"], errors="coerce").fillna(0)
    articulos["Categoría"] = articulos["Categoría"].fillna("SIN CATEGORÍA")
    articulos["referencia"] = articulos["Nombre"].apply(referencia_base)
    articulos["valor_costo"] = articulos["Costo manual"] * articulos["Stock total empresa"]

    ropa = articulos[~articulos["Categoría"].isin(categorias_accesorios)]
    con_stock = ropa[ropa["Stock total empresa"] > 0].copy()

    conceptos = cargar_conceptos_combinados()
    conceptos["Fecha creación"] = pd.to_datetime(conceptos["Fecha creación"])
    validas = conceptos[conceptos["Estado CXC"] == "Pago total"].copy()
    validas["referencia"] = validas["Descripción artículo"].apply(referencia_base)

    ref_venta_anio = set(validas[validas["Fecha creación"] >= INICIO_ANIO]["referencia"].unique())
    ref_venta_historico = set(validas["referencia"].unique())

    con_stock["activo_anio"] = con_stock["referencia"].isin(ref_venta_anio)
    con_stock["vendido_historico"] = con_stock["referencia"].isin(ref_venta_historico)

    resumen = (
        con_stock.groupby("referencia")
        .agg(
            disponible=("Stock total empresa", "sum"),
            valor_costo=("valor_costo", "sum"),
            activo=("activo_anio", "max"),
            vendido_historico=("vendido_historico", "max"),
            categoria=("Categoría", "first"),
        )
        .reset_index()
    )

    def _grupo(r):
        if r["activo"]:
            return "activa"
        if r["vendido_historico"]:
            return "inactiva"
        return "nueva"

    resumen["grupo"] = resumen.apply(_grupo, axis=1)

    def _lista(grupo):
        sub = resumen[resumen["grupo"] == grupo].sort_values("valor_costo", ascending=False)
        return [
            {
                "referencia": r["referencia"],
                "categoria": r["categoria"],
                "disponible": int(r["disponible"]),
                "valor_costo": round(float(r["valor_costo"]), 2),
            }
            for _, r in sub.iterrows()
        ]

    def _resumen_grupo(grupo):
        sub = resumen[resumen["grupo"] == grupo]
        return {
            "num_referencias": int(len(sub)),
            "unidades": int(sub["disponible"].sum()),
            "valor_costo": round(float(sub["valor_costo"].sum()), 2),
        }

    salida = {
        "generado_al": str(HOY.date()),
        "anio": HOY.year,
        "resumen": {
            "activas": _resumen_grupo("activa"),
            "inactivas": _resumen_grupo("inactiva"),
            "nuevas": _resumen_grupo("nueva"),
        },
        "inactivas": _lista("inactiva"),
        "nuevas": _lista("nueva"),
    }

    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(salida["resumen"], ensure_ascii=False, indent=2))
    print(f"Guardado en {OUT}")


if __name__ == "__main__":
    main()
