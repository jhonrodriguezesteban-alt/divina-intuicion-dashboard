"""
Descarga TODAS las facturas de venta desde 2025-01-01 hasta hoy (nivel
documento, una fila por factura) -- análogo a descargar_remisiones_completas.py.

Por qué existe este módulo aparte de Remisiones: cuando una venta necesita
factura formal (cliente con NIT/CUFE DIAN), el flujo en Effi es crear
primero la remisión y luego convertirla en factura -- Effi anula
automáticamente la remisión original al hacerlo. Esa remisión Anulada ya
se excluye del cálculo de ventas (correcto), pero la factura resultante
nunca se estaba descargando, así que esa venta no se contaba en ningún
lado. Se corrige agregando esta fuente y sumándola (Estado CXC != Anulado)
junto con remisiones -- sin riesgo de doble conteo porque la remisión que
originó la factura siempre queda Anulada.

Exportación con el flujo nuevo de Effi (modal de columnas + archivo en
segundo plano) -- ver common.effi_client.exportar_excel.
"""

import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto, exportar_excel

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
DESDE = "2025-01-01 00:00:00"
HASTA = datetime.now().strftime("%Y-%m-%d 23:59:59")

COLUMNAS = [
    "Sucursal", "ID interno", "CUFE", "Cliente", "Total neto", "Costo manual",
    "Utilidad (costo manual)", "Margen de utilidad (costo manual)",
    "Estado CXC", "Fecha de creación", "Observación de anulación",
    "Fecha de anulación", "Relación de despacho",
]


def main():
    url = f"https://effi.com.co/app/factura_v?desde={DESDE.replace(' ', '%20')}&hasta={HASTA.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)
        try:
            exportar_excel(page, context, url, COLUMNAS, RAW_DIR / "raw_facturas_completo.xlsx", "Reporte de Facturas de venta")
        except Exception as e:
            print(f"ERROR descargando facturas: {e}")
            browser.close()
            sys.exit(1)
        browser.close()


if __name__ == "__main__":
    main()
