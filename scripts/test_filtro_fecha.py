from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

OUT_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH))
        page = context.new_page()

        url = "https://effi.com.co/app/remision_v?desde=2025-01-01%2000:00:00&hasta=2026-07-16%2023:59:59"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        texto = page.inner_text("body")
        resumen = next((l for l in texto.splitlines() if "resultado" in l.lower() or "encontrad" in l.lower() or "visualizan" in l.lower()), "sin resumen")
        print("Resumen tras querystring desde/hasta:", resumen)

        # también probar aplicando el filtro manualmente vía el input
        page.goto("https://effi.com.co/app/remision_v", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.locator("text=Filtros de búsqueda").first.click()
        page.wait_for_timeout(1500)
        page.fill("#desde", "2025-01-01 00:00:00")
        page.fill("#hasta", "2026-07-16 23:59:59")
        page.keyboard.press("Escape")  # cerrar datepicker si aparece
        page.locator("button:has-text('Aplicar filtros')").first.click()
        page.wait_for_timeout(4000)
        texto2 = page.inner_text("body")
        resumen2 = next((l for l in texto2.splitlines() if "resultado" in l.lower() or "encontrad" in l.lower() or "visualizan" in l.lower()), "sin resumen")
        print("Resumen tras llenar campos + Aplicar filtros:", resumen2)
        print("URL final:", page.url)

        browser.close()


if __name__ == "__main__":
    main()
