from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH))
        page = context.new_page()
        page.goto("https://effi.com.co/app/articulo", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        botones = page.eval_on_selector_all(
            "a, button",
            "els => els.filter(e => e.innerText && e.innerText.toLowerCase().includes('exportar'))"
            ".map(e => ({tag: e.tagName, texto: e.innerText.trim(), href: e.href || null, cls: e.className}))"
        )
        print("Botones/enlaces con 'exportar':", botones)

        page.locator("text=Exportar a excel").first.click()
        page.wait_for_timeout(4000)

        (RAW_DIR / "_debug_post_click.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(RAW_DIR / "_debug_post_click.png"), full_page=False)
        print("Screenshot y HTML guardados.")
        print("URL actual:", page.url)
        browser.close()


if __name__ == "__main__":
    main()
