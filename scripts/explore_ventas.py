from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

MODULOS = {
    "pos": "https://effi.com.co/app/pos",
    "factura_v": "https://effi.com.co/app/factura_v",
    "remision_v": "https://effi.com.co/app/remision_v",
    "articulo": "https://effi.com.co/app/articulo",
}

OUT_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH))
        page = context.new_page()
        for nombre, url in MODULOS.items():
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            texto = page.inner_text("body")
            out = OUT_DIR / f"_explore_{nombre}.txt"
            out.write_text(texto, encoding="utf-8")
            # primera línea con "resultados encontrados" para ver si hay data
            resumen = next((l for l in texto.splitlines() if "resultado" in l.lower()), "sin resumen de resultados")
            print(f"{nombre}: {resumen}  (guardado en {out.name})")
        browser.close()


if __name__ == "__main__":
    main()
