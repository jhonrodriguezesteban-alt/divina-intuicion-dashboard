"""
Primera descarga real de datos para construir la v1 del dashboard:
- Remisiones de venta (ventana visible por defecto de Effi)
- Artículos / Inventario

Usa el botón directo "Exportar a excel" de cada listado (no el flujo
avanzado de "Reporte de conceptos" con selección de columnas — ese se
usa más adelante cuando necesitemos columnas específicas no incluidas
por defecto).
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"

MODULOS = {
    "articulos": "https://effi.com.co/app/articulo",
}


def descargar(page, nombre, url):
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    with page.expect_download(timeout=280_000) as dl_info:
        page.locator("text=Exportar a excel").first.click()
    ruta = RAW_DIR / f"raw_{nombre}.xlsx"
    dl_info.value.save_as(str(ruta))
    print(f"{nombre}: descargado en {ruta}")
    return ruta


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH), accept_downloads=True)
        page = context.new_page()
        for nombre, url in MODULOS.items():
            try:
                descargar(page, nombre, url)
            except Exception as e:
                print(f"{nombre}: FALLÓ ({e})")
        browser.close()


if __name__ == "__main__":
    main()
