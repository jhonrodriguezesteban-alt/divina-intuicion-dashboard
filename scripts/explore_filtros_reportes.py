"""
Diagnóstico: revisa el panel de "Filtros de búsqueda" de remision_v (para
confirmar cómo filtrar por rango de fechas completo) y el flujo "Reportes
y análisis de datos" (para ver si hay un reporte a nivel de línea/artículo,
necesario para rentabilidad por categoría y top referencias).
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

OUT_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH))
        page = context.new_page()

        # 1. Filtros de búsqueda en remision_v
        page.goto("https://effi.com.co/app/remision_v", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.locator("text=Filtros de búsqueda").first.click()
        page.wait_for_timeout(2000)
        page.screenshot(path=str(OUT_DIR / "_debug_filtros.png"))
        (OUT_DIR / "_debug_filtros.html").write_text(page.content(), encoding="utf-8")
        campos = page.eval_on_selector_all(
            "input, select",
            "els => els.map(e => ({tag: e.tagName, type: e.type, name: e.name, id: e.id, placeholder: e.placeholder}))"
        )
        print("Campos de filtro encontrados:", campos)

        # 2. Reportes y análisis de datos
        page.goto("https://effi.com.co/app/remision_v", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.locator("text=Reportes y análisis de datos").first.click()
        page.wait_for_timeout(3000)
        page.screenshot(path=str(OUT_DIR / "_debug_reportes_analisis.png"))
        (OUT_DIR / "_debug_reportes_analisis.html").write_text(page.content(), encoding="utf-8")
        print("URL tras clic en Reportes y análisis de datos:", page.url)

        browser.close()


if __name__ == "__main__":
    main()
