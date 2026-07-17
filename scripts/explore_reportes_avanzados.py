from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

OUT_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH))
        page = context.new_page()

        page.goto("https://effi.com.co/app/remision_v", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.locator("text=Reportes y análisis de datos").first.click()
        page.wait_for_timeout(1500)

        # Reporte de conceptos
        page.locator("text=Reporte de conceptos").first.click()
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT_DIR / "_debug_reporte_conceptos.png"), full_page=True)
        (OUT_DIR / "_debug_reporte_conceptos.html").write_text(page.content(), encoding="utf-8")
        print("Reporte de conceptos: screenshot guardado")

        browser.close()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH))
        page = context.new_page()
        page.goto("https://effi.com.co/app/remision_v", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.locator("text=Reportes y análisis de datos").first.click()
        page.wait_for_timeout(1500)

        # Remisiones de venta mensuales
        page.locator("text=Remisiones de venta mensuales").first.click()
        page.wait_for_timeout(2500)
        page.screenshot(path=str(OUT_DIR / "_debug_remisiones_mensuales.png"), full_page=True)
        (OUT_DIR / "_debug_remisiones_mensuales.html").write_text(page.content(), encoding="utf-8")
        print("Remisiones de venta mensuales: screenshot guardado. URL:", page.url)

        browser.close()


if __name__ == "__main__":
    main()
