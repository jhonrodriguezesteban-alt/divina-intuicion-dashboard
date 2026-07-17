"""
Descarga el "Reporte de remisiones de venta mensuales" filtrado por cada
sucursal (una corrida por sucursal, porque el reporte no desglosa por
sucursal en columnas — solo agrega por mes). Rango: todo el histórico
disponible hasta hoy.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH
from common.export_async import exportar_con_fallback_async
from common.procesamiento import cargar_config

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
URL = "https://effi.com.co/app/remision_v/reporte_mensual"
DESDE = "2025-01-01 00:00:00"
HASTA = "2026-07-16 23:59:59"


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
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH), accept_downloads=True)
        page = context.new_page()

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
            resultado = exportar_con_fallback_async(
                context, page,
                boton_selector="text=Exportar a excel",
                prefijo_notificacion="Reporte: Remisiones",
                ruta_destino=ruta,
                timeout_directo_ms=20_000,
                max_espera_segundos=120,
            )
            print(f"  -> {resultado}: {ruta.name}")

        browser.close()


if __name__ == "__main__":
    main()
