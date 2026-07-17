"""
Motor de generación del dashboard.html — un solo archivo estático, sin build step.
Ver JR ARQUITECTURA_REPLICABLE.md sección 4 para las trampas de f-strings/JS embebido.

v2: estructura y profundidad de datos calcada del dashboard de referencia
de Grupo Bentley (KPIs año + mes en curso, venta de hoy vs ayer, ventas
por punto de venta, rentabilidad por categoría, top de referencias,
comparativo histórico mensual año contra año por sucursal), pero con la
paleta de grises claros / boutique de Divina Intuición — no los colores
neón del dashboard de referencia, solo la diagramación y el nivel de data.

Pendiente: índice de cobertura por SKU (cruce inventario x ventas) y
Comercial/Comisiones — se agregan cuando completemos
config/categoria_familia.json y config/metas_comisiones.json.
"""

import json
from datetime import datetime
from pathlib import Path

REPORTES_DIR = Path(__file__).resolve().parent.parent / "reportes"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "dashboard.html"

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


# ---------- helpers de formato ----------

def _cargar_json(ruta: Path, default=None):
    if not ruta.exists():
        return default
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _miles(n) -> str:
    return f"{round(n):,}".replace(",", ".")


def _cop(valor) -> str:
    return "$" + _miles(valor)


def _pct(valor, decimales=1) -> str:
    return f"{round(valor * 100, decimales)}%"


# ---------- bloques reutilizables ----------

def _tarjeta_kpi(etiqueta: str, valor: str, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="kpi-card">
      <div class="kpi-label">{etiqueta}</div>
      <div class="kpi-valor">{valor}</div>
      {sub_html}
    </div>"""


def _grupo_kpis(kpis: dict, unidades: int = None) -> str:
    tarjetas = [
        _tarjeta_kpi("Ventas", _cop(kpis["ingreso_total"]), f'{_miles(kpis["num_transacciones"])} transacciones'),
        _tarjeta_kpi("Ticket promedio", _cop(kpis["ticket_promedio"])),
    ]
    if unidades is not None:
        tarjetas.append(_tarjeta_kpi("Unidades vendidas", _miles(unidades)))
    tarjetas += [
        _tarjeta_kpi("Utilidad", _cop(kpis["utilidad_total"])),
        _tarjeta_kpi("Margen", _pct(kpis["margen_promedio"])),
    ]
    return "".join(tarjetas)


def _fila_barra(nombre: str, valor: float, sub: str, maximo: float, clase_barra: str = "") -> str:
    pct = round((valor / maximo) * 100, 1) if maximo else 0
    return f"""
    <div class="suc-fila">
      <div class="suc-nombre">{nombre}</div>
      <div class="suc-barra-wrap">
        <div class="suc-barra {clase_barra}" style="width:{pct}%"></div>
      </div>
      <div class="suc-cifras">{sub}</div>
    </div>"""


def _fila_sucursal(nombre: str, ingreso: float, transacciones: int, maximo: float) -> str:
    return _fila_barra(nombre, ingreso, f'{_cop(ingreso)} <span class="suc-trans">· {_miles(transacciones)} ventas</span>', maximo)


def _fila_stock(nombre: str, unidades: int, maximo: int) -> str:
    return _fila_barra(nombre, unidades, f"{_miles(unidades)} unidades", maximo, "suc-barra-inv")


def _clase_margen(margen: float) -> str:
    if margen >= 0.40:
        return "margen-alto"
    if margen >= 0.25:
        return "margen-medio"
    return "margen-bajo"


def _fila_categoria_rentabilidad(cat: dict, maximo: float) -> str:
    pct_barra = round((cat["ventas_netas"] / maximo) * 100, 1) if maximo else 0
    clase = _clase_margen(cat["margen"])
    return f"""
    <div class="cat-fila">
      <div class="cat-nombre">{cat["categoria"]}</div>
      <div class="cat-barra-wrap">
        <div class="cat-barra {clase}" style="width:{pct_barra}%"></div>
      </div>
      <div class="cat-margen {clase}">{_pct(cat["margen"])}</div>
      <div class="cat-valor">{_cop(cat["ventas_netas"])}</div>
    </div>"""


def _fila_referencia(rank: int, ref: dict) -> str:
    return f"""
    <div class="ref-fila">
      <div class="ref-rank">{rank}</div>
      <div class="ref-nombre">{ref["nombre"].title()}</div>
      <div class="ref-unidades">{_miles(ref["unidades"])} und.</div>
      <div class="ref-valor">{_cop(ref["ventas_netas"])}</div>
    </div>"""


def _fila_categoria_inventario(cat: dict) -> str:
    return f"""
    <tr>
      <td>{cat["Categoría"]}</td>
      <td class="num">{_miles(cat["articulos"])}</td>
      <td class="num">{_miles(cat["stock_total"])}</td>
      <td class="num">{_cop(cat["valor_costo"])}</td>
    </tr>"""


# ---------- secciones ----------

def _seccion_venta_hoy(hoy: dict, nombre_map: dict) -> str:
    k = hoy["kpis"]
    ayer = hoy["ingreso_ayer"]
    hoy_val = k["ingreso_total"]
    if ayer:
        variacion = (hoy_val - ayer) / ayer
        signo = "▲" if variacion >= 0 else "▼"
        clase = "pos" if variacion >= 0 else "neg"
        comparativo = f'<span class="{clase}">{signo} {_pct(abs(variacion))} vs ayer</span>'
    else:
        comparativo = '<span class="suc-trans">sin venta ayer</span>'

    por_sucursal = sorted(hoy["por_sucursal"], key=lambda r: -r["ingreso"])
    desglose = " · ".join(f'{r["sucursal"]}: {_cop(r["ingreso"])}' for r in por_sucursal)

    return f"""
  <div class="venta-hoy">
    <div class="venta-hoy-label">Venta hoy · {k["num_transacciones"]} transacciones</div>
    <div class="venta-hoy-valor">{_cop(hoy_val)}</div>
    <div class="venta-hoy-comp">Ayer: {_cop(ayer)} &nbsp;{comparativo}</div>
    <div class="venta-hoy-desglose">{desglose}</div>
  </div>"""


def _seccion_inventario(inv: dict) -> str:
    if not inv:
        return '<div class="nota">Inventario aún no procesado. Corre scripts/procesar_inventario.py.</div>'

    kpis_inv = "".join([
        _tarjeta_kpi("Artículos activos", _miles(inv["total_articulos"])),
        _tarjeta_kpi("Sin stock", _miles(inv["articulos_sin_stock"]), "de todas las sucursales"),
        _tarjeta_kpi("Unidades totales", _miles(inv["unidades_totales"])),
        _tarjeta_kpi("Valor inventario (costo)", _cop(inv["valor_total_costo"])),
    ])

    maximo_stock = max(inv["stock_por_sucursal"].values(), default=1)
    stock_html = "".join([
        _fila_stock(nombre, unidades, maximo_stock)
        for nombre, unidades in sorted(inv["stock_por_sucursal"].items(), key=lambda kv: -kv[1])
    ])

    filas_categorias = "".join(_fila_categoria_inventario(c) for c in inv["top_categorias_por_valor"])

    return f"""
  <h2>Inventario</h2>
  <div class="kpi-grid">{kpis_inv}</div>

  <h3 class="subseccion">Stock por sucursal</h3>
  <div>{stock_html}</div>

  <h3 class="subseccion">Categorías con mayor valor en inventario</h3>
  <table class="tabla-categorias">
    <thead><tr><th>Categoría</th><th class="num">Artículos</th><th class="num">Unidades</th><th class="num">Valor a costo</th></tr></thead>
    <tbody>{filas_categorias}</tbody>
  </table>
  <div class="nota">
    Índice de cobertura por SKU (para sugerencia de pedidos a proveedores) pendiente:
    requiere cruzar este inventario con velocidad de venta por artículo — próxima iteración.
  </div>"""


def _seccion_comparativo_historico(historico_mensual: dict) -> str:
    if not historico_mensual:
        return ""

    filas = []
    for cod, data in historico_mensual.items():
        por_anio_mes = data["por_anio_mes"]
        anios_disponibles = sorted(por_anio_mes.keys())
        if len(anios_disponibles) < 1:
            continue
        anio_reciente = anios_disponibles[-1]
        anio_anterior = anios_disponibles[-2] if len(anios_disponibles) > 1 else None

        celdas = []
        for mes in MESES_ES:
            actual = por_anio_mes.get(anio_reciente, {}).get(mes)
            anterior = por_anio_mes.get(anio_anterior, {}).get(mes) if anio_anterior else None

            if not actual and not anterior:
                celdas.append('<td class="num hist-vacio">—</td>')
                continue

            partes = []
            if actual:
                partes.append(f'<div class="hist-actual">{_cop(actual["neto"])}</div>')
            else:
                partes.append('<div class="hist-actual hist-vacio">—</div>')
            if anterior:
                partes.append(f'<div class="hist-anterior">{_cop(anterior["neto"])}</div>')
                if actual and anterior["neto"]:
                    var = (actual["neto"] - anterior["neto"]) / anterior["neto"]
                    clase = "pos" if var >= 0 else "neg"
                    signo = "+" if var >= 0 else ""
                    partes.append(f'<div class="hist-var {clase}">{signo}{round(var * 100, 1)}%</div>')
            celdas.append(f'<td class="num">{"".join(partes)}</td>')

        filas.append(f'<tr><td class="hist-sucursal">{data["nombre"]}</td>{"".join(celdas)}</tr>')

    anios_todos = sorted({a for d in historico_mensual.values() for a in d["por_anio_mes"].keys()})
    etiqueta_anios = " vs ".join(anios_todos[-2:]) if len(anios_todos) > 1 else (anios_todos[0] if anios_todos else "")

    encabezado_meses = "".join(f"<th class='num'>{m}</th>" for m in MESES_ES)

    return f"""
  <h2>Comparativo histórico por sucursal</h2>
  <div class="subtitulo" style="margin-bottom:1rem;">{etiqueta_anios} · Total neto por mes</div>
  <div class="tabla-scroll">
  <table class="tabla-historico">
    <thead><tr><th>Sucursal</th>{encabezado_meses}</tr></thead>
    <tbody>{"".join(filas)}</tbody>
  </table>
  </div>"""


# ---------- generador principal ----------

def generar_dashboard_html(datos: dict = None) -> str:
    ventas = _cargar_json(REPORTES_DIR / "ventas_procesado.json")
    inventario = _cargar_json(REPORTES_DIR / "inventario_procesado.json")
    historico_mensual = _cargar_json(REPORTES_DIR / "historico_mensual.json")
    cat_ref = _cargar_json(REPORTES_DIR / "categorias_referencias.json")
    sucursales_cfg = _cargar_json(CONFIG_DIR / "sucursales.json", {"sucursales": []})["sucursales"]
    nombre_map = {s["nombre_effi"]: s["nombre"] for s in sucursales_cfg}

    if not ventas:
        return _html_sin_datos()

    anio = ventas["anio_actual"]
    mes = ventas["mes_actual"]
    hoy = ventas["hoy"]
    cartera = ventas["cartera"]

    unidades_anio = cat_ref["anio_actual"]["unidades_totales"] if cat_ref else None
    kpis_anio_html = _grupo_kpis(anio["kpis"], unidades_anio)
    kpis_mes_html = _grupo_kpis(mes["kpis"])

    venta_hoy_html = _seccion_venta_hoy(hoy, nombre_map)

    por_sucursal_anio = sorted(anio["por_sucursal"], key=lambda r: -r["ingreso"])
    maximo_suc = max((r["ingreso"] for r in por_sucursal_anio), default=1)
    sucursales_html = "".join([
        _fila_sucursal(r["sucursal"], r["ingreso"], r["transacciones"], maximo_suc)
        for r in por_sucursal_anio
    ])

    rentabilidad_html = ""
    referencias_html = ""
    if cat_ref:
        categorias = cat_ref["anio_actual"]["categorias"][:10]
        maximo_cat = max((c["ventas_netas"] for c in categorias), default=1)
        rentabilidad_html = "".join(_fila_categoria_rentabilidad(c, maximo_cat) for c in categorias)

        referencias = cat_ref["anio_actual"]["top_referencias"][:10]
        referencias_html = "".join(_fila_referencia(i + 1, r) for i, r in enumerate(referencias))

    comparativo_html = _seccion_comparativo_historico(historico_mensual)

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
    --destacado-bg: #ece5d8;
    --verde: #4d7358;
    --ambar: #a97b34;
    --rojo: #b0503f;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--texto);
    margin: 0;
    padding: 2.5rem 3rem;
  }}
  header {{ margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: .5rem; }}
  h1 {{
    font-family: Georgia, "Times New Roman", serif;
    letter-spacing: .04em;
    font-weight: 400;
    font-size: 1.9rem;
    margin: 0 0 .3rem 0;
    text-transform: uppercase;
  }}
  .subtitulo {{ color: var(--texto-sub); font-size: .95rem; }}
  .actualizado {{ color: var(--texto-sub); font-size: .8rem; text-align: right; }}
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
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
  }}
  .kpi-card {{
    background: var(--card);
    border: 1px solid var(--borde);
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
  }}
  .kpi-label {{ font-size: .8rem; color: var(--texto-sub); text-transform: uppercase; letter-spacing: .03em; }}
  .kpi-valor {{ font-size: 1.5rem; margin-top: .3rem; font-weight: 600; }}
  .kpi-sub {{ font-size: .78rem; color: var(--texto-sub); margin-top: .2rem; }}

  .venta-hoy {{
    margin-top: 1.5rem;
    background: var(--destacado-bg);
    border: 1px solid var(--acento-suave);
    border-radius: 12px;
    padding: 1.4rem 1.6rem;
  }}
  .venta-hoy-label {{ font-size: .78rem; text-transform: uppercase; letter-spacing: .03em; color: var(--texto-sub); }}
  .venta-hoy-valor {{ font-size: 2.4rem; font-weight: 700; margin: .2rem 0; }}
  .venta-hoy-comp {{ font-size: .9rem; color: var(--texto-sub); }}
  .venta-hoy-desglose {{ font-size: .85rem; color: var(--texto-sub); margin-top: .6rem; }}
  .pos {{ color: var(--verde); font-weight: 600; }}
  .neg {{ color: var(--rojo); font-weight: 600; }}

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
  .suc-barra-inv {{ background: #a89f8c; }}
  .suc-cifras {{ text-align: right; font-size: .92rem; font-variant-numeric: tabular-nums; }}
  .suc-trans {{ color: var(--texto-sub); font-size: .8rem; }}

  .cat-fila {{
    display: grid;
    grid-template-columns: 130px 1fr 60px 150px;
    align-items: center;
    gap: .8rem;
    padding: .55rem 0;
    border-bottom: 1px solid var(--borde);
  }}
  .cat-nombre {{ font-weight: 600; font-size: .85rem; }}
  .cat-barra-wrap {{ background: #ece7dd; border-radius: 6px; height: 10px; overflow: hidden; }}
  .cat-barra {{ height: 100%; border-radius: 6px; }}
  .cat-margen {{ font-size: .8rem; font-weight: 700; text-align: right; }}
  .cat-valor {{ text-align: right; font-size: .88rem; font-variant-numeric: tabular-nums; }}
  .cat-barra.margen-alto {{ background: var(--verde); }}
  .cat-barra.margen-medio {{ background: var(--ambar); }}
  .cat-barra.margen-bajo {{ background: var(--rojo); }}
  .cat-margen.margen-alto {{ color: var(--verde); }}
  .cat-margen.margen-medio {{ color: var(--ambar); }}
  .cat-margen.margen-bajo {{ color: var(--rojo); }}

  .ref-fila {{
    display: grid;
    grid-template-columns: 28px 1fr 90px 130px;
    align-items: center;
    gap: .8rem;
    padding: .5rem 0;
    border-bottom: 1px solid var(--borde);
    font-size: .88rem;
  }}
  .ref-rank {{ color: var(--texto-sub); font-weight: 700; }}
  .ref-nombre {{ font-weight: 500; }}
  .ref-unidades {{ color: var(--texto-sub); text-align: right; }}
  .ref-valor {{ text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }}

  .subseccion {{
    font-family: -apple-system, "Segoe UI", sans-serif;
    font-size: .85rem;
    text-transform: uppercase;
    letter-spacing: .03em;
    color: var(--texto-sub);
    margin: 1.8rem 0 .8rem 0;
    font-weight: 600;
  }}
  .tabla-categorias {{ width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--borde); border-radius: 10px; overflow: hidden; }}
  .tabla-categorias th, .tabla-categorias td {{ padding: .6rem 1rem; text-align: left; font-size: .88rem; border-bottom: 1px solid var(--borde); }}
  .tabla-categorias th {{ color: var(--texto-sub); text-transform: uppercase; font-size: .72rem; letter-spacing: .03em; font-weight: 600; }}
  .tabla-categorias td.num, .tabla-categorias th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .tabla-categorias tr:last-child td {{ border-bottom: none; }}

  .tabla-scroll {{ overflow-x: auto; border: 1px solid var(--borde); border-radius: 10px; background: var(--card); }}
  .tabla-historico {{ width: 100%; border-collapse: collapse; font-size: .78rem; min-width: 900px; }}
  .tabla-historico th, .tabla-historico td {{ padding: .5rem .6rem; border-bottom: 1px solid var(--borde); text-align: left; white-space: nowrap; }}
  .tabla-historico th {{ color: var(--texto-sub); text-transform: uppercase; font-size: .68rem; letter-spacing: .02em; font-weight: 600; position: sticky; top: 0; background: var(--card); }}
  .tabla-historico td.num {{ text-align: right; }}
  .tabla-historico tr:last-child td {{ border-bottom: none; }}
  .hist-sucursal {{ font-weight: 600; position: sticky; left: 0; background: var(--card); }}
  .hist-actual {{ font-weight: 600; }}
  .hist-anterior {{ color: var(--texto-sub); font-size: .85em; }}
  .hist-var {{ font-size: .85em; }}
  .hist-vacio {{ color: var(--acento-suave); }}

  .grid-2col {{ display: grid; grid-template-columns: 1.3fr 1fr; gap: 2rem; align-items: start; }}
  @media (max-width: 900px) {{ .grid-2col {{ grid-template-columns: 1fr; }} }}

  .nota {{
    margin-top: 1.5rem;
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
    <div>
      <h1>Divina Intuición</h1>
      <div class="subtitulo">Dashboard Gerencial de Ventas · Local 144 · Local 433 · Local 107 (Divina Accesorios)</div>
    </div>
    <div class="actualizado">Datos actualizados hasta<br>{ventas["actualizado_hasta"]}</div>
  </header>

  <h2>Indicadores clave · Año 2026</h2>
  <div class="kpi-grid">{kpis_anio_html}</div>
  {venta_hoy_html}

  <h2>Mes en curso</h2>
  <div class="kpi-grid">{kpis_mes_html}</div>

  <h2>Ventas por Punto de Venta · Año 2026</h2>
  <div>{sucursales_html}</div>

  <div class="grid-2col">
    <div>
      <h2>Rentabilidad por categoría · Año 2026</h2>
      <div>{rentabilidad_html}</div>
    </div>
    <div>
      <h2>Top referencias · ventas netas</h2>
      <div>{referencias_html}</div>
    </div>
  </div>

  {comparativo_html}

  {_seccion_inventario(inventario)}

  <div class="nota">
    Cartera: {_miles(cartera["num_pendiente_de_cobro"])} remisiones pendientes de cobro por {_cop(cartera["pendiente_de_cobro"])} ·
    {_miles(cartera["num_anuladas_historico"])} remisiones anuladas excluidas del histórico.
    Pendiente: escalafón de Comisiones (falta definir con el negocio) e índice de cobertura por SKU.
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
