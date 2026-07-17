"""
Descarga el "Reporte de conceptos" (detalle por línea/artículo dentro de
cada remisión) para todo el histórico — necesario para Rentabilidad por
categoría y Top de referencias, que las remisiones a nivel documento no
traen.

A diferencia del catálogo de Artículos, este reporte SIEMPRE dispara un
download directo del navegador (no pasa por el centro de notificaciones)
— para 15 meses de historia simplemente tarda varios minutos, así que se
le da un timeout largo en vez de sondear notificaciones que nunca llegan.

Campos elegidos (ver reportes/raw/_debug_reporte_conceptos.html para el
mapeo completo value->label):
  c1  Sucursal            c47 Categoría artículo
  c22 Estado CXC          c51 Cod. artículo
  c25 Fecha creación      c52 Descripción artículo
                           c57 Cantidad
                           c60 Costo manual unitario
                           c61 Costo manual total
                           c69 Precio neto total
                           c70 Utilidad total (costo manual)
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
DESDE = "2025-01-01 00:00:00"
HASTA = "2026-07-16 23:59:59"

CAMPOS = ["c1", "c22", "c25", "c47", "c51", "c52", "c57", "c60", "c61", "c69", "c70"]


def main():
    url = f"https://effi.com.co/app/remision_v?desde={DESDE.replace(' ', '%20')}&hasta={HASTA.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH), accept_downloads=True)
        page = context.new_page()

        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        page.locator("text=Reportes y análisis de datos").first.click()
        page.wait_for_timeout(1500)
        page.locator("text=Reporte de conceptos").first.click()
        page.locator("#btnValidarExcelConceptos").wait_for(state="visible", timeout=15_000)

        page.locator("text=Desmarcar todo").first.click()
        page.wait_for_timeout(500)
        for c in CAMPOS:
            page.locator(f"input[type='checkbox'][value='{c}']").first.check(force=True)

        ruta = RAW_DIR / "raw_conceptos.xlsx"
        print("Enviando export, puede tardar varios minutos para 15 meses de historia...")
        with page.expect_download(timeout=900_000) as dl_info:
            page.locator("#btnValidarExcelConceptos").click()
        dl_info.value.save_as(str(ruta))
        print(f"Descargado en {ruta}")
        browser.close()


if __name__ == "__main__":
    main()
