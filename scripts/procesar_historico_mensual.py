"""
Procesa reportes/raw/raw_mensual_{codigo}.xlsx (remisiones, uno por
sucursal) + raw_facturas_completo.xlsx -> reportes/historico_mensual.json
— comparativo mes a mes, año actual vs año anterior, por sucursal (igual
estructura que el comparativo histórico del dashboard de referencia de
Grupo Bentley).

Las facturas se agregan por mes acá mismo (no con el reporte mensual de
Effi para facturas, que tiene un bug confirmado: sigue incluyendo
documentos Anulados aunque se filtre por Estado CXC = Pago total). Ver
la nota en procesar_ventas.py sobre por qué sumar remisiones + facturas
no duplica ninguna venta.
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_config

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
RAW_FACTURAS = RAW_DIR / "raw_facturas_completo.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "historico_mensual.json"

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _facturas_por_sucursal_mes(nombre_effi_a_codigo: dict) -> dict:
    """{codigo: {anio: {MesEs: {neto, cantidad, utilidad}}}}, solo Pago total."""
    if not RAW_FACTURAS.exists():
        return {}
    df = leer_excel_effi(RAW_FACTURAS)
    df = df[df["Estado CXC"] == "Pago total"].copy()
    if not len(df):
        return {}
    df["Fecha de creación"] = pd.to_datetime(df["Fecha de creación"])
    df["anio"] = df["Fecha de creación"].dt.year.astype(str)
    df["mes_idx"] = df["Fecha de creación"].dt.month - 1

    resultado = {}
    for (sucursal_effi, anio, mes_idx), grupo in df.groupby(["Sucursal", "anio", "mes_idx"]):
        codigo = nombre_effi_a_codigo.get(sucursal_effi)
        if not codigo:
            continue
        resultado.setdefault(codigo, {}).setdefault(anio, {})[MESES_ES[mes_idx]] = {
            "neto": round(float(grupo["Total neto"].sum()), 2),
            "cantidad": int(len(grupo)),
            "utilidad": round(float(grupo["Utilidad (costo manual)"].sum()), 2),
        }
    return resultado


def _sumar_mes(actual, factura: dict) -> dict:
    if not actual:
        neto, cantidad, utilidad = factura["neto"], factura["cantidad"], factura["utilidad"]
    else:
        neto = actual["neto"] + factura["neto"]
        cantidad = actual["cantidad"] + factura["cantidad"]
        utilidad = actual["utilidad"] + factura["utilidad"]
    return {
        "neto": round(neto, 2),
        "cantidad": cantidad,
        "utilidad": round(utilidad, 2),
        "margen": round(utilidad / neto, 4) if neto else 0,
    }


def main():
    sucursales = cargar_config("sucursales.json")["sucursales"]
    nombre_effi_a_codigo = {s["nombre_effi"]: s["codigo"] for s in sucursales}
    facturas_por_suc = _facturas_por_sucursal_mes(nombre_effi_a_codigo)

    resultado = {}
    for s in sucursales:
        ruta = RAW_DIR / f"raw_mensual_{s['codigo']}.xlsx"
        por_anio_mes = {}
        if ruta.exists():
            df = leer_excel_effi(ruta)
            for _, row in df.iterrows():
                anio, mes = row["Fecha"].split("-")
                mes_idx = int(mes) - 1
                por_anio_mes.setdefault(anio, {})[MESES_ES[mes_idx]] = {
                    "neto": round(float(row["Total neto"]), 2),
                    "cantidad": int(row["Cantidad"]),
                    "utilidad": round(float(row["Utilidad costo manual"]), 2),
                    "margen": round(float(row["Margen de utilidad costo manual"]), 4),
                }

        for anio, meses in facturas_por_suc.get(s["codigo"], {}).items():
            for mes_es, datos_f in meses.items():
                bloque_anio = por_anio_mes.setdefault(anio, {})
                bloque_anio[mes_es] = _sumar_mes(bloque_anio.get(mes_es), datos_f)

        if not por_anio_mes:
            continue
        resultado[s["codigo"]] = {"nombre": s["nombre"], "por_anio_mes": por_anio_mes}

    OUT.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardado en {OUT}")
    for cod, data in resultado.items():
        anios = list(data["por_anio_mes"].keys())
        print(f"  {data['nombre']}: años {anios}")


if __name__ == "__main__":
    main()
