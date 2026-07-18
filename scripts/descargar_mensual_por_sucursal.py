"""
Descarga el "Reporte de remisiones de venta mensuales" filtrado por cada
sucursal (una corrida por sucursal, porque el reporte no desglosa por
sucursal en columnas — solo agrega por mes). Rango: todo el histórico
disponible hasta hoy.
"""

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto
from common.procesamiento import cargar_config

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
URL = "https://effi.com.co/app/remision_v/reporte_mensual"
DESDE = "2025-01-01 00:00:00"
HASTA = datetime.now().strftime("%Y-%m-%d 23:59:59")


def _select_por_texto(page, selector_css: str, texto_opcion: str):
    """Los <select> de Effi usan el plugin Chosen (oculta el select nativo),
    así que Playwright no puede usar select_option normalmente. Se fija el
    valor por JS sobre el select que contenga la opción buscada y se dispara
    'change' para que Chosen y los listeners de Effi se enteren."""
    ok = page.evaluate(
        """([selectorCss, texto]) => {
            const selects = Array.from(document.querySelectorAll(selectorCss || 'select'));
            for (const sel of selects) {
                const opt = Array.from(sel.options).find(o => o.text.trim() === texto || o.text.trim().includes(texto));
                if (opt) {
                    sel.value = opt.value;
                    sel.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }
            }
            return false;
        }""",
        [selector_css, texto_opcion],
    )
    if not ok:
        raise RuntimeError(f"No se encontró opción '{texto_opcion}' en selects '{selector_css}'")


def main():
    sucursales = cargar_config("sucursales.json")["sucursales"]

    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)

        for s in sucursales:
            page.goto(URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2500)

            _select_por_texto(page, "#sucursal", s["nombre_effi"])
            page.fill("#desde", DESDE)
            page.fill("#hasta", HASTA)
            _select_por_texto(page, "select", "Pago total")
            page.keyboard.press("Escape")
            page.locator("button:has-text('Aplicar filtros')").first.click()
            page.wait_for_timeout(3000)

            texto = page.inner_text("body")
            resumen = next((l for l in texto.splitlines() if "resultado" in l.lower()), "?")
            print(f"{s['nombre']} ({s['nombre_effi']}): {resumen}")

            ruta = RAW_DIR / f"raw_mensual_{s['codigo']}.xlsx"
            with page.expect_download(timeout=120_000) as dl_info:
                page.locator("text=Exportar a excel").first.click()
            dl_info.value.save_as(str(ruta))
            print(f"  -> descargado: {ruta.name}")

        browser.close()


if __name__ == "__main__":
    main()
