from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

OUT = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "_sucursales.txt"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH))
        page = context.new_page()
        page.goto("https://effi.com.co/app/sucursal", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        texto = page.inner_text("body")
        OUT.write_text(texto, encoding="utf-8")
        print(f"Guardado en {OUT}")
        browser.close()


if __name__ == "__main__":
    main()
