"""
Corrida automática (cron/LaunchAgent cada hora): reutiliza la sesión guardada,
descarga solo el período en curso, regenera y publica.
Si la sesión expiró, intenta auto-login; si falla (ej. captcha), se detiene sin publicar.
"""

from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto, navegar_y_descargar
from generar_dashboard import generar_dashboard_html, publicar

RAW_DIR = Path(__file__).resolve().parent.parent / "reportes" / "raw"


def main():
    hoy = date.today().isoformat()
    with sync_playwright() as p:
        try:
            browser, context, page = obtener_contexto(p, headless=True)
        except Exception as e:
            print(f"No se pudo establecer sesión con Effi ({e}). Abortando sin publicar.")
            return

        try:
            # TODO: descargar solo el período en curso (hoy) para los módulos activos.
            pass
        finally:
            browser.close()

    html = generar_dashboard_html({})
    publicar(html)
    # TODO: git add/commit/push automático una vez el repo remoto esté creado.


if __name__ == "__main__":
    main()
