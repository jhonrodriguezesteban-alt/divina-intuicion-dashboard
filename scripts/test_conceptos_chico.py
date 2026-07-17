from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH
from common.export_async import exportar_con_fallback_async

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
CAMPOS = ["c1", "c22", "c25", "c47", "c51", "c52", "c57", "c60", "c61", "c69", "c70"]


def main():
    url = "https://effi.com.co/app/remision_v?desde=2026-07-01%2000:00:00&hasta=2026-07-16%2023:59:59"
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

        ruta = RAW_DIR / "raw_conceptos_test.xlsx"
        resultado = exportar_con_fallback_async(
            context, page,
            boton_selector="#btnValidarExcelConceptos",
            prefijo_notificacion="Reporte:",
            ruta_destino=ruta,
            timeout_directo_ms=25_000,
            max_espera_segundos=180,
        )
        print(f"Resultado: {resultado}")
        browser.close()


if __name__ == "__main__":
    main()
