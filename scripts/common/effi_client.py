"""
Cliente de Effi Systems (ERP sin API pública) vía Playwright.

Maneja login, persistencia de sesión (cookies) y descarga de reportes en Excel.
Sigue los patrones documentados en JR ARQUITECTURA_REPLICABLE.md sección 2.

Las credenciales NUNCA se guardan en el repo. Se leen del Keychain de macOS:
    security add-generic-password -a "<usuario>" -s "divina-intuicion-effi" -w "<clave>"
La sesión (cookies) se guarda fuera del repo, en el home del usuario.
"""

import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL_LOGIN = "https://effi.com.co/ingreso"
URL_BASE = "https://effi.com.co/app/"

KEYCHAIN_SERVICE = "divina-intuicion-effi"
KEYCHAIN_USER = "dayanajaimes2002@gmail.com"
SESSION_PATH = Path.home() / ".divina_intuicion_session.json"


def obtener_credenciales():
    """Lee usuario/clave desde el Keychain de macOS (nunca desde un archivo del repo)."""
    clave = subprocess.run(
        ["security", "find-generic-password", "-a", KEYCHAIN_USER, "-s", KEYCHAIN_SERVICE, "-w"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return KEYCHAIN_USER, clave


def sesion_viva(page) -> bool:
    """Navega a una URL interna y confirma que Effi no redirigió a /ingreso.
    Si Effi tarda en responder, se asume sesión no válida y se hace login
    nuevo -- antes un timeout aquí tumbaba la descarga entera."""
    try:
        page.goto(URL_BASE, wait_until="domcontentloaded", timeout=60_000)
    except Exception:
        return False
    time.sleep(2)
    return "ingreso" not in page.url and "login" not in page.url


def login(page):
    """Login manual con usuario/clave del Keychain. No intenta resolver reCAPTCHA."""
    usuario, clave = obtener_credenciales()
    page.goto(URL_LOGIN, wait_until="domcontentloaded")
    # Effi rediseñó /ingreso (~15-oct-2026): el placeholder del correo pasó de
    # "Email de usuario" a "nombre@empresa.com" y así estuvo caído el scraping
    # dos días. Se busca por id/name/type (más estables que el texto visible)
    # con el placeholder viejo como último recurso.
    page.locator("#email, input[name='email'], input[type='email'], input[placeholder='Email de usuario']").first.fill(usuario)
    page.locator("#password, input[name='password'], input[type='password']").first.fill(clave)
    page.locator("button:has-text('Ingresar'), button[type='submit']").first.click()
    page.wait_for_url(lambda url: "ingreso" not in url and "login" not in url, timeout=30_000)


def obtener_contexto(playwright, headless=True):
    """
    Devuelve (browser, context, page) reutilizando la sesión guardada si sigue viva.
    Si no hay sesión o expiró, hace login y guarda la sesión nueva.
    Si el login automático falla (ej. reCAPTCHA), lanza la excepción sin publicar nada.
    """
    browser = playwright.chromium.launch(headless=headless)

    if SESSION_PATH.exists():
        context = browser.new_context(storage_state=str(SESSION_PATH), accept_downloads=True)
        page = context.new_page()
        if sesion_viva(page):
            return browser, context, page
        context.close()

    context = browser.new_context(accept_downloads=True)
    page = context.new_page()
    login(page)
    context.storage_state(path=str(SESSION_PATH))
    return browser, context, page


def navegar_y_descargar(page, url_base, raw_dir: Path, sufijo: str, desde: str = None, hasta: str = None, columnas=None):
    """
    Patrón genérico de descarga de un reporte de Effi a Excel.
    desde/hasta en formato 'YYYY-MM-DD'. columnas: lista de nombres a marcar en "Seleccione las columnas".
    """
    url = url_base
    if desde and hasta:
        url = f"{url_base}?desde={desde}%2000:00:00&hasta={hasta}%2023:59:59"

    page.goto(url, wait_until="domcontentloaded")
    time.sleep(5)  # Effi es una SPA lenta; esperas fijas son más confiables que esperar selectores

    page.locator("a:has-text('Reportes y análisis de datos')").click()
    page.locator("a:has-text('Reporte de conceptos')").click()
    page.locator("text=Seleccione las columnas").wait_for(state="visible")

    for col in (columnas or []):
        chk = page.locator(f"label:has-text('{col}') input[type='checkbox']")
        if chk.count() and not chk.first.is_checked():
            chk.first.check()

    raw_dir.mkdir(parents=True, exist_ok=True)
    ruta = raw_dir / f"raw_{sufijo}.xlsx"
    with page.expect_download(timeout=240_000) as dl_info:
        page.locator("button:has-text('Exportar'), input[value*='Exportar' i]").first.click()
    dl_info.value.save_as(str(ruta))
    return ruta


# ---------------------------------------------------------------------------
# Exportación a Excel con el flujo nuevo de Effi (desde ~15-oct-2026)
# ---------------------------------------------------------------------------
# Antes "Exportar a excel" en Remisiones/Facturas descargaba el archivo de una
# vez. Ahora siempre abre el modal "Seleccione las columnas que desea exportar
# a Excel" (todas desmarcadas) y, al confirmar, genera el archivo EN SEGUNDO
# PLANO: unos segundos después aparece como enlace en el centro de
# notificaciones (".../descarga_amigable_archivo/?file_name=...&file_url=
# public/temp/reportes_excel/XXXX.xlsx"). Nunca dispara un download directo.

import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse

URL_EFFI = "https://effi.com.co/"
_SELECTOR_LINKS_REPORTE = "a[href*='reportes_excel']"


def _links_reportes(page) -> dict:
    """{href: texto} de todos los enlaces a reportes generados visibles en la página."""
    return {
        x["href"]: x["texto"]
        for x in page.eval_on_selector_all(
            _SELECTOR_LINKS_REPORTE,
            "els => els.map(e => ({href: e.href, texto: (e.innerText || '').trim()}))",
        )
    }


def _url_archivo(href: str) -> str:
    """El enlace nuevo pasa por descarga_amigable_archivo con el archivo real en
    el parámetro file_url; el formato viejo apuntaba directo al .xlsx."""
    qs = parse_qs(urlparse(href).query)
    if "file_url" in qs:
        return URL_EFFI + qs["file_url"][0].lstrip("/")
    return href


def _nombre_archivo(href: str) -> str:
    qs = parse_qs(urlparse(href).query)
    return qs.get("file_name", [href.rsplit("/", 1)[-1]])[0]


_RE_FECHA_REPORTE = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2})[-:](\d{2})[-:](\d{2})")


def _es_reporte_esperado(href: str, nombre_reporte: str, desde: datetime) -> bool:
    """El centro de notificaciones carga enlaces de forma irregular: un reporte
    VIEJO puede aparecer como "nuevo" al recargar (pasó 2026-10-17: el
    catálogo de artículos se guardó con el archivo de facturas). Por eso no
    basta con "enlace que no estaba antes": se exige el nombre del reporte y
    que su hora de generación sea posterior al clic en exportar."""
    nombre = _nombre_archivo(href)
    if not nombre.lower().startswith(nombre_reporte.lower()):
        return False
    m = _RE_FECHA_REPORTE.search(nombre)
    if not m:
        return False
    generado = datetime.strptime(f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}", "%Y-%m-%d %H:%M:%S")
    return generado >= desde - timedelta(minutes=2)


def marcar_columnas_modal(page, boton_confirmar: str, columnas: list, prefijos: list = ()) -> None:
    """Marca las columnas por nombre EXACTO de la etiqueta (no por "contiene":
    "Costo manual" también aparecería dentro de "Utilidad (costo manual)").
    Primero desmarca todo para no arrastrar lo que haya quedado marcado de
    una exportación anterior (el estado se comparte a nivel de cuenta)."""
    modal = page.locator(f".modal:has({boton_confirmar})")
    desmarcar = modal.locator("button:has-text('Desmarcar todo'), a:has-text('Desmarcar todo')")
    if desmarcar.count():
        desmarcar.first.click()
        page.wait_for_timeout(500)
    valores = modal.first.evaluate(
        """(m, cols) => {
          const norm = s => (s || '').replace(/\\s+/g, ' ').trim().toLowerCase();
          const chks = [...m.querySelectorAll('input[type=checkbox]')];
          const lbl = c => norm((c.closest('label') || {}).innerText);
          return cols.map(col => { const c = chks.find(x => lbl(x) === norm(col)); return c ? c.value : null; });
        }""",
        columnas,
    )
    if prefijos:
        # columnas "dinámicas" (ej. una por bodega): se marcan todas las que
        # empiecen así, para que una bodega nueva no se pierda en silencio
        valores += modal.first.evaluate(
            """(m, prefs) => [...m.querySelectorAll('input[type=checkbox]')]
                 .filter(c => prefs.some(p => ((c.closest('label') || {}).innerText || '').trim().startsWith(p)))
                 .map(c => c.value)""",
            list(prefijos),
        )
    faltantes = [c for c, v in zip(columnas, valores) if not v]
    if faltantes:
        disponibles = modal.first.evaluate(
            "m => [...m.querySelectorAll('input[type=checkbox]')].map(c => ((c.closest('label') || {}).innerText || '').trim())"
        )
        raise RuntimeError(f"Effi ya no ofrece estas columnas en el modal: {faltantes}. Disponibles: {disponibles}")
    for v in valores:
        modal.locator(f"input[type=checkbox][value='{v}']").first.check(force=True)


def exportar_excel(page, context, url: str, columnas: list, ruta: Path, nombre_reporte: str,
                   boton_abrir: str = "a.bg-green-active:has-text('Exportar a excel')",
                   boton_confirmar: str = "#btnValidarExcel",
                   max_espera_s: int = 1200, poll_s: int = 15, prefijos: list = ()) -> Path:
    """Abre `url`, exporta a Excel con `columnas` y guarda el archivo en `ruta`.
    Lanza excepción si algo falla (para que el orquestador lo reporte)."""
    page.goto(url, wait_until="domcontentloaded", timeout=120_000)
    page.wait_for_timeout(3000)
    return exportar_excel_pagina_actual(page, context, columnas, ruta, nombre_reporte, boton_abrir, boton_confirmar, max_espera_s, poll_s, prefijos)


def exportar_excel_pagina_actual(page, context, columnas: list, ruta: Path, nombre_reporte: str,
                                 boton_abrir: str = "a.bg-green-active:has-text('Exportar a excel')",
                                 boton_confirmar: str = "#btnValidarExcel",
                                 max_espera_s: int = 1200, poll_s: int = 15, prefijos: list = ()) -> Path:
    """Igual que exportar_excel pero sobre la página ya cargada -- para reportes
    que necesitan aplicar filtros en pantalla antes de exportar (ej. el
    reporte mensual por sucursal)."""
    texto = page.inner_text("body")
    resumen = next((l for l in texto.splitlines() if "encontrad" in l.lower()), "")
    if resumen:
        print(f"[{datetime.now():%H:%M:%S}] Rango:", resumen.strip())
    antes = set(_links_reportes(page))

    page.locator(boton_abrir).first.click()
    page.locator(boton_confirmar).wait_for(state="visible", timeout=20_000)
    marcar_columnas_modal(page, boton_confirmar, columnas, prefijos)

    momento_clic = datetime.now()
    descarga_directa = None
    try:
        with page.expect_download(timeout=15_000) as dl:
            page.locator(boton_confirmar).click()
        descarga_directa = dl.value
    except Exception:
        pass
    if descarga_directa:
        descarga_directa.save_as(str(ruta))
        print(f"Descarga directa -> {ruta}")
        return ruta

    print(f"[{datetime.now():%H:%M:%S}] Exportación en segundo plano; esperando el enlace en notificaciones...")
    esperado, nuevo = 0, None
    while esperado < max_espera_s:
        nuevos = [h for h in _links_reportes(page) if h not in antes and _es_reporte_esperado(h, nombre_reporte, momento_clic)]
        if nuevos:
            nuevo = nuevos[-1]
            break
        page.wait_for_timeout(poll_s * 1000)
        esperado += poll_s
        if esperado % (poll_s * 4) == 0:
            # el centro de notificaciones a veces solo se refresca al recargar;
            # se recarga una página liviana en vez del listado pesado
            try:
                page.goto(URL_BASE, wait_until="domcontentloaded", timeout=120_000)
                page.wait_for_timeout(2000)
            except Exception:
                pass
            print(f"  ...{esperado}s, aún no aparece el reporte")
    if not nuevo:
        raise TimeoutError(f"Effi no generó el reporte '{nombre_reporte}' en {max_espera_s}s.")

    print(f"[{datetime.now():%H:%M:%S}] Reporte listo: {_nombre_archivo(nuevo)}")
    ultimo_error = None
    for intento in range(3):
        try:
            resp = context.request.get(_url_archivo(nuevo), timeout=180_000)
            cuerpo = resp.body()
            if resp.ok and cuerpo[:2] == b"PK":
                ruta.write_bytes(cuerpo)
                print(f"[{datetime.now():%H:%M:%S}] Descargado en {ruta} ({len(cuerpo):,} bytes)")
                return ruta
            ultimo_error = f"HTTP {resp.status}, {len(cuerpo)} bytes, no es xlsx"
        except Exception as e:
            ultimo_error = str(e)
            print(f"[{datetime.now():%H:%M:%S}] Falló la descarga del archivo (intento {intento + 1}/3): {ultimo_error[:120]}")
        page.wait_for_timeout(5000)
    raise RuntimeError(f"No se pudo bajar el archivo generado: {ultimo_error}")
