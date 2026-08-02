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

Effi NO recuerda qué columnas quedaron marcadas de una vez a otra (lo
confirmó John probando manualmente el 2026-08-01: las vuelve a
desmarcar cada vez que se reabre el modal, incluso tras exportar). Por
eso este script marca a la fuerza las columnas que el pipeline necesita
en cada corrida en vez de confiar en lo que haya quedado seleccionado
-- si no, procesar_inventario.py/procesar_reorden.py/procesar_liquidacion.py
truenan con KeyError apenas falte "Categoría", "Costo manual", etc.

Además, para este catálogo (2800+ items) el export se genera en
segundo plano en Effi -- se confirmó en vivo (probando varias veces
seguidas) que el archivo resultante a veces NO trae todas las columnas
marcadas en el modal, aunque el DOM las muestre correctamente marcadas
justo antes de exportar. No es algo que este script pueda controlar
del lado del navegador (el modal ya está bien), así que en vez de
confiar en un solo intento, se valida el Excel resultante contra las
columnas requeridas y se reintenta la descarga completa (recargar,
volver a abrir el modal, volver a marcar) unas cuantas veces antes de
darse por vencido.
"""

from datetime import datetime
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto
from common.procesamiento import leer_excel_effi

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
URL_ARTICULOS = "https://effi.com.co/app/articulo"
POLL_SEGUNDOS = 15
MAX_ESPERA_SEGUNDOS = 300
MAX_INTENTOS = 3

# Columnas que procesar_inventario.py / procesar_reorden.py / procesar_liquidacion.py
# leen del Excel -- si Effi las desmarca, hay que volver a marcarlas antes de exportar.
COLUMNAS_REQUERIDAS = [
    "ID",
    "Nombre",
    "Categoría",
    "Costo manual",
    "Stock total empresa",
    "Stock bodega: DIVINA INTUCION 144",
    "Stock bodega: DIVINA INTUICION 433",
    "Stock bodega: DIVINA ACCESORIOS",
]


def _marcar_columnas_requeridas(page):
    """El estado de estas casillas parece compartido a nivel de cuenta Effi
    (la misma cuenta "Jenifer Dayana" se usa en el navegador manual y en
    este script) -- se vio en vivo que un checkbox puede aparecer marcado
    en un load y sin marcar en el siguiente sin que este script haga nada.
    Por eso se usa .check() (idempotente, con las esperas/reintentos de
    Playwright) en vez de leer is_checked() primero y decidir si clickear."""
    for col in COLUMNAS_REQUERIDAS:
        chk = page.locator(f"#modalExcel label:has-text('{col}') input[type='checkbox']").first
        chk.wait_for(state="attached", timeout=10_000)
        chk.check()


def _links_reporte_articulos(page):
    return page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => ({texto: e.innerText.trim(), href: e.href}))"
        ".filter(x => x.texto.startsWith('Reporte: Artículos'))"
    )


def _columnas_faltantes(ruta: Path) -> list:
    df = leer_excel_effi(ruta)
    return [c for c in COLUMNAS_REQUERIDAS if not any(c in real for real in df.columns)]


def _intentar_descarga(page, context, ruta: Path) -> bool:
    """Un intento completo: abre el modal, marca columnas, exporta (directo
    o vía notificación) y guarda en `ruta`. Devuelve True si la descarga en
    sí funcionó (sin validar columnas todavía -- eso lo hace el caller)."""
    page.goto(URL_ARTICULOS, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    antes = {l["href"] for l in _links_reporte_articulos(page)}

    page.locator("a.bg-green-active:has-text('Exportar a excel')").first.click()
    page.locator("#btnValidarExcel").wait_for(state="visible", timeout=15_000)
    _marcar_columnas_requeridas(page)

    try:
        with page.expect_download(timeout=25_000) as dl_info:
            page.locator("#btnValidarExcel").click()
        dl_info.value.save_as(str(ruta))
        print(f"Descarga directa OK: {ruta}")
        return True
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
        return False

    print(f"Reporte listo: {nuevo_link['texto']}")
    resp = context.request.get(nuevo_link["href"])
    ruta.write_bytes(resp.body())
    print(f"Descargado en {ruta} ({len(resp.body())} bytes)")
    return True


def main():
    ruta = RAW_DIR / "raw_articulos.xlsx"
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)

        for intento in range(1, MAX_INTENTOS + 1):
            print(f"--- intento {intento}/{MAX_INTENTOS} ---")
            if not _intentar_descarga(page, context, ruta):
                continue
            faltantes = _columnas_faltantes(ruta)
            if not faltantes:
                print("Columnas requeridas OK.")
                browser.close()
                return
            print(f"AVISO: el Excel descargado no trae estas columnas requeridas: {faltantes}. Reintentando...")

        print(f"No se logró que Effi incluyera todas las columnas requeridas tras {MAX_INTENTOS} intentos. "
              f"Se deja el último archivo descargado en {ruta}; procesar_inventario.py avisará qué falta.")
        browser.close()


if __name__ == "__main__":
    main()
