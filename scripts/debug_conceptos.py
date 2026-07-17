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
        page.wait_for_timeout(1000)

        page.screenshot(path=str(RAW_DIR / "_debug_conceptos_antes.png"), full_page=True)

        page.locator("text=Desmarcar todo").first.click()
        page.wait_for_timeout(500)
        page.screenshot(path=str(RAW_DIR / "_debug_conceptos_desmarcado.png"), full_page=True)

        for c in CAMPOS:
            loc = page.locator(f"input[type='checkbox'][value='{c}']").first
            loc.check(force=True)
            estado = loc.is_checked()
            print(f"{c}: checked={estado}")

        page.wait_for_timeout(500)
        page.screenshot(path=str(RAW_DIR / "_debug_conceptos_marcado.png"), full_page=True)

        # click y observar qué pasa (sin esperar download largo)
        page.locator("#btnValidarExcelConceptos").click()
        page.wait_for_timeout(5000)
        page.screenshot(path=str(RAW_DIR / "_debug_conceptos_post_click.png"), full_page=True)
        (RAW_DIR / "_debug_conceptos_post_click.html").write_text(page.content(), encoding="utf-8")
        print("URL tras click:", page.url)

        browser.close()


if __name__ == "__main__":
    main()
