"""
Genera un resumen de texto del cierre del día a partir de
reportes/ventas_procesado.json (ya actualizado) y reportes/reorden.json.
Se guarda con fecha en reportes/resumenes/ y también en
reportes/resumen_dia.txt (el más reciente), para consulta rápida.
"""

import json
from datetime import datetime
from pathlib import Path

REPORTES_DIR = Path(__file__).resolve().parent.parent / "reportes"
RESUMENES_DIR = REPORTES_DIR / "resumenes"


def _cargar(nombre):
    ruta = REPORTES_DIR / nombre
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def _cop(v):
    return "$" + f"{round(v):,}".replace(",", ".")


def generar_texto() -> str:
    ventas = _cargar("ventas_procesado.json")
    reorden = _cargar("reorden.json")

    if not ventas:
        return "Sin datos de ventas procesados — no se pudo generar el resumen del cierre."

    hoy = ventas["hoy"]
    k = hoy["kpis"]
    ayer = hoy["ingreso_ayer"]
    variacion = f"{round((k['ingreso_total'] - ayer) / ayer * 100, 1)}%" if ayer else "s/d"

    mes = ventas["mes_actual"]["kpis"]
    anio = ventas["anio_actual"]["kpis"]

    lineas = [
        f"CIERRE DEL DÍA — Divina Intuición",
        f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        f"Venta de hoy: {_cop(k['ingreso_total'])} ({k['num_transacciones']} ventas) · vs ayer: {variacion}",
    ]
    for r in sorted(hoy["por_sucursal"], key=lambda x: -x["ingreso"]):
        lineas.append(f"  - {r['sucursal']}: {_cop(r['ingreso'])} ({r['transacciones']} ventas)")

    lineas += [
        "",
        f"Mes en curso: {_cop(mes['ingreso_total'])} · {mes['num_transacciones']} ventas · margen {round(mes['margen_promedio']*100,1)}%",
        f"Año en curso: {_cop(anio['ingreso_total'])} · {anio['num_transacciones']} ventas · margen {round(anio['margen_promedio']*100,1)}%",
    ]

    if reorden:
        r = reorden["resumen"]
        lineas += [
            "",
            "Inventario / pedidos a proveedores:",
            f"  - Referencias críticas: {r['criticos']} · en alerta: {r['alerta']}",
            f"  - Unidades sugeridas a pedir: {r['unidades_sugeridas_total']}",
        ]

    lineas.append("")
    lineas.append("Dashboard: revisa el link publicado en GitHub Pages para el detalle completo.")
    return "\n".join(lineas)


def main():
    texto = generar_texto()
    RESUMENES_DIR.mkdir(parents=True, exist_ok=True)
    fecha = datetime.now().strftime("%Y-%m-%d")
    (RESUMENES_DIR / f"{fecha}.txt").write_text(texto, encoding="utf-8")
    (REPORTES_DIR / "resumen_dia.txt").write_text(texto, encoding="utf-8")
    print(texto)


if __name__ == "__main__":
    main()
