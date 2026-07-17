"""
Motor de generación del dashboard.html — un solo archivo estático, sin build step.
Ver JR ARQUITECTURA_REPLICABLE.md sección 4 para las trampas de f-strings/JS embebido.

v1: Mesa de Gerencia + Ventas por Punto de Venta, con datos reales de Effi
(remisiones de venta, filtradas por Estado CXC = "Pago total").
Pendiente: Inventario/Rotación y Comercial/Comisiones (se agregan cuando
completemos config/categoria_familia.json y config/metas_comisiones.json).

Paleta: tonos grises claros / boutique minimalista, inspirada en el
Instagram de la marca (@divina_intuicion) — fondo crema, tarjetas blancas,
tipografía serif en titulares, acentos en carbón.
"""

import json
from datetime import datetime
from pathlib import Path

REPORTES_DIR = Path(__file__).resolve().parent.parent / "reportes"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "dashboard.html"


def _cargar_json(ruta: Path, default=None):
    if not ruta.exists():
        return default
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _cop(valor) -> str:
    return "$" + f"{round(valor):,}".replace(",", ".")


def _tarjeta_kpi(etiqueta: str, valor: str, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{etiqueta}</div>
      <div class="kpi-valor">{valor}</div>
      {sub_html}
    </div>"""


def _fila_sucursal(nombre: str, ingreso: float, transacciones: int, maximo: float) -> str:
    pct = round((ingreso / maximo) * 100, 1) if maximo else 0
    return f"""
    <div class="suc-fila">
      <div class="suc-nombre">{nombre}</div>
      <div class="suc-barra-wrap">
        <div class="suc-barra" style="width:{pct}%"></div>
      </div>
      <div class="suc-cifras">{_cop(ingreso)} <span class="suc-trans">· {transacciones} ventas</span></div>
    </div>"""


def generar_dashboard_html(datos: dict = None) -> str:
    ventas = _cargar_json(REPORTES_DIR / "ventas_procesado.json")
    sucursales_cfg = _cargar_json(CONFIG_DIR / "sucursales.json", {"sucursales": []})["sucursales"]
    nombre_effi_a_comercial = {s["nombre_effi"]: s["nombre"] for s in sucursales_cfg}

    if not ventas:
        return _html_sin_datos()

    k = ventas["kpis"]
    por_sucursal = sorted(ventas["por_sucursal"], key=lambda r: -r["ingreso"])
    maximo = max((r["ingreso"] for r in por_sucursal), default=1)

    kpis_html = "".join([
        _tarjeta_kpi("Ingreso total", _cop(k["ingreso_total"]), f'{k["num_transacciones"]} ventas'),
        _tarjeta_kpi("Ticket promedio", _cop(k["ticket_promedio"])),
        _tarjeta_kpi("Utilidad (costo promedio)", _cop(k["utilidad_total_costo_promedio"])),
        _tarjeta_kpi("Margen promedio", f'{round(k["margen_promedio"] * 100, 1)}%'),
        _tarjeta_kpi("Anuladas", str(k["num_anuladas"]), "excluidas del ingreso"),
    ])

    sucursales_html = "".join([
        _fila_sucursal(
            nombre_effi_a_comercial.get(r["Sucursal"], r["Sucursal"]),
            r["ingreso"], r["transacciones"], maximo,
        )
        for r in por_sucursal
    ])

    rango = k["rango_fechas"]
    generado = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Divina Intuición — Dashboard Gerencial</title>
<style>
  :root {{
    --bg: #f4f1ec;
    --card: #ffffff;
    --borde: #e6e1d8;
    --texto: #2b2823;
    --texto-sub: #8a8377;
    --acento: #33302a;
    --acento-suave: #cbc3b3;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--texto);
    margin: 0;
    padding: 2.5rem 3rem;
  }}
  header {{ margin-bottom: 2rem; }}
  h1 {{
    font-family: Georgia, "Times New Roman", serif;
    letter-spacing: .04em;
    font-weight: 400;
    font-size: 1.9rem;
    margin: 0 0 .3rem 0;
    text-transform: uppercase;
  }}
  .subtitulo {{ color: var(--texto-sub); font-size: .95rem; }}
  h2 {{
    font-family: Georgia, "Times New Roman", serif;
    font-weight: 400;
    font-size: 1.2rem;
    text-transform: uppercase;
    letter-spacing: .03em;
    border-bottom: 1px solid var(--borde);
    padding-bottom: .5rem;
    margin: 2.5rem 0 1.2rem 0;
  }}
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
  }}
  .kpi-card {{
    background: var(--card);
    border: 1px solid var(--borde);
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
  }}
  .kpi-label {{ font-size: .8rem; color: var(--texto-sub); text-transform: uppercase; letter-spacing: .03em; }}
  .kpi-valor {{ font-size: 1.6rem; margin-top: .3rem; font-weight: 600; }}
  .kpi-sub {{ font-size: .78rem; color: var(--texto-sub); margin-top: .2rem; }}
  .suc-fila {{
    display: grid;
    grid-template-columns: 160px 1fr 220px;
    align-items: center;
    gap: 1rem;
    padding: .7rem 0;
    border-bottom: 1px solid var(--borde);
  }}
  .suc-nombre {{ font-weight: 600; font-size: .92rem; }}
  .suc-barra-wrap {{ background: #ece7dd; border-radius: 6px; height: 14px; overflow: hidden; }}
  .suc-barra {{ background: var(--acento); height: 100%; border-radius: 6px; }}
  .suc-cifras {{ text-align: right; font-size: .92rem; font-variant-numeric: tabular-nums; }}
  .suc-trans {{ color: var(--texto-sub); font-size: .8rem; }}
  .nota {{
    margin-top: 2.5rem;
    padding: 1rem 1.2rem;
    border: 1px dashed var(--acento-suave);
    border-radius: 8px;
    font-size: .85rem;
    color: var(--texto-sub);
  }}
  footer {{ margin-top: 2rem; font-size: .75rem; color: var(--texto-sub); }}
</style>
</head>
<body>
  <header>
    <h1>Divina Intuición</h1>
    <div class="subtitulo">Dashboard Gerencial · Local 144 · Local 433 · Local 107 (Divina Accesorios)</div>
  </header>

  <h2>Mesa de Gerencia</h2>
  <div class="kpi-grid">{kpis_html}</div>

  <h2>Ventas por Punto de Venta</h2>
  <div>{sucursales_html}</div>

  <div class="nota">
    Periodo mostrado: {rango["desde"]} a {rango["hasta"]} (ventana visible por defecto de Effi al momento de la descarga).
    Ingreso calculado solo sobre remisiones con estado "Pago total" — excluye {k["num_anuladas"]} remisiones anuladas.
    Pendiente: Inventario/Rotación (reorden a proveedores) y Comisiones, en construcción.
  </div>

  <footer>Generado el {generado} · datos de Effi Systems</footer>
</body>
</html>
"""


def _html_sin_datos() -> str:
    return """<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>Divina Intuición — Dashboard Gerencial</title></head>
<body style="font-family:sans-serif;padding:2rem;background:#f4f1ec;">
<h1>Divina Intuición</h1>
<p>Aún sin datos procesados. Corre scripts/procesar_ventas.py primero.</p>
</body></html>"""


def publicar(html: str):
    """Escribe dashboard.html. La publicación a GitHub Pages (git commit + push) se hace
    aparte, y solo desde reporte_completo.py / actualizar_dashboard.py — nunca desde un script de prueba."""
    DASHBOARD_PATH.write_text(html, encoding="utf-8")
    print(f"dashboard.html generado en {DASHBOARD_PATH}")


if __name__ == "__main__":
    publicar(generar_dashboard_html())
