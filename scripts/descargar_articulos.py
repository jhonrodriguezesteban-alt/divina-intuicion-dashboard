"""
El export de Artículos abre un modal "Seleccione las columnas que desea
exportar a Excel" (mismo patrón que "Reporte de conceptos" en la guía).
El link "Exportar a excel" solo abre el modal; el envío real se hace con
el botón #btnValidarExcel dentro de ese modal — ambos tienen el mismo
texto visible, por eso un selector por texto ambiguo dispara el link
equivocado.

Para catálogos grandes (2800+ items) el archivo se genera en segundo
plano y aparece como link en el centro de notificaciones
(https://effi.com.co/public/temp/reportes_excel/...) en vez de disparar
un download inmediato del navegador — este script cubre ambos casos.
"""

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
URL_ARTICULOS = "https://effi.com.co/app/articulo"
POLL_SEGUNDOS = 15
MAX_ESPERA_SEGUNDOS = 300


def _links_reporte_articulos(page):
    return page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => ({texto: e.innerText.trim(), href: e.href}))"
        ".filter(x => x.texto.startsWith('Reporte: Artículos'))"
    )


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH), accept_downloads=True)
        page = context.new_page()

        page.goto(URL_ARTICULOS, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        antes = {l["href"] for l in _links_reporte_articulos(page)}

        page.locator("a.bg-green-active:has-text('Exportar a excel')").first.click()
        page.locator("#btnValidarExcel").wait_for(state="visible", timeout=15_000)

        ruta = RAW_DIR / "raw_articulos.xlsx"
        try:
            with page.expect_download(timeout=25_000) as dl_info:
                page.locator("#btnValidarExcel").click()
            dl_info.value.save_as(str(ruta))
            print(f"Descarga directa OK: {ruta}")
            browser.close()
            return
        except Exception:
            print("No hubo download directo (probablemente async por catálogo grande). Sondeando notificaciones...")

        esperado = 0
        nuevo_link = None
        while esperado < MAX_ESPERA_SEGUNDOS:
            page.wait_for_timeout(POLL_SEGUNDOS * 1000)
            esperado += POLL_SEGUNDOS
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            actuales = _links_reporte_articulos(page)
            nuevos = [l for l in actuales if l["href"] not in antes]
            if nuevos:
                nuevo_link = nuevos[0]
                break
            print(f"  ...{esperado}s, aún no aparece el reporte nuevo")

        if not nuevo_link:
            print("No apareció el reporte a tiempo. Revisar manualmente el centro de notificaciones en Effi.")
            browser.close()
            return

        print(f"Reporte listo: {nuevo_link['texto']}")
        resp = context.request.get(nuevo_link["href"])
        ruta.write_bytes(resp.body())
        print(f"Descargado en {ruta} ({len(resp.body())} bytes)")
        browser.close()


if __name__ == "__main__":
    main()
