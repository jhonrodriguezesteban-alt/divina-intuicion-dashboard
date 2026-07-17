"""Prueba puntual de login + guardado de sesión. No descarga nada, solo valida acceso."""

from playwright.sync_api import sync_playwright

from common.effi_client import obtener_contexto


def main():
    with sync_playwright() as p:
        browser, context, page = obtener_contexto(p, headless=True)
        print("Login OK. URL actual:", page.url)
        print("Título de la página:", page.title())
        browser.close()


if __name__ == "__main__":
    main()
