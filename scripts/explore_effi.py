"""
Diagnóstico puntual: usa la sesión ya guardada (no vuelve a loguear) para
mapear la navegación real de la app y volcarla a un JSON local. Sirve para
confirmar URLs/nombres de módulo reales antes de escribir los flujos de
descarga definitivos.
"""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from common.effi_client import SESSION_PATH, URL_BASE

OUT = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "_mapa_navegacion.json"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(SESSION_PATH))
        page = context.new_page()
        page.goto(URL_BASE, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        links = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({texto: e.innerText.trim(), href: e.href})).filter(x => x.texto)"
        )

        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(links)} links encontrados. Guardado en {OUT}")
        browser.close()


if __name__ == "__main__":
    main()
