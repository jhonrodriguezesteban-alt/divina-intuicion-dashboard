"""
Descarga TODAS las facturas de venta desde 2025-01-01 hasta hoy (nivel
documento, una fila por factura) -- analógico a descargar_remisiones_completas.py.

Por qué existe este módulo aparte de Remisiones: cuando una venta necesita
factura formal (cliente con NIT/CUFE DIAN), el flujo en Effi es crear
primero la remisión y luego convertirla en factura -- Effi anula
automáticamente la remisión original al hacerlo. Esa remisión Anulada ya
se excluye del cálculo de ventas (correcto), pero la factura resultante
nunca se estaba descargando, así que esa venta no se contaba en ningún
lado. Se corrige agregando esta fuente y sumándola (Estado CXC != Anulado)
junto con remisiones -- sin riesgo de doble conteo porque la remisión que
originó la factura siempre queda Anulada.
"""

from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
DESDE = "2025-01-01 00:00:00"
HASTA = datetime.now().strftime("%Y-%m-%d 23:59:59")


def main():
    url = f"https://effi.com.co/app/factura_v?desde={DESDE.replace(' ', '%20')}&hasta={HASTA.replace(' ', '%20')}"
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)
        page.goto(url, wait_until="domcontentloaded")
        boton = page.locator("text=Exportar a excel").first
        boton.wait_for(state="visible", timeout=120_000)
        page.wait_for_timeout(1500)

        texto = page.inner_text("body")
        resumen = next((l for l in texto.splitlines() if "encontrad" in l.lower()), "?")
        print("Rango:", resumen)

        ruta = RAW_DIR / "raw_facturas_completo.xlsx"
        with page.expect_download(timeout=300_000) as dl_info:
            boton.click()
        dl_info.value.save_as(str(ruta))
        print(f"Descargado en {ruta}")
        browser.close()


if __name__ == "__main__":
    main()
