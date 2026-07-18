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
    """Navega a una URL interna y confirma que Effi no redirigió a /ingreso."""
    page.goto(URL_BASE, wait_until="domcontentloaded")
    time.sleep(2)
    return "ingreso" not in page.url and "login" not in page.url


def login(page):
    """Login manual con usuario/clave del Keychain. No intenta resolver reCAPTCHA."""
    usuario, clave = obtener_credenciales()
    page.goto(URL_LOGIN, wait_until="domcontentloaded")
    # Selectores confirmados en https://effi.com.co/ingreso (16-jul-2026).
    page.locator("input[placeholder='Email de usuario']").fill(usuario)
    page.locator("input[placeholder='Contraseña']").fill(clave)
    page.locator("button:has-text('Ingresar')").click()
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
