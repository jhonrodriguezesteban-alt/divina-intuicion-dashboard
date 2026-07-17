"""
Verifica si la sesión guardada de Effi sigue viva.
Pensado para correr al encender la máquina / montar el volumen.
Si la sesión expiró, abre un navegador VISIBLE para reloguear manualmente
(nunca intenta resolver un reCAPTCHA de forma automática).
"""

from playwright.sync_api import sync_playwright

from common.effi_client import login, obtener_contexto, sesion_viva, SESSION_PATH


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        if SESSION_PATH.exists():
            context = browser.new_context(storage_state=str(SESSION_PATH))
            page = context.new_page()
            if sesion_viva(page):
                print("Sesión de Effi activa. Nada que hacer.")
                browser.close()
                return
            context.close()
        browser.close()

        print("Sesión inválida o inexistente. Abriendo navegador para login manual/automático...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        login(page)
        context.storage_state(path=str(SESSION_PATH))
        print(f"Sesión guardada en {SESSION_PATH}")
        browser.close()


if __name__ == "__main__":
    main()
