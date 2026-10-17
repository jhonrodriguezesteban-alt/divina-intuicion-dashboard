"""
Descarga el "Reporte de conceptos" de Facturas de venta (detalle por
línea/artículo) para todo el histórico -> reportes/raw/raw_conceptos_facturas.xlsx.
cargar_conceptos_combinados() lo une con el de remisiones (y le trae el
Estado CXC desde raw_facturas_completo.xlsx por "ID interno").

Flujo nuevo de Effi (~15-oct-2026): modal de columnas #modalExcel_EXCEL1 +
archivo en segundo plano -- ver common.effi_client.
"""

import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto, exportar_excel_pagina_actual

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
DESDE = "2025-01-01 00:00:00"
HASTA = datetime.now().strftime("%Y-%m-%d 23:59:59")

COLUMNAS = [
    "Sucursal", "ID interno", "Vigencia factura", "Fecha creación factura",
    "Categoría artículo", "Cod. artículo", "Descripción artículo", "Cantidad",
    "Costo manual unitario", "Costo manual total", "Precio neto total",
    "Utilidad total (costo manual)",
]


def main():
    url = f"https://effi.com.co/app/factura_v?desde={DESDE.replace(' ', '%20')}&hasta={HASTA.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=120_000)
            page.wait_for_timeout(4000)
            page.locator("a:has-text('Reportes y análisis de datos')").last.click()
            page.wait_for_timeout(1500)
            exportar_excel_pagina_actual(
                page, context, COLUMNAS, RAW_DIR / "raw_conceptos_facturas.xlsx",
                "Reporte de conceptos de Facturas de venta",
                boton_abrir="#toExcel_EXCEL1", boton_confirmar="#btnValidarExcel_EXCEL1",
            )
        except Exception as e:
            print(f"ERROR descargando conceptos de facturas: {e}")
            browser.close()
            sys.exit(1)
        browser.close()


if __name__ == "__main__":
    main()
