"""
Descarga el catálogo de artículos (con stock por bodega y costos) ->
reportes/raw/raw_articulos.xlsx

Usa el flujo de exportación nuevo de Effi (modal de columnas + archivo
generado en segundo plano, ver common.effi_client.exportar_excel). Se
marcan explícitamente las columnas que necesitan procesar_inventario.py,
procesar_reorden.py, procesar_liquidacion.py y procesar_planeacion_temporada.py,
más TODAS las columnas "Stock bodega: ..." (si Effi agrega una bodega nueva,
entra sola -- ya pasó con "BODEGA PRINCIPAL 413" en oct-2026).

Para este catálogo grande Effi a veces genera el archivo SIN algunas de las
columnas marcadas (confirmado 2026-08-01, del lado de Effi) -- por eso se
valida el Excel resultante y se reintenta. Historial de cambios de Effi:
"Stock total empresa" pasó a llamarse "Stock disponible empresa" (oct-2026);
asegurar_columnas_articulos() lo mapea al nombre viejo.
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto, exportar_excel
from common.procesamiento import leer_excel_effi

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"
URL_ARTICULOS = "https://effi.com.co/app/articulo"
MAX_INTENTOS = 3

COLUMNAS_REQUERIDAS = [
    "ID", "Nombre", "Referencia", "Categoría", "Vigencia",
    "Costo manual", "Precio: DETAL", "Stock disponible empresa",
]
PREFIJOS_COLUMNAS = ["Stock bodega:"]


def _columnas_faltantes(ruta: Path) -> list:
    df = leer_excel_effi(ruta)
    faltan = [c for c in COLUMNAS_REQUERIDAS if c not in df.columns]
    if not any(c.startswith("Stock bodega:") for c in df.columns):
        faltan.append("Stock bodega: (ninguna)")
    return faltan


def main():
    ruta = RAW_DIR / "raw_articulos.xlsx"
    hubo_descarga = False
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)
        for intento in range(1, MAX_INTENTOS + 1):
            print(f"--- intento {intento}/{MAX_INTENTOS} ---")
            try:
                exportar_excel(page, context, URL_ARTICULOS, COLUMNAS_REQUERIDAS, ruta, "Reporte de Artículos", prefijos=PREFIJOS_COLUMNAS)
            except Exception as e:
                print(f"Intento {intento} falló: {e}")
                continue
            hubo_descarga = True
            faltantes = _columnas_faltantes(ruta)
            if not faltantes:
                print("Columnas requeridas OK.")
                browser.close()
                return
            print(f"AVISO: el Excel descargado no trae estas columnas: {faltantes}. Reintentando...")
        browser.close()

    if not hubo_descarga:
        # código 1 para que cierre_dia.py lo reporte (allá no bloquea el resto del cierre)
        print(f"ERROR: no se logró descargar el catálogo en {MAX_INTENTOS} intentos; {ruta} quedó con la versión anterior.")
        sys.exit(1)
    print(f"No se logró que Effi incluyera todas las columnas tras {MAX_INTENTOS} intentos. "
          f"Se deja el último archivo en {ruta}; procesar_inventario.py avisará qué falta.")


if __name__ == "__main__":
    main()
