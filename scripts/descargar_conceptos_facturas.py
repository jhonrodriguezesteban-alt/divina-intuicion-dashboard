"""
Descarga el "Reporte de conceptos" de Facturas de venta (detalle por
línea/artículo dentro de cada factura) para todo el histórico --
analógico a descargar_conceptos.py, pero para el módulo de facturas.

A diferencia del de remisiones, este botón dispara la descarga directa al
click (no abre un modal de "seleccione las columnas" primero) -- ya trae
por defecto las columnas necesarias (Categoría artículo, Cod./Descripción
artículo, Cantidad, costos, precio neto, utilidad).

Necesario para que Top Referencias, Rentabilidad por categoría y Reorden
también reflejen lo vendido por factura, no solo por remisión (ver nota
en descargar_facturas_completas.py).
"""

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
DESDE = "2025-01-01 00:00:00"
HASTA = datetime.now().strftime("%Y-%m-%d 23:59:59")


def main():
    url = f"https://effi.com.co/app/factura_v?desde={DESDE.replace(' ', '%20')}&hasta={HASTA.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        page.locator("a:has-text('Reportes y análisis de datos')").last.click()
        page.wait_for_timeout(1500)

        ruta = RAW_DIR / "raw_conceptos_facturas.xlsx"
        print("Enviando export de conceptos de facturas...")
        with page.expect_download(timeout=300_000) as dl_info:
            page.locator("text=Reporte de conceptos").first.click(force=True)
        dl_info.value.save_as(str(ruta))
        print(f"Descargado en {ruta}")
        browser.close()


if __name__ == "__main__":
    main()
