"""
Descarga TODAS las remisiones de venta desde 2025-01-01 hasta hoy (nivel
documento, una fila por remisión) usando el filtro de fecha por
querystring confirmado en explore/test_filtro_fecha.py.

Igual que "Reporte de conceptos" (ver descargar_conceptos.py), este
export SIEMPRE dispara un download directo del navegador — nunca pasa
por el centro de notificaciones. A medida que crece el histórico puede
tardar más de lo que parecía al principio, así que se usa un timeout
largo en vez del helper de fallback async (que nunca encuentra nada
para este tipo de reporte y solo hace perder minutos esperando).
"""

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
DESDE = "2025-01-01 00:00:00"
HASTA = datetime.now().strftime("%Y-%m-%d 23:59:59")


def main():
    url = f"https://effi.com.co/app/remision_v?desde={DESDE.replace(' ', '%20')}&hasta={HASTA.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)
        page.goto(url, wait_until="domcontentloaded")
        boton = page.locator("text=Exportar a excel").first
        boton.wait_for(state="visible", timeout=120_000)
        page.wait_for_timeout(1500)

        texto = page.inner_text("body")
        resumen = next((l for l in texto.splitlines() if "encontrad" in l.lower()), "?")
        print("Rango:", resumen)

        ruta = RAW_DIR / "raw_remisiones_completo.xlsx"
        print("Enviando export, puede tardar varios minutos...")
        with page.expect_download(timeout=900_000) as dl_info:
            boton.click()
        dl_info.value.save_as(str(ruta))
        print(f"Descargado en {ruta}")
        browser.close()


if __name__ == "__main__":
    main()
