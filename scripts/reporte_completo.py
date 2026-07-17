"""
Corrida completa (manual, 1 vez por semana/mes): login completo a Effi,
descarga TODO lo definido en config/sucursales.json + módulos activos,
genera el HTML completo y publica.

Único script (junto con actualizar_dashboard.py) autorizado a publicar en GitHub Pages.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto, navegar_y_descargar
from generar_dashboard import generar_dashboard_html, publicar

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"


def main():
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)
        try:
            # TODO: recorrer módulos activos (Remisiones/Facturas, Inventario) por cada
            # sucursal en config/sucursales.json y descargar con navegar_y_descargar().
            pass
        finally:
            browser.close()

    html = generar_dashboard_html({})
    publicar(html)

    # TODO: git add/commit/push del dashboard.html (+ sec_*.html si aplica) a GitHub Pages.
    # Se agrega explícitamente cuando el repo remoto esté creado y confirmado.


if __name__ == "__main__":
    main()
