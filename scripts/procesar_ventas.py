"""
Procesa reportes/raw/raw_remisiones_completo.xlsx + raw_facturas_completo.xlsx
-> reportes/ventas_procesado.json

Regla de negocio (JR ARQUITECTURA_REPLICABLE.md 5.3): el ingreso real se
mide por documentos con Estado CXC = "Pago total". Se excluyen anuladas.

Por qué dos fuentes: cuando una venta necesita factura formal (cliente con
NIT/CUFE), el flujo en Effi es crear la remisión y luego convertirla en
factura -- Effi anula automáticamente la remisión original al hacerlo. Esa
remisión Anulada ya se excluye (correcto), pero si solo se lee remisiones,
la factura resultante nunca se cuenta en ningún lado. Se suman ambas
fuentes sin riesgo de doble conteo porque la remisión que originó una
factura siempre queda Anulada -- verificado contra el histórico real
(117 de 125 facturas no anuladas tienen una remisión Anulada exacta del
mismo cliente y monto).

"Composición de venta" (Facturado vs Remisionado) usa exactamente esta
distinción de fuente -- reemplaza la versión anterior (Cobrado vs
Pendiente de cobro), que era una aproximación mientras no se sabía que
"Facturas de venta" era un módulo aparte en Effi.

Genera: KPIs de todo el histórico, del año en curso, del mes en curso, de
hoy (con comparación vs ayer), y ventas por sucursal en cada uno de esos
cortes — estructura equivalente al dashboard de referencia de Grupo Bentley.
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_config

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
RAW_REMISIONES = RAW_DIR / "raw_remisiones_completo.xlsx"
RAW_FACTURAS = RAW_DIR / "raw_facturas_completo.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "ventas_procesado.json"

HOY = pd.Timestamp.now().normalize()
AYER = HOY - pd.Timedelta(days=1)
INICIO_ANIO = pd.Timestamp(year=HOY.year, month=1, day=1)
INICIO_MES = pd.Timestamp(year=HOY.year, month=HOY.month, day=1)


def _cargar_documentos() -> pd.DataFrame:
    remisiones = leer_excel_effi(RAW_REMISIONES)
    remisiones["Fecha de creación"] = pd.to_datetime(remisiones["Fecha de creación"])
    remisiones["fuente"] = "remision"
    marcos = [remisiones]

    if RAW_FACTURAS.exists():
        facturas = leer_excel_effi(RAW_FACTURAS)
        facturas["Fecha de creación"] = pd.to_datetime(facturas["Fecha de creación"])
        facturas["fuente"] = "factura"
        marcos.append(facturas)

    return pd.concat(marcos, ignore_index=True)


def _kpis(df: pd.DataFrame) -> dict:
    if not len(df):
        return {"ingreso_total": 0, "num_transacciones": 0, "ticket_promedio": 0,
                "utilidad_total": 0, "margen_promedio": 0}
    return {
        "ingreso_total": round(float(df["Total neto"].sum()), 2),
        "num_transacciones": int(len(df)),
        "ticket_promedio": round(float(df["Total neto"].mean()), 2),
        "utilidad_total": round(float(df["Utilidad (costo manual)"].sum()), 2),
        "margen_promedio": round(float(df["Margen de utilidad (costo manual)"].mean()), 4),
    }


def _por_sucursal(df: pd.DataFrame, nombre_map: dict) -> list:
    if not len(df):
        return []
    agg = (
        df.groupby("Sucursal")
        .agg(ingreso=("Total neto", "sum"), transacciones=("Total neto", "count"))
        .reset_index()
        .sort_values("ingreso", ascending=False)
    )
    return [
        {"sucursal": nombre_map.get(r["Sucursal"], r["Sucursal"]), "ingreso": round(float(r["ingreso"]), 2),
         "transacciones": int(r["transacciones"])}
        for _, r in agg.iterrows()
    ]


def main():
    df_full = _cargar_documentos()
    df_full["dia"] = df_full["Fecha de creación"].dt.date

    sucursales_cfg = cargar_config("sucursales.json")["sucursales"]
    nombre_map = {s["nombre_effi"]: s["nombre"] for s in sucursales_cfg}

    validas = df_full[df_full["Estado CXC"] == "Pago total"].copy()
    anuladas = df_full[df_full["Estado CXC"] == "Anulado"]
    pendientes_cobro_todas = df_full[df_full["Estado CXC"] == "Pendiente de cobro al día"]

    historico = validas
    anio_actual = validas[validas["Fecha de creación"] >= INICIO_ANIO]
    mes_actual = validas[validas["Fecha de creación"] >= INICIO_MES]
    hoy = validas[validas["dia"] == HOY.date()]
    ayer = validas[validas["dia"] == AYER.date()]

    facturado_anio = anio_actual[anio_actual["fuente"] == "factura"]
    remisionado_anio = anio_actual[anio_actual["fuente"] == "remision"]
    composicion_anio = {
        "facturado": round(float(facturado_anio["Total neto"].sum()), 2),
        "remisionado": round(float(remisionado_anio["Total neto"].sum()), 2),
        "num_facturado": int(len(facturado_anio)),
        "num_remisionado": int(len(remisionado_anio)),
    }

    salida = {
        "actualizado_hasta": str(df_full["Fecha de creación"].max()),
        "historico": {
            "kpis": _kpis(historico),
            "por_sucursal": _por_sucursal(historico, nombre_map),
            "rango_fechas": {"desde": str(df_full["Fecha de creación"].min().date()), "hasta": str(HOY.date())},
        },
        "anio_actual": {
            "kpis": _kpis(anio_actual),
            "por_sucursal": _por_sucursal(anio_actual, nombre_map),
            "composicion": composicion_anio,
        },
        "mes_actual": {
            "kpis": _kpis(mes_actual),
            "por_sucursal": _por_sucursal(mes_actual, nombre_map),
        },
        "hoy": {
            "kpis": _kpis(hoy),
            "por_sucursal": _por_sucursal(hoy, nombre_map),
            "ingreso_ayer": round(float(ayer["Total neto"].sum()), 2),
        },
        "cartera": {
            "num_anuladas_historico": int(len(anuladas)),
            "pendiente_de_cobro": round(float(pendientes_cobro_todas["Total neto"].sum()), 2),
            "num_pendiente_de_cobro": int(len(pendientes_cobro_todas)),
        },
    }

    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in salida.items() if k != "historico"}, ensure_ascii=False, indent=2))
    print(f"\nGuardado en {OUT}")


if __name__ == "__main__":
    main()
