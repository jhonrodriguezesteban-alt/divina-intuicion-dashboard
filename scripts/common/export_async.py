"""
Helper genérico de export para listados de Effi: intenta un download directo
(síncrono) y si no llega, sondea el centro de notificaciones (export
asíncrono para volúmenes grandes) — mismo patrón descubierto para el
catálogo de Artículos, generalizado para reusar en Remisiones y otros
listados.
"""

from pathlib import Path


def _links_reporte(page, prefijo_texto: str):
    return page.eval_on_selector_all(
        "a[href]",
        f"""els => els.map(e => ({{texto: e.innerText.trim(), href: e.href}}))
            .filter(x => x.texto.startsWith({prefijo_texto!r}))"""
    )


def exportar_con_fallback_async(context, page, boton_selector: str, prefijo_notificacion: str,
                                 ruta_destino: Path, timeout_directo_ms=25_000,
                                 poll_segundos=15, max_espera_segundos=300):
    """
    Hace clic en boton_selector (debe disparar el export). Si hay download
    directo, lo guarda. Si no, sondea notificaciones por un link nuevo que
    empiece con prefijo_notificacion y lo descarga vía HTTP autenticado.
    """
    antes = {l["href"] for l in _links_reporte(page, prefijo_notificacion)}

    try:
        with page.expect_download(timeout=timeout_directo_ms) as dl_info:
            page.locator(boton_selector).first.click()
        dl_info.value.save_as(str(ruta_destino))
        return "directo"
    except Exception:
        pass

    esperado = 0
    while esperado < max_espera_segundos:
        page.wait_for_timeout(poll_segundos * 1000)
        esperado += poll_segundos
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        nuevos = [l for l in _links_reporte(page, prefijo_notificacion) if l["href"] not in antes]
        if nuevos:
            resp = context.request.get(nuevos[0]["href"])
            ruta_destino.write_bytes(resp.body())
            return "async"
        print(f"  ...{esperado}s esperando reporte '{prefijo_notificacion}'")

    return "timeout"
