from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
DESDE = "2025-01-01 00:00:00"
HASTA = datetime.now().strftime("%Y-%m-%d 23:59:59")


def main():
    url = f"https://effi.com.co/app/remision_v?desde={DESDE.replace(' ', '%20')}&hasta={HASTA.replace(' ', '%20')}"
    print("URL:", url)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH), accept_downloads=True)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        page.screenshot(path=str(RAW_DIR / "_debug_remisiones_grandes.png"), full_page=True)
        texto = page.inner_text("body")
        (RAW_DIR / "_debug_remisiones_grandes.txt").write_text(texto, encoding="utf-8")
        print("Primeras líneas del body:")
        print("\n".join(texto.splitlines()[:15]))
        browser.close()


if __name__ == "__main__":
    main()
