"""
Descarga TODAS las remisiones de venta desde 2025-01-01 hasta hoy (nivel
documento, una fila por remisión) usando el filtro de fecha por
querystring confirmado en explore/test_filtro_fecha.py.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH
from common.export_async import exportar_con_fallback_async

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
DESDE = "2025-01-01 00:00:00"
HASTA = "2026-07-16 23:59:59"


def main():
    url = f"https://effi.com.co/app/remision_v?desde={DESDE.replace(' ', '%20')}&hasta={HASTA.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH), accept_downloads=True)
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        texto = page.inner_text("body")
        resumen = next((l for l in texto.splitlines() if "encontrad" in l.lower()), "?")
        print("Rango:", resumen)

        ruta = RAW_DIR / "raw_remisiones_completo.xlsx"
        resultado = exportar_con_fallback_async(
            context, page,
            boton_selector="text=Exportar a excel",
            prefijo_notificacion="Reporte: Remisiones",
            ruta_destino=ruta,
            timeout_directo_ms=40_000,
            max_espera_segundos=420,
        )
        print(f"Resultado: {resultado} -> {ruta if resultado != 'timeout' else 'NO DESCARGADO'}")
        browser.close()


if __name__ == "__main__":
    main()
