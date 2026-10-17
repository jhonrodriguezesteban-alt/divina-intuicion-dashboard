"""
Descarga TODAS las remisiones de venta desde 2025-01-01 hasta hoy (nivel
documento, una fila por remisión).

Desde ~15-oct-2026 Effi ya no descarga directo: "Exportar a excel" abre un
modal de selección de columnas y genera el archivo en segundo plano (llega
como enlace al centro de notificaciones) -- todo eso lo maneja
common.effi_client.exportar_excel. Solo se piden las columnas que usa el
pipeline (antes bajaban ~70 columnas y el archivo pesaba ~60 MB).
"""

import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto, exportar_excel

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
DESDE = "2025-01-01 00:00:00"
HASTA = datetime.now().strftime("%Y-%m-%d 23:59:59")

# Usadas por procesar_ventas.py, procesar_ventas_diarias.py,
# procesar_historico_mensual.py y mapa_fecha_original_facturas()
# (Observación de anulación = rastro de "Remisión convertida a factura #ID").
COLUMNAS = [
    "Sucursal", "ID remisión", "Cliente", "Total neto", "Costo manual",
    "Utilidad (costo manual)", "Margen de utilidad (costo manual)",
    "Estado CXC", "Estado remisión", "Fecha de creación",
    "Observación de anulación", "Fecha de anulación",
]


def main():
    url = f"https://effi.com.co/app/remision_v?desde={DESDE.replace(' ', '%20')}&hasta={HASTA.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)
        try:
            exportar_excel(page, context, url, COLUMNAS, RAW_DIR / "raw_remisiones_completo.xlsx", "Reporte de Notas de remisión de venta")
        except Exception as e:
            print(f"ERROR descargando remisiones: {e}")
            browser.close()
            sys.exit(1)
        browser.close()


if __name__ == "__main__":
    main()
