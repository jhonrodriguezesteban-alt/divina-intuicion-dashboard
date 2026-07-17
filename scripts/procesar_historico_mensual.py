"""
Procesa reportes/raw/raw_mensual_{codigo}.xlsx (uno por sucursal) ->
reportes/historico_mensual.json — comparativo mes a mes, año actual vs
año anterior, por sucursal (igual estructura que el comparativo histórico
del dashboard de referencia de Grupo Bentley).
"""

import json
from pathlib import Path

from common.procesamiento import leer_excel_effi, cargar_config

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "historico_mensual.json"

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def main():
    sucursales = cargar_config("sucursales.json")["sucursales"]

    resultado = {}
    for s in sucursales:
        ruta = RAW_DIR / f"raw_mensual_{s['codigo']}.xlsx"
        if not ruta.exists():
            continue
        df = leer_excel_effi(ruta)

        por_anio_mes = {}
        for _, row in df.iterrows():
            anio, mes = row["Fecha"].split("-")
            mes_idx = int(mes) - 1
            por_anio_mes.setdefault(anio, {})[MESES_ES[mes_idx]] = {
                "neto": round(float(row["Total neto"]), 2),
                "cantidad": int(row["Cantidad"]),
                "utilidad": round(float(row["Utilidad costo manual"]), 2),
                "margen": round(float(row["Margen de utilidad costo manual"]), 4),
            }

        resultado[s["codigo"]] = {
            "nombre": s["nombre"],
            "por_anio_mes": por_anio_mes,
        }

    OUT.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Guardado en {OUT}")
    for cod, data in resultado.items():
        anios = list(data["por_anio_mes"].keys())
        print(f"  {data['nombre']}: años {anios}")


if __name__ == "__main__":
    main()
