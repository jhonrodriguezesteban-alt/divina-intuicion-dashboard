"""
Motor de generación del dashboard.html — un solo archivo estático, sin build step.
Ver JR ARQUITECTURA_REPLICABLE.md sección 4 para las trampas de f-strings/JS embebido.

v3: navegabilidad e interacciones calcadas del dashboard de referencia de
Grupo Bentley (menú hamburguesa con secciones, tarjetas de categoría y
referencia expandibles al clic, filtro de rango de fechas que recalcula
en JS puro, módulo de sugerencia de pedidos a proveedores con acordeón
por categoría) — pero con la paleta de grises claros / boutique de
Divina Intuición, no los colores neón del dashboard de referencia.

Todo el JS es un bloque estático (sin interpolación de Python) que lee
datos vía atributos data-* y un <script type="application/json"> — así
se evita por completo la trampa de comillas en f-strings con JS embebido
(sección 4.1 de la guía).

Pendiente: Comercial/Comisiones (falta escalafón del negocio).
"""

import base64
import json
from datetime import datetime
from pathlib import Path

REPORTES_DIR = Path(__file__).resolve().parent.parent / "reportes"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "dashboard.html"
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo_divina.png"
MARMOL_PATH = Path(__file__).resolve().parent.parent / "assets" / "marmol_textura.jpg"
ICONO_APP_PATH = Path(__file__).resolve().parent.parent / "assets" / "icono_app.png"


def _logo_img_html(clase: str, alto: str) -> str:
    """<img> con el logo incrustado en base64 (un solo archivo HTML, sin dependencias externas)."""
    if not LOGO_PATH.exists():
        return ""
    b64 = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f'<img class="{clase}" src="data:image/png;base64,{b64}" style="height:{alto};width:auto;" alt="Divina Intuición">'


def _marmol_data_uri() -> str:
    if not MARMOL_PATH.exists():
        return ""
    b64 = base64.b64encode(MARMOL_PATH.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _icono_app_data_uri() -> str:
    """PNG cuadrado (logo sobre fondo crema, ver scripts/generar_icono_app.py) para
    favicon/apple-touch-icon -- así "Agregar a pantalla de inicio" en el celular
    muestra el logo real en vez de un ícono genérico o una captura recortada."""
    if not ICONO_APP_PATH.exists():
        return ""
    b64 = base64.b64encode(ICONO_APP_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _manifest_data_uri(icono_uri: str) -> str:
    if not icono_uri:
        return ""
    manifest = {
        "name": "Divina Intuición — Dashboard Gerencial",
        "short_name": "Divina Intuición",
        "start_url": ".",
        "display": "standalone",
        "background_color": "#f4f1ec",
        "theme_color": "#f4f1ec",
        "icons": [{"src": icono_uri, "sizes": "512x512", "type": "image/png"}],
    }
    b64 = base64.b64encode(json.dumps(manifest, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return f"data:application/manifest+json;base64,{b64}"

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _opciones_mes_filtro(ventas_diarias: dict, anio_num: int) -> str:
    """<option> por cada mes del año en curso con datos en ventas_diarias.json,
    para el selector "Filtrar por mes" de Ventas por Punto de Venta."""
    meses_presentes = sorted({d[:7] for d in ventas_diarias.get("por_dia", {}) if d.startswith(str(anio_num))})
    opciones = []
    for ym in meses_presentes:
        mes_num = int(ym.split("-")[1])
        opciones.append(f'<option value="{ym}">{MESES_ES[mes_num - 1]} {anio_num}</option>')
    return "".join(opciones)


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


def _fila_sucursal(nombre: str, ingreso: float, transacciones: int, maximo: float, pct_total: float = None) -> str:
    pct_txt = f' · {pct_total:.0f}% del total' if pct_total is not None else ''
    return _fila_barra(nombre, ingreso, f'{_cop(ingreso)} <span class="suc-trans">· {_miles(transacciones)} ventas{pct_txt}</span>', maximo)


def _fila_stock(nombre: str, unidades: int, maximo: int) -> str:
    return _fila_barra(nombre, unidades, f"{_miles(unidades)} unidades", maximo, "suc-barra-inv")


def _clase_margen(margen: float) -> str:
    """Umbrales calcados del dashboard de referencia (Grupo Bentley): >=30% verde, >=10% ámbar, si no rojo."""
    if margen >= 0.30:
        return "margen-alto"
    if margen >= 0.10:
        return "margen-medio"
    return "margen-bajo"


def _detalle_categoria_html(productos: list) -> str:
    if not productos:
        return '<div class="detalle-vacio">Sin detalle de productos.</div>'
    filas = "".join(
        f'<div class="detalle-item"><span>{p["nombre"].title()}</span>'
        f'<span>{_miles(p["unidades"])} und. · {_cop(p["ventas_netas"])}</span></div>'
        for p in productos
    )
    return f'<div class="cat-detalle"><div class="detalle-titulo">Top productos de la categoría</div>{filas}</div>'


def _fila_categoria_rentabilidad(cat: dict, maximo_margen: float, productos_por_categoria: dict) -> str:
    """El orden de las categorías es por ventas (de mayor a menor), pero el largo de la
    barra representa el MARGEN relativo al máximo margen del grupo — igual que el
    dashboard de referencia: la barra comunica rentabilidad, no volumen de venta."""
    pct_barra = round((cat["margen"] / maximo_margen) * 100, 1) if maximo_margen else 0
    clase = _clase_margen(cat["margen"])
    productos = productos_por_categoria.get(cat["categoria"], [])
    detalle = _detalle_categoria_html(productos)
    return f"""
    <div class="expandible cat-wrap" onclick="toggleAbierto(this)">
      <div class="cat-fila">
        <div class="cat-nombre"><span class="chevron">▶</span> {cat["categoria"]}</div>
        <div class="cat-barra-wrap">
          <div class="cat-barra {clase}" style="width:{pct_barra}%"></div>
        </div>
        <div class="cat-margen {clase}">{_pct(cat["margen"])}</div>
        <div class="cat-valor">{_cop(cat["ventas_netas"])}</div>
      </div>
      {detalle}
    </div>"""


def _detalle_referencia_html(por_sucursal: list) -> str:
    """Ventas por sucursal de una referencia; si esa sucursal vendió más de una
    talla/color de la referencia, la fila es clicable y despliega el detalle
    (mismo patrón de doble expandible que el módulo de Reorden: toggleAbierto
    con el evento para no disparar también el toggle de la fila padre)."""
    if not por_sucursal:
        return '<div class="detalle-vacio">Sin detalle por sucursal.</div>'
    filas = []
    for s in por_sucursal:
        variantes = s.get("variantes", [])
        tiene_variantes = len(variantes) > 1
        chevron = '<span class="chevron">▶</span> ' if tiene_variantes else ""
        clase_wrap = "ref-suc-wrap expandible" if tiene_variantes else "ref-suc-wrap"
        onclick = ' onclick="toggleAbierto(this, event)"' if tiene_variantes else ""
        nested = ""
        if tiene_variantes:
            items = "".join(
                f'<div class="detalle-item"><span>{v["nombre"]}</span>'
                f'<span>{_miles(v["unidades"])} und. · {_cop(v["ventas_netas"])}</span></div>'
                for v in variantes
            )
            nested = f'<div class="ref-variantes">{items}</div>'
        filas.append(f"""
      <div class="{clase_wrap}"{onclick}>
        <div class="detalle-item"><span>{chevron}{s["sucursal"]}</span>
        <span>{_miles(s["unidades"])} und. · {_cop(s["ventas_netas"])}</span></div>
        {nested}
      </div>""")
    return f'<div class="ref-detalle"><div class="detalle-titulo">Ventas por sucursal · clic para ver tallas/colores</div>{"".join(filas)}</div>'


def _fila_referencia(rank: int, ref: dict, por_sucursal_ref: dict) -> str:
    detalle = _detalle_referencia_html(por_sucursal_ref.get(ref["nombre"], []))
    return f"""
    <div class="expandible ref-wrap" onclick="toggleAbierto(this)">
      <div class="ref-fila">
        <div class="ref-rank">{rank}</div>
        <div class="ref-nombre"><span class="chevron">▶</span> {ref["nombre"].title()}</div>
        <div class="ref-unidades">{_miles(ref["unidades"])} und.</div>
        <div class="ref-valor">{_cop(ref["ventas_netas"])}</div>
      </div>
      {detalle}
    </div>"""


def _fila_categoria_inventario(cat: dict) -> str:
    return f"""
    <tr>
      <td>{cat["Categoría"]}</td>
      <td class="num">{_miles(cat["articulos"])}</td>
      <td class="num">{_miles(cat["stock_total"])}</td>
      <td class="num">{_cop(cat["valor_costo"])}</td>
    </tr>"""


# ---------- sección: venta de hoy + filtro de rango interactivo ----------

def _seccion_venta_hoy(hoy: dict) -> str:
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


def _seccion_ventas_recientes() -> str:
    return """
  <h2>Ventas recientes por sucursal</h2>
  <div class="filtro-rango">
    <button class="filtro-btn activo" data-desde="0" data-hasta="0" onclick="filtrarRango(0,0,this)">Hoy</button>
    <button class="filtro-btn" data-desde="1" data-hasta="1" onclick="filtrarRango(1,1,this)">Ayer</button>
    <button class="filtro-btn" data-desde="6" data-hasta="0" onclick="filtrarRango(6,0,this)">7 días</button>
    <button class="filtro-btn" data-desde="29" data-hasta="0" onclick="filtrarRango(29,0,this)">30 días</button>
  </div>
  <div class="subtitulo" style="margin:.8rem 0;">Total del rango: <strong id="ventas-recientes-total">—</strong></div>
  <div id="ventas-recientes-bars"></div>"""


def _seccion_composicion_venta(composicion: dict, margen: float) -> str:
    """Donut SVG hecho a mano (stroke-dasharray/dashoffset), igual técnica que el
    dashboard de referencia. Ahí mostraba Facturado vs Pendiente de facturar — en
    Divina esa distinción no aplica (todo queda "pendiente de facturar" en Effi),
    así que la composición real y útil es Cobrado (Pago total) vs Pendiente de cobro."""
    pago = composicion["pago_total"]
    pendiente = composicion["pendiente_cobro"]
    total = pago + pendiente
    if total <= 0:
        return '<div class="detalle-vacio">Sin datos de cartera para este período.</div>'

    pct_pago = pago / total * 100
    pct_pendiente = pendiente / total * 100
    circ = 2 * 3.14159265 * 70
    gap = 2
    arco_pago = max(0, pct_pago / 100 * circ - gap)
    arco_pendiente = max(0, pct_pendiente / 100 * circ - gap)
    offset_pendiente = -(pct_pago / 100 * circ)
    clase_margen = _clase_margen(margen)
    color_margen = {"margen-alto": "var(--verde)", "margen-medio": "var(--ambar)", "margen-bajo": "var(--rojo)"}[clase_margen]

    return f"""
    <div class="donut-container">
      <svg class="donut-svg" width="180" height="180" viewBox="0 0 180 180">
        <circle cx="90" cy="90" r="70" fill="none" stroke="var(--borde)" stroke-width="22"/>
        <circle cx="90" cy="90" r="70" fill="none" stroke="var(--verde)" stroke-width="22"
                stroke-dasharray="{arco_pago:.1f} {circ:.1f}" stroke-dashoffset="0" transform="rotate(-90 90 90)"/>
        <circle cx="90" cy="90" r="70" fill="none" stroke="var(--ambar)" stroke-width="22"
                stroke-dasharray="{arco_pendiente:.1f} {circ:.1f}" stroke-dashoffset="{offset_pendiente:.1f}" transform="rotate(-90 90 90)"/>
      </svg>
      <div class="donut-center">
        <div class="donut-pct" style="color:var(--verde)">{pct_pago:.1f}%</div>
        <div class="donut-sub-label">Cobrado</div>
      </div>
    </div>
    <div class="donut-legend">
      <div class="legend-item"><div class="legend-dot" style="background:var(--verde)"></div>
        <span class="legend-name">Pago total</span><span class="legend-pct">{pct_pago:.1f}%</span></div>
      <div class="legend-item"><div class="legend-dot" style="background:var(--ambar)"></div>
        <span class="legend-name">Pendiente de cobro</span><span class="legend-pct">{pct_pendiente:.1f}%</span></div>
      <div class="legend-item legend-item-separada">
        <div class="legend-dot" style="background:{color_margen}"></div>
        <span class="legend-name">Margen general</span>
        <span class="legend-pct" style="color:{color_margen}">{_pct(margen)}</span>
      </div>
    </div>"""


# ---------- sección: inventario + reorden ----------

def _seccion_inventario_resumen(inv: dict) -> str:
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
  <div class="kpi-grid">{kpis_inv}</div>

  <h3 class="subseccion">Stock por sucursal</h3>
  <div>{stock_html}</div>

  <h3 class="subseccion">Categorías con mayor valor en inventario</h3>
  <table class="tabla-categorias">
    <thead><tr><th>Categoría</th><th class="num">Artículos</th><th class="num">Unidades</th><th class="num">Valor a costo</th></tr></thead>
    <tbody>{filas_categorias}</tbody>
  </table>"""


def _badge_reorden(cantidad: int, etiqueta: str, clase: str) -> str:
    if cantidad <= 0:
        return ""
    return f'<span class="reo-badge {clase}">{cantidad} {etiqueta}</span>'


def _fila_reorden_ref(ref: dict) -> str:
    estado = ref["estado"]
    rot = f'{_miles(ref["rotacion_anualizada"])} uds/año' if ref["rotacion_anualizada"] else "sin ventas 90d"
    sug = f'+{_miles(ref["sugerido"])}' if ref["sugerido"] > 0 else "—"
    variantes = ref.get("variantes", [])
    tiene_tallas = len(variantes) > 1

    chevron = '<span class="chevron">▶</span> ' if tiene_tallas else ""
    conteo = f' <span class="reo-tallas-count">· {len(variantes)} tallas</span>' if tiene_tallas else ""
    detalle = ""
    if tiene_tallas:
        items = "".join(
            f'<div class="detalle-item"><span>{v["talla"]}</span><span>{_miles(v["disponible"])} disp.</span></div>'
            for v in variantes
        )
        detalle = f'<div class="reo-variantes">{items}</div>'

    clase_wrap = "reo-ref-wrap expandible" if tiene_tallas else "reo-ref-wrap"
    onclick = ' onclick="toggleAbierto(this, event)"' if tiene_tallas else ""

    return f"""
      <div class="{clase_wrap}"{onclick}>
        <div class="reo-fila">
          <div class="reo-nombre">{chevron}{ref["referencia"].title()}{conteo}</div>
          <div class="reo-disp">{_miles(ref["disponible"])} disp.</div>
          <div class="reo-rot">{rot}</div>
          <div class="reo-estado {estado}">{ref["estado_label"]}</div>
          <div class="reo-sug">{sug}</div>
        </div>
        {detalle}
      </div>"""


def _seccion_categoria_reorden(cat: dict) -> str:
    accionables = [r for r in cat["referencias"] if r["estado"] in ("critico", "alerta")]
    otros = len(cat["referencias"]) - len(accionables)
    filas = "".join(_fila_reorden_ref(r) for r in accionables)
    nota_otros = (
        f'<div class="detalle-vacio">+{_miles(otros)} referencias más sin alerta de cobertura (ok, sin rotación o nuevas).</div>'
        if otros > 0 else ""
    )
    if not accionables:
        filas = '<div class="detalle-vacio">Sin referencias críticas o en alerta en esta categoría.</div>'

    badges = (
        _badge_reorden(cat["num_criticos"], "crítico", "critico")
        + _badge_reorden(cat["num_alerta"], "alerta", "alerta")
        + (f'<span class="reo-badge sugerido">Sugerido: {_miles(cat["unidades_sugeridas"])} uds</span>' if cat["unidades_sugeridas"] > 0 else "")
    )

    return f"""
    <div class="expandible reo-cat-wrap" onclick="toggleAbierto(this)">
      <div class="reo-cat-header">
        <span class="chevron">▶</span>
        <span class="reo-cat-nombre">{cat["categoria"]}</span>
        <span class="reo-cat-meta">{_miles(cat["num_refs"])} refs · {_miles(cat["uds_disponibles"])} uds disponibles</span>
        {badges}
      </div>
      <div class="reo-cat-detalle">
        {filas}
        {nota_otros}
      </div>
    </div>"""


def _seccion_reorden(reorden: dict) -> str:
    if not reorden:
        return '<div class="nota">Sugerencia de pedidos aún no procesada. Corre scripts/procesar_reorden.py.</div>'

    r = reorden["resumen"]
    kpis_html = "".join([
        _tarjeta_kpi("Críticas", _miles(r["criticos"]), "cobertura ≤ 7 días"),
        _tarjeta_kpi("En alerta", _miles(r["alerta"]), "cobertura ≤ 30 días"),
        _tarjeta_kpi("Sin rotación 90d", _miles(r["sin_rotacion"]), "candidatas a liquidar"),
        _tarjeta_kpi("Nuevas / sin evaluar", _miles(r["nuevos"])),
        _tarjeta_kpi("Unidades sugeridas", _miles(r["unidades_sugeridas_total"]), "a pedir a proveedores"),
    ])

    categorias_html = "".join(_seccion_categoria_reorden(c) for c in reorden["categorias"])

    return f"""
  <h2>Solicitud de pedidos a proveedores</h2>
  <div class="subtitulo" style="margin-bottom:1rem;">
    Índice de cobertura calculado sobre venta de los últimos {reorden["ventana_dias"]} días, al {reorden["generado_al"]}.
    Clic en una categoría para ver las referencias que necesitan atención.
  </div>
  <div class="kpi-grid">{kpis_html}</div>
  <div style="margin-top:1.2rem;">{categorias_html}</div>"""


# ---------- sección: comparativo histórico ----------

MESES_UP = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def _hist_data_js(historico_mensual: dict) -> dict:
    """Reforma reportes/historico_mensual.json a la forma que consume el JS de
    renderHist (calcada del dashboard de referencia): {anio: {sucursal: {MES: valor, TOTAL: valor}}}."""
    hist = {}
    for data in historico_mensual.values():
        nombre = data["nombre"]
        for anio, meses in data["por_anio_mes"].items():
            bloque = hist.setdefault(anio, {}).setdefault(nombre, {})
            total = 0
            for mes_es, mes_up in zip(MESES_ES, MESES_UP):
                valor = meses.get(mes_es, {}).get("neto", 0)
                bloque[mes_up] = valor
                total += valor
            bloque["TOTAL"] = round(total, 2)
    return hist


def _metas_js(metas_cfg: dict, sucursales_cfg: list) -> dict:
    """config/metas_mensuales.json (por código de sucursal) -> {nombre_sucursal: {mes_idx: valor}},
    solo con los meses que el negocio fijó manualmente (el resto usa el respaldo +10% vs año anterior)."""
    nombre_por_codigo = {s["codigo"]: s["nombre"] for s in sucursales_cfg}
    metas = {}
    for codigo, meses in metas_cfg.items():
        if codigo.startswith("_") or not isinstance(meses, dict):
            continue
        nombre = nombre_por_codigo.get(codigo, codigo)
        limpio = {k: v for k, v in meses.items() if v is not None}
        if limpio:
            metas[nombre] = limpio
    return metas


def _seccion_comparativo_historico(historico_mensual: dict, metas_cfg: dict, sucursales_cfg: list, hoy: "datetime") -> str:
    if not historico_mensual:
        return ""

    hist_data = _hist_data_js(historico_mensual)
    metas = _metas_js(metas_cfg, sucursales_cfg)
    anios = sorted(hist_data.keys())
    if not anios:
        return ""
    anio_actual_str = str(hoy.year)
    anio_principal = anio_actual_str if anio_actual_str in anios else anios[-1]
    anio_comparar = str(int(anio_principal) - 1) if str(int(anio_principal) - 1) in anios else ""

    opciones_principal = "".join(
        f'<option value="{a}"{" selected" if a == anio_principal else ""}>{a}{" YTD" if a == anio_actual_str else ""}</option>'
        for a in reversed(anios)
    )
    opciones_cmp = '<option value="">Ninguno</option>' + "".join(
        f'<option value="{a}"{" selected" if a == anio_comparar else ""}>{a}</option>'
        for a in reversed(anios)
    )
    botones_mes = "".join(
        f'<button class="hmf-btn hmf-on" data-mes="{m}" onclick="togMes(\'{m}\',this)">{lbl}</button>'
        for m, lbl in zip(MESES_UP, MESES_ES)
    )

    datos_json = json.dumps({
        "histData": hist_data,
        "metas": metas,
        "meses": MESES_UP,
        "mesLabels": MESES_ES,
        "mesActual": hoy.month,
        "anioActual": anio_actual_str,
    }, ensure_ascii=False)

    return f"""
  <h2>Comparativo histórico por sucursal</h2>
  <div class="hist-controles">
    <div class="hist-selects">
      <label>Año principal <select id="hist-yr-main" onchange="renderHist()">{opciones_principal}</select></label>
      <label>Comparar con <select id="hist-yr-cmp" onchange="renderHist()">{opciones_cmp}</select></label>
    </div>
    <div id="hist-legend" class="hist-legend"></div>
  </div>
  <div class="hist-meses">
    {botones_mes}
    <button class="hmf-btn hmf-todos" onclick="selAllMes()">Todos</button>
  </div>
  <div class="tabla-scroll">
    <table class="tabla-historico" id="hist-table"></table>
  </div>
  <div class="nota">
    Las celdas en gris con "META" son meses sin cerrar o sin meta fijada manualmente en
    config/metas_mensuales.json — se calculan automáticamente como +10% de lo vendido ese
    mismo mes el año anterior, igual que el dashboard de referencia.
  </div>
  <script type="application/json" id="data-historico">{datos_json}</script>"""


# ---------- sección: comisiones ----------

def _seccion_comisiones(comisiones_cfg: dict, sucursales_cfg: list, hoy: "datetime") -> str:
    """Tarjetas por sucursal (meta/venta/% cumplimiento/comisión + mini gráfico
    presupuesto vs. real acumulado), calcadas del módulo "Comisiones Asesoras" del
    dashboard de referencia. A diferencia de Bentley (escalafón 0.5%-3% por asesora),
    Divina paga una tasa plana a la administradora de cada punto -- ver
    config/comisiones_config.json. Todo el cálculo día a día corre en JS puro sobre
    los datos ya embebidos (data-diarias, data-historico), sin generar un JSON nuevo
    por mes -- mismo patrón de la sección de filtros de Ventas por Punto de Venta."""
    if not comisiones_cfg:
        return '<div class="nota">Falta config/comisiones_config.json (tasa de comisión y administradoras por sucursal).</div>'

    tasa = comisiones_cfg.get("tasa_comision", 0.01)
    admins_por_codigo = comisiones_cfg.get("administradoras", {})
    nombre_por_codigo = {s["codigo"]: s["nombre"] for s in sucursales_cfg}
    administradoras = {nombre_por_codigo.get(cod, cod): nom for cod, nom in admins_por_codigo.items()}

    botones_mes = "".join(
        f'<button class="com-mes-btn{" com-mes-on" if i + 1 == hoy.month else ""}" '
        f'data-mes="{i + 1}" onclick="renderComisiones({i + 1}, this)">{MESES_ES[i]}</button>'
        for i in range(hoy.month)
    )

    comisiones_json = json.dumps({"tasaComision": tasa, "administradoras": administradoras}, ensure_ascii=False)

    return f"""
  <h2>Comisiones · Administradoras de punto</h2>
  <div class="subtitulo" style="margin-bottom:1.2rem;">
    Comisión del {tasa * 100:.0f}% sobre la venta neta del mes (Estado CXC = Pago total),
    medida contra la meta fijada en config/metas_mensuales.json.
  </div>
  <div class="com-meses">{botones_mes}</div>
  <div class="com-total-card">
    <div class="kpi-label" id="comisiones-total-label">Total comisiones</div>
    <div class="com-total-valor" id="comisiones-total">—</div>
  </div>
  <div class="com-grid" id="comisiones-tarjetas"></div>
  <script type="application/json" id="data-comisiones">{comisiones_json}</script>
  <script>document.addEventListener('DOMContentLoaded', function(){{ renderComisiones({hoy.month}); }});</script>"""


# ---------- login (pantalla de acceso, protección de fricción — ver nota en el README) ----------
# Credenciales de acceso al dashboard (no las de Effi). Cambiar aquí si hace falta.
LOGIN_USUARIO = "divina"
LOGIN_CLAVE = "DivinaIntuicion2026"

_LOGIN_HTML = f"""
  <div class="login-overlay" id="login-overlay">
    <div class="login-card">
      {_logo_img_html("login-logo", "56px")}
      <div class="login-subtitulo">Dashboard Gerencial</div>
      <input type="text" id="login-usuario" placeholder="Usuario" autocomplete="username">
      <div class="login-pass-wrap">
        <input type="password" id="login-clave" placeholder="Contraseña" autocomplete="current-password">
        <span class="login-eye" onclick="togglePassVis()">👁</span>
      </div>
      <label class="login-recordar"><input type="checkbox" id="login-recordar"> Recordarme en este dispositivo</label>
      <button class="login-btn" onclick="doLogin()">Ingresar</button>
      <div class="login-error" id="login-error"></div>
    </div>
  </div>"""


# ---------- JS estático (sin interpolación de Python, ver docstring del módulo) ----------

_JS = """
function togglePassVis(){
  var el = document.getElementById('login-clave');
  el.type = (el.type === 'password') ? 'text' : 'password';
}

function _mostrarApp(){
  document.getElementById('login-overlay').style.display = 'none';
  document.getElementById('app-contenido').style.display = '';
}

function doLogin(){
  var usuario = document.getElementById('login-usuario').value.trim();
  var clave = document.getElementById('login-clave').value;
  if (usuario === LOGIN_USUARIO && clave === LOGIN_CLAVE){
    if (document.getElementById('login-recordar').checked){
      localStorage.setItem('divina_dashboard_auth', '1');
    }
    _mostrarApp();
  } else {
    document.getElementById('login-error').textContent = 'Usuario o contraseña incorrectos.';
  }
}

if (localStorage.getItem('divina_dashboard_auth') === '1'){
  document.addEventListener('DOMContentLoaded', _mostrarApp);
}

function cerrarSesion(){
  localStorage.removeItem('divina_dashboard_auth');
  document.getElementById('app-contenido').style.display = 'none';
  document.getElementById('login-overlay').style.display = '';
  document.getElementById('login-usuario').value = '';
  document.getElementById('login-clave').value = '';
}

function toggleAbierto(el, evt){
  if (evt) evt.stopPropagation();
  el.classList.toggle('abierto');
}

function toggleNav(){
  document.getElementById('nav-panel').classList.toggle('abierto');
  document.getElementById('nav-overlay').classList.toggle('abierto');
}
function closeNav(){
  document.getElementById('nav-panel').classList.remove('abierto');
  document.getElementById('nav-overlay').classList.remove('abierto');
}
function navTo(id){
  document.querySelectorAll('.seccion').forEach(function(s){ s.style.display = 'none'; });
  var target = document.getElementById('sec-' + id);
  if (target) target.style.display = '';
  document.querySelectorAll('.nav-item').forEach(function(n){ n.classList.remove('activo'); });
  var item = document.querySelector('.nav-item[data-nav="' + id + '"]');
  if (item) item.classList.add('activo');
  closeNav();
  window.scrollTo(0, 0);
}

function _cop(valor){
  return '$' + Math.round(valor).toLocaleString('es-CO');
}

function filtrarRango(diasDesde, diasHasta, btn){
  document.querySelectorAll('.filtro-btn').forEach(function(b){ b.classList.remove('activo'); });
  if (btn) btn.classList.add('activo');

  var diarios = JSON.parse(document.getElementById('data-diarias').textContent);
  var hoyRef = document.body.getAttribute('data-hoy');
  var hoy = new Date(hoyRef + 'T00:00:00');

  var totales = {};
  diarios.sucursales.forEach(function(s){ totales[s] = {ingreso: 0, transacciones: 0}; });

  for (var d = diasHasta; d <= diasDesde; d++){
    var fecha = new Date(hoy.getTime() - d * 86400000);
    var key = fecha.toISOString().slice(0, 10);
    var dia = diarios.por_dia[key];
    if (!dia) continue;
    Object.keys(dia).forEach(function(suc){
      if (!totales[suc]) totales[suc] = {ingreso: 0, transacciones: 0};
      totales[suc].ingreso += dia[suc].ingreso;
      totales[suc].transacciones += dia[suc].transacciones;
    });
  }

  var entries = Object.keys(totales).map(function(k){
    return {sucursal: k, ingreso: totales[k].ingreso, transacciones: totales[k].transacciones};
  });
  entries.sort(function(a, b){ return b.ingreso - a.ingreso; });
  var maximo = Math.max.apply(null, entries.map(function(e){ return e.ingreso; }).concat([1]));
  var totalGeneral = entries.reduce(function(s, e){ return s + e.ingreso; }, 0);

  var totalEl = document.getElementById('ventas-recientes-total');
  if (totalEl) totalEl.textContent = _cop(totalGeneral);

  var html = '';
  entries.forEach(function(e){
    var pct = maximo ? (e.ingreso / maximo * 100) : 0;
    html += '<div class="suc-fila"><div class="suc-nombre">' + e.sucursal + '</div>' +
      '<div class="suc-barra-wrap"><div class="suc-barra" style="width:' + pct + '%"></div></div>' +
      '<div class="suc-cifras">' + _cop(e.ingreso) + ' <span class="suc-trans">\\u00b7 ' + e.transacciones + ' ventas</span></div></div>';
  });
  var cont = document.getElementById('ventas-recientes-bars');
  if (cont) cont.innerHTML = html;
}

function _diaISO(fecha){
  return fecha.toISOString().slice(0, 10);
}

function _rangoFechasISO(desde, hasta){
  var dias = [];
  var d = new Date(desde.getTime());
  while (d <= hasta){
    dias.push(_diaISO(d));
    d.setDate(d.getDate() + 1);
  }
  return dias;
}

function _renderSucursalesFiltro(diasISO){
  var diarios = JSON.parse(document.getElementById('data-diarias').textContent);
  var totales = {};
  diarios.sucursales.forEach(function(s){ totales[s] = {ingreso: 0, transacciones: 0}; });
  var pago = 0, pendiente = 0;

  diasISO.forEach(function(key){
    var dia = diarios.por_dia[key];
    if (dia){
      Object.keys(dia).forEach(function(suc){
        if (!totales[suc]) totales[suc] = {ingreso: 0, transacciones: 0};
        totales[suc].ingreso += dia[suc].ingreso;
        totales[suc].transacciones += dia[suc].transacciones;
      });
    }
    var comp = diarios.composicion_por_dia[key];
    if (comp){ pago += comp.pago_total; pendiente += comp.pendiente_cobro; }
  });

  var entries = Object.keys(totales).map(function(k){
    return {sucursal: k, ingreso: totales[k].ingreso, transacciones: totales[k].transacciones};
  });
  entries.sort(function(a, b){ return b.ingreso - a.ingreso; });
  var maximo = Math.max.apply(null, entries.map(function(e){ return e.ingreso; }).concat([1]));
  var totalGeneral = entries.reduce(function(s, e){ return s + e.ingreso; }, 0);
  var totalTrans = entries.reduce(function(s, e){ return s + e.transacciones; }, 0);

  var html = '';
  entries.forEach(function(e){
    var pct = maximo ? (e.ingreso / maximo * 100) : 0;
    var pctTotal = totalGeneral ? (e.ingreso / totalGeneral * 100) : 0;
    html += '<div class="suc-fila"><div class="suc-nombre">' + e.sucursal + '</div>' +
      '<div class="suc-barra-wrap"><div class="suc-barra" style="width:' + pct + '%"></div></div>' +
      '<div class="suc-cifras">' + _cop(e.ingreso) + ' <span class="suc-trans">\\u00b7 ' + e.transacciones + ' ventas \\u00b7 ' + pctTotal.toFixed(0) + '% del total</span></div></div>';
  });
  if (html) html += '<div class="suc-total-linea"><span>Total</span><span>' + _cop(totalGeneral) + ' \\u00b7 ' + totalTrans + ' ventas</span></div>';
  var cont = document.getElementById('suc-punto-venta-bars');
  if (cont) cont.innerHTML = html || '<div class="detalle-vacio">Sin ventas en este período.</div>';

  _renderComposicionFiltro(pago, pendiente);
}

function _renderComposicionFiltro(pago, pendiente){
  var wrap = document.getElementById('composicion-wrap');
  if (!wrap) return;
  var total = pago + pendiente;
  if (total <= 0){
    wrap.innerHTML = '<div class="detalle-vacio">Sin datos de cartera para este período.</div>';
    return;
  }
  var pctPago = pago / total * 100, pctPendiente = pendiente / total * 100;
  var circ = 2 * Math.PI * 70, gap = 2;
  var arcoPago = Math.max(0, pctPago / 100 * circ - gap);
  var arcoPendiente = Math.max(0, pctPendiente / 100 * circ - gap);
  var offsetPendiente = -(pctPago / 100 * circ);
  wrap.innerHTML =
    '<div class="donut-container"><svg class="donut-svg" width="180" height="180" viewBox="0 0 180 180">' +
    '<circle cx="90" cy="90" r="70" fill="none" stroke="var(--borde)" stroke-width="22"/>' +
    '<circle cx="90" cy="90" r="70" fill="none" stroke="var(--verde)" stroke-width="22" stroke-dasharray="' + arcoPago.toFixed(1) + ' ' + circ.toFixed(1) + '" stroke-dashoffset="0" transform="rotate(-90 90 90)"/>' +
    '<circle cx="90" cy="90" r="70" fill="none" stroke="var(--ambar)" stroke-width="22" stroke-dasharray="' + arcoPendiente.toFixed(1) + ' ' + circ.toFixed(1) + '" stroke-dashoffset="' + offsetPendiente.toFixed(1) + '" transform="rotate(-90 90 90)"/>' +
    '</svg><div class="donut-center"><div class="donut-pct" style="color:var(--verde)">' + pctPago.toFixed(1) + '%</div><div class="donut-sub-label">Cobrado</div></div></div>' +
    '<div class="donut-legend">' +
    '<div class="legend-item"><div class="legend-dot" style="background:var(--verde)"></div><span class="legend-name">Pago total</span><span class="legend-pct">' + pctPago.toFixed(1) + '%</span></div>' +
    '<div class="legend-item"><div class="legend-dot" style="background:var(--ambar)"></div><span class="legend-name">Pendiente de cobro</span><span class="legend-pct">' + pctPendiente.toFixed(1) + '%</span></div>' +
    '</div>';
}

function _limpiarBotonesFiltroSuc(){
  document.querySelectorAll('.filtro-btn-suc').forEach(function(b){ b.classList.remove('activo'); });
}

function filtrarSucursales(diasDesde, diasHasta, btn){
  _limpiarBotonesFiltroSuc();
  if (btn) btn.classList.add('activo');
  document.getElementById('filtro-fecha-desde').value = '';
  document.getElementById('filtro-fecha-hasta').value = '';
  document.getElementById('filtro-mes-select').value = '';

  var hoyRef = document.body.getAttribute('data-hoy');
  var hoy = new Date(hoyRef + 'T00:00:00');
  var desde = new Date(hoy.getTime() - diasDesde * 86400000);
  var hasta = new Date(hoy.getTime() - diasHasta * 86400000);
  _renderSucursalesFiltro(_rangoFechasISO(desde, hasta));
}

function filtrarPorMes(valor){
  _limpiarBotonesFiltroSuc();
  document.getElementById('filtro-fecha-desde').value = '';
  document.getElementById('filtro-fecha-hasta').value = '';
  if (!valor){ limpiarFiltroSucursales(); return; }
  var partes = valor.split('-');
  var anio = parseInt(partes[0], 10), mes = parseInt(partes[1], 10);
  var desde = new Date(anio, mes - 1, 1);
  var hasta = new Date(anio, mes, 0);
  _renderSucursalesFiltro(_rangoFechasISO(desde, hasta));
}

function filtrarPorRangoFechas(){
  var desdeStr = document.getElementById('filtro-fecha-desde').value;
  var hastaStr = document.getElementById('filtro-fecha-hasta').value;
  if (!desdeStr || !hastaStr) return;
  _limpiarBotonesFiltroSuc();
  document.getElementById('filtro-mes-select').value = '';
  var desde = new Date(desdeStr + 'T00:00:00');
  var hasta = new Date(hastaStr + 'T00:00:00');
  if (hasta < desde) return;
  _renderSucursalesFiltro(_rangoFechasISO(desde, hasta));
}

function limpiarFiltroSucursales(){
  _limpiarBotonesFiltroSuc();
  document.getElementById('filtro-fecha-desde').value = '';
  document.getElementById('filtro-fecha-hasta').value = '';
  document.getElementById('filtro-mes-select').value = '';
  var diarios = JSON.parse(document.getElementById('data-diarias').textContent);
  var anioActual = new Date(document.body.getAttribute('data-hoy') + 'T00:00:00').getFullYear();
  var dias = Object.keys(diarios.por_dia).filter(function(d){ return d.slice(0, 4) === String(anioActual); }).sort();
  _renderSucursalesFiltro(dias);
}

function _histCop(v){
  if (!v || v === 0) return '\\u2014';
  return '$' + Math.round(v).toLocaleString('es-CO');
}

function colorSelect(el){
  var c = el.id === 'hist-yr-main' ? 'var(--acento)' : 'var(--ambar)';
  el.style.color = c;
  el.style.borderColor = c;
}

function _histYrLabel(yr, anioActual){
  return yr === anioActual ? yr + ' YTD' : yr;
}

function updateLegend(yr, cmp){
  var el = document.getElementById('hist-legend');
  if (!el) return;
  var d = JSON.parse(document.getElementById('data-historico').textContent);
  var h = '<span style="color:var(--acento)">\\u25a0 ' + _histYrLabel(yr, d.anioActual) + '</span>';
  if (cmp) h += ' <span style="color:var(--texto-sub)">vs</span> <span style="color:var(--ambar)">\\u25a0 ' + _histYrLabel(cmp, d.anioActual) + '</span>';
  el.innerHTML = h;
}

var visibleMes = (function(){
  var el = document.getElementById('data-historico');
  return el ? new Set(JSON.parse(el.textContent).meses) : new Set();
})();

function togMes(m, btn){
  if (visibleMes.has(m)) { visibleMes.delete(m); btn.classList.remove('hmf-on'); }
  else { visibleMes.add(m); btn.classList.add('hmf-on'); }
  renderHist();
}

function selAllMes(){
  var d = JSON.parse(document.getElementById('data-historico').textContent);
  visibleMes = new Set(d.meses);
  document.querySelectorAll('.hmf-btn[data-mes]').forEach(function(b){ b.classList.add('hmf-on'); });
  renderHist();
}

function renderHist(){
  var datosEl = document.getElementById('data-historico');
  if (!datosEl) return;
  var datos = JSON.parse(datosEl.textContent);
  var selM = document.getElementById('hist-yr-main');
  var selC = document.getElementById('hist-yr-cmp');
  var yr = selM.value, cmp = selC.value;
  colorSelect(selM); colorSelect(selC);
  updateLegend(yr, cmp);

  var MD = datos.histData[yr] || {};
  var CD = cmp ? (datos.histData[cmp] || {}) : null;
  var MESES = datos.meses, MES_LABELS = datos.mesLabels, MES_ACTUAL = datos.mesActual;
  var ANIO_ACTUAL = datos.anioActual, METAS = datos.metas;
  var yc = 'var(--acento)', cc = 'var(--ambar)';

  var visMes = MESES.filter(function(m){ return visibleMes.has(m); });
  var visMesLbl = MES_LABELS.filter(function(_, i){ return visibleMes.has(MESES[i]); });

  function sucTotal(sd){
    var t = 0; visMes.forEach(function(m){ var v = (sd || {})[m] || 0; if (v > 0) t += v; }); return t;
  }
  var sucs = Object.keys(MD).sort(function(a, b){ return sucTotal(MD[b]) - sucTotal(MD[a]); });

  var h = '<thead><tr><th class="hist-th-suc">SUCURSAL</th>';
  visMesLbl.forEach(function(lbl){ h += '<th>' + lbl + '</th>'; });
  h += '<th>TOTAL</th></tr></thead><tbody>';

  sucs.forEach(function(s){
    h += '<tr><td class="hist-td-suc">' + s + '</td>';
    visMes.forEach(function(m){
      var v = (MD[s] || {})[m] || 0;
      var vc = CD ? ((CD[s] || {})[m] || 0) : 0;
      var mIdx = MESES.indexOf(m) + 1;
      var vPrevYear = ((datos.histData[String(Number(yr) - 1)] || {})[s] || {})[m] || 0;
      var mr = METAS[s], hayMeta = mr !== undefined && mr[mIdx] !== undefined;
      var metaV = (hayMeta && mIdx <= 12) ? mr[mIdx] : vPrevYear * 1.10;

      if (yr === ANIO_ACTUAL) {
        if (mIdx > MES_ACTUAL || v === 0) {
          h += metaV > 0
            ? '<td class="hist-td-meta"><span class="hist-v-meta">' + _histCop(metaV) + '</span><span class="hist-meta-lbl"> META</span></td>'
            : '<td class="hist-td-meta">\\u2014</td>';
        } else {
          var cell = '<span class="hist-v-main" style="color:' + yc + '">' + _histCop(v) + '</span>';
          if (CD && vc > 0) {
            var p = (v - vc) / vc * 100, cl = p >= 0 ? 'hist-var-up' : 'hist-var-dn';
            cell += '<span class="hist-v-cmp" style="color:' + cc + '">' + _histCop(vc) + '</span><span class="' + cl + '">' + (p >= 0 ? '+' : '') + p.toFixed(1) + '%</span>';
          } else if (metaV > 0) {
            var p2 = (v / metaV - 1) * 100, cl2 = p2 >= 0 ? 'hist-var-up' : 'hist-var-dn';
            cell += '<span class="hist-v-cmp">' + _histCop(metaV) + '</span><span class="' + cl2 + '">' + (p2 >= 0 ? '+' : '') + p2.toFixed(1) + '%</span>';
          }
          h += '<td>' + cell + '</td>';
        }
      } else {
        var cell2 = '<span class="hist-v-main" style="color:' + yc + '">' + _histCop(v) + '</span>';
        if (CD) {
          cell2 += '<span class="hist-v-cmp" style="color:' + cc + '">' + _histCop(vc) + '</span>';
          if (vc > 0) {
            var p3 = (v - vc) / vc * 100, cl3 = p3 >= 0 ? 'hist-var-up' : 'hist-var-dn';
            cell2 += '<span class="' + cl3 + '">' + (p3 >= 0 ? '+' : '') + p3.toFixed(1) + '%</span>';
          }
        }
        h += '<td>' + cell2 + '</td>';
      }
    });

    var vt = 0, vtc = 0;
    visMes.forEach(function(m){
      var mv = (MD[s] || {})[m] || 0; if (mv > 0) vt += mv;
      if (CD) { var mvc = (CD[s] || {})[m] || 0; if (mvc > 0) vtc += mvc; }
    });
    var tc = '<span class="hist-v-main" style="color:' + yc + '">' + _histCop(vt) + '</span>';
    if (CD) {
      tc += '<span class="hist-v-cmp" style="color:' + cc + '">' + _histCop(vtc) + '</span>';
      if (vtc > 0) {
        var p4 = (vt - vtc) / vtc * 100, cl4 = p4 >= 0 ? 'hist-var-up' : 'hist-var-dn';
        tc += '<span class="' + cl4 + '">' + (p4 >= 0 ? '+' : '') + p4.toFixed(1) + '%</span>';
      }
    }
    h += '<td>' + tc + '</td></tr>';
  });

  h += '</tbody><tfoot><tr><td>TOTAL MES</td>';
  visMes.forEach(function(m){
    var t = 0, tc2 = 0;
    sucs.forEach(function(s){ t += (MD[s] || {})[m] || 0; if (CD) tc2 += (CD[s] || {})[m] || 0; });
    var mIdxF = MESES.indexOf(m) + 1;
    if (yr === ANIO_ACTUAL) {
      var tMeta = 0;
      sucs.forEach(function(s){
        var v25s = ((datos.histData[String(Number(yr) - 1)] || {})[s] || {})[m] || 0;
        var mr2 = METAS[s], hayMeta2 = mr2 !== undefined && mr2[mIdxF] !== undefined;
        tMeta += (hayMeta2 && mIdxF <= 12) ? mr2[mIdxF] : v25s * 1.10;
      });
      if (mIdxF > MES_ACTUAL || t === 0) {
        h += tMeta > 0
          ? '<td class="hist-td-meta"><span class="hist-v-meta">' + _histCop(tMeta) + '</span><span class="hist-meta-lbl"> META</span></td>'
          : '<td class="hist-td-meta">\\u2014</td>';
      } else {
        var fc = '<span style="color:' + yc + '">' + _histCop(t) + '</span>';
        if (CD && tc2 > 0) {
          var p5 = (t - tc2) / tc2 * 100, cl5 = p5 >= 0 ? 'hist-var-up' : 'hist-var-dn';
          fc += '<span class="hist-v-cmp" style="color:' + cc + '">' + _histCop(tc2) + '</span><span class="' + cl5 + '">' + (p5 >= 0 ? '+' : '') + p5.toFixed(1) + '%</span>';
        } else if (tMeta > 0) {
          var p6 = (t / tMeta - 1) * 100, cl6 = p6 >= 0 ? 'hist-var-up' : 'hist-var-dn';
          fc += '<span class="hist-v-cmp">' + _histCop(tMeta) + '</span><span class="' + cl6 + '">' + (p6 >= 0 ? '+' : '') + p6.toFixed(1) + '%</span>';
        }
        h += '<td>' + fc + '</td>';
      }
    } else {
      var fc2 = '<span style="color:' + yc + '">' + _histCop(t) + '</span>';
      if (CD && tc2 > 0) fc2 += '<span class="hist-v-cmp" style="color:' + cc + '">' + _histCop(tc2) + '</span>';
      h += '<td>' + fc2 + '</td>';
    }
  });

  var g = 0, gc = 0;
  sucs.forEach(function(s){
    visMes.forEach(function(m){ var mv2 = (MD[s] || {})[m] || 0; if (mv2 > 0) g += mv2; });
    if (CD) visMes.forEach(function(m){ var mvc2 = (CD[s] || {})[m] || 0; if (mvc2 > 0) gc += mvc2; });
  });
  var gfc = '<span style="color:' + yc + '">' + _histCop(g) + '</span>';
  if (CD && gc > 0) gfc += '<span class="hist-v-cmp" style="color:' + cc + '">' + _histCop(gc) + '</span>';
  h += '<td>' + gfc + '</td></tr></tfoot>';

  document.getElementById('hist-table').innerHTML = h;
}

if (document.getElementById('hist-table')) renderHist();

function _comisionLineChart(puntos, meta, diasEnMes){
  var w = 400, h = 130, padL = 4, padR = 6, padT = 10, padB = 18;
  var plotW = w - padL - padR, plotH = h - padT - padB;
  var ultimoReal = puntos.length ? puntos[puntos.length - 1].real : 0;
  var maxVal = Math.max(meta, ultimoReal, 1) * 1.05;

  function xFor(d){ return padL + (d - 1) / Math.max(1, diasEnMes - 1) * plotW; }
  function yFor(v){ return padT + plotH - (v / maxVal) * plotH; }

  var presupuestoPts = xFor(1) + ',' + yFor(meta / diasEnMes) + ' ' + xFor(diasEnMes) + ',' + yFor(meta);
  var realPts = puntos.map(function(p){ return xFor(p.dia) + ',' + yFor(p.real); }).join(' ');
  var dotX = puntos.length ? xFor(puntos[puntos.length - 1].dia) : padL;
  var dotY = puntos.length ? yFor(ultimoReal) : (padT + plotH);

  var ejeX = [1, Math.round(diasEnMes / 2), diasEnMes].map(function(d){
    return '<text x="' + xFor(d) + '" y="' + (h - 3) + '" class="com-chart-eje" text-anchor="middle">' + d + '</text>';
  }).join('');

  return '<svg viewBox="0 0 ' + w + ' ' + h + '" class="com-chart" preserveAspectRatio="none">' +
    ejeX +
    '<polyline points="' + presupuestoPts + '" fill="none" stroke="var(--verde)" stroke-width="2" stroke-dasharray="6 4"/>' +
    '<polyline points="' + realPts + '" fill="none" stroke="var(--acento)" stroke-width="2.5"/>' +
    '<circle cx="' + dotX + '" cy="' + dotY + '" r="4" fill="var(--acento)"/>' +
    '</svg>';
}

function _tarjetaComision(suc, admin, tasaPct, venta, meta, comision, puntos, diaCorte, mesLbl, diasEnMes, esMesActual){
  if (meta <= 0 && venta <= 0){
    return '<div class="comision-card"><div class="comision-card-top"><span class="comision-suc">' + suc + '</span></div>' +
      '<div class="detalle-vacio">Sin datos ni meta fijada para este mes.</div></div>';
  }
  var sinMeta = meta <= 0;
  var pct = sinMeta ? null : (venta / meta * 100);
  var claseP = sinMeta ? '' : (pct >= 100 ? 'pos' : (pct >= 70 ? '' : 'neg'));
  var pctTxt = sinMeta ? '—' : pct.toFixed(1) + '%';
  var barraPct = sinMeta ? 0 : Math.max(0, Math.min(100, pct));
  var deberiamos = meta * (diaCorte / diasEnMes);
  var diff = venta - deberiamos;

  var avance;
  if (sinMeta){
    avance = '<div class="comision-avance-sub">Sin meta de referencia este mes</div>' +
      '<div class="comision-avance-meta"><span class="comision-meta-txt">Fija una meta manual en config/metas_mensuales.json para comparar el ritmo.</span></div>';
  } else if (esMesActual){
    avance = '<div class="comision-avance-sub">Primeros ' + diaCorte + ' días de ' + mesLbl + '</div>' +
      '<div class="comision-avance-meta">' + (diff >= 0
        ? '<span class="pos">✓ Vas ' + _cop(Math.abs(diff)) + ' arriba del ritmo</span>'
        : '<span class="neg">⚠ Deberíamos tener ' + _cop(deberiamos) + ' · Falta ' + _cop(Math.abs(diff)) + '</span>') + '</div>';
  } else {
    avance = '<div class="comision-avance-sub">Mes cerrado</div>' +
      '<div class="comision-avance-meta">' + (venta >= meta
        ? '<span class="pos">✓ Meta cumplida</span>'
        : '<span class="neg">No se alcanzó la meta (' + pct.toFixed(1) + '%)</span>') + '</div>';
  }

  return '<div class="comision-card">' +
    '<div class="comision-card-top"><span class="comision-suc">' + suc + '</span><span class="comision-pct ' + claseP + '">' + pctTxt + '</span></div>' +
    '<div class="comision-cifras">' + _cop(venta) + ' <span class="comision-meta-txt">/ ' + (sinMeta ? 'sin meta' : _cop(meta)) + '</span></div>' +
    '<div class="comision-barra-wrap"><div class="comision-barra" style="width:' + barraPct + '%"></div></div>' +
    '<div class="comision-admin"><span>' + admin + '</span><span>' + pctTxt + '</span></div>' +
    '<div class="comision-desglose">' +
      '<div><span class="comision-desglose-lbl">Meta</span><span>' + (sinMeta ? '—' : _cop(meta)) + '</span></div>' +
      '<div><span class="comision-desglose-lbl">Venta</span><span>' + _cop(venta) + '</span></div>' +
      '<div><span class="comision-desglose-lbl">% Comisión</span><span>' + tasaPct + '%</span></div>' +
      '<div><span class="comision-desglose-lbl">Comisión</span><span class="pos">' + _cop(comision) + '</span></div>' +
    '</div>' +
    '<div class="comision-total-linea">Total comisión ' + suc + '<span class="pos">' + _cop(comision) + '</span></div>' +
    '<div class="comision-chart-legend"><span><i class="com-dot-dash"></i>Presupuesto</span><span><i class="com-dot-solid"></i>Real acumulado</span></div>' +
    _comisionLineChart(puntos, meta, diasEnMes) +
    avance +
  '</div>';
}

function renderComisiones(mesIdx, btn){
  var cfgEl = document.getElementById('data-comisiones');
  var histEl = document.getElementById('data-historico');
  var diariosEl = document.getElementById('data-diarias');
  if (!cfgEl || !histEl || !diariosEl) return;

  document.querySelectorAll('.com-mes-btn').forEach(function(b){ b.classList.remove('com-mes-on'); });
  if (btn) btn.classList.add('com-mes-on');

  var cfg = JSON.parse(cfgEl.textContent);
  var hist = JSON.parse(histEl.textContent);
  var diarios = JSON.parse(diariosEl.textContent);

  var anioActual = hist.anioActual;
  var histActual = hist.histData[anioActual] || {};
  var histPrev = hist.histData[String(Number(anioActual) - 1)] || {};
  var mesUp = hist.meses[mesIdx - 1];
  var mesLbl = hist.mesLabels[mesIdx - 1];
  var hoy = new Date(document.body.getAttribute('data-hoy') + 'T00:00:00');
  var esMesActual = (mesIdx === hoy.getMonth() + 1) && (Number(anioActual) === hoy.getFullYear());
  var diasEnMes = new Date(Number(anioActual), mesIdx, 0).getDate();
  var diaCorte = esMesActual ? hoy.getDate() : diasEnMes;
  var tasaPct = (cfg.tasaComision * 100).toFixed(cfg.tasaComision * 100 % 1 === 0 ? 0 : 1);

  var totalComisiones = 0;
  var tarjetas = '';

  diarios.sucursales.forEach(function(suc){
    var venta = (histActual[suc] || {})[mesUp] || 0;
    var metaCfg = hist.metas[suc];
    var metaManual = metaCfg && metaCfg[mesIdx] !== undefined ? metaCfg[mesIdx] : null;
    var ventaPrevYear = (histPrev[suc] || {})[mesUp] || 0;
    var meta = metaManual !== null ? metaManual : ventaPrevYear * 1.10;

    var puntos = [];
    var acumulado = 0;
    for (var d = 1; d <= diaCorte; d++){
      var key = anioActual + '-' + String(mesIdx).padStart(2, '0') + '-' + String(d).padStart(2, '0');
      var dia = diarios.por_dia[key];
      if (dia && dia[suc]) acumulado += dia[suc].ingreso;
      puntos.push({dia: d, real: acumulado});
    }

    var comision = venta * cfg.tasaComision;
    totalComisiones += comision;

    tarjetas += _tarjetaComision(suc, cfg.administradoras[suc] || ('Administradora ' + suc), tasaPct, venta, meta, comision, puntos, diaCorte, mesLbl, diasEnMes, esMesActual);
  });

  var totalEl = document.getElementById('comisiones-total');
  if (totalEl) totalEl.textContent = _cop(totalComisiones);
  var lblEl = document.getElementById('comisiones-total-label');
  if (lblEl) lblEl.textContent = 'Total comisiones ' + mesLbl + ' ' + anioActual;
  var cont = document.getElementById('comisiones-tarjetas');
  if (cont) cont.innerHTML = tarjetas;
}

filtrarRango(0, 0, document.querySelector('.filtro-btn[data-desde="0"][data-hasta="0"]'));
"""


# ---------- CSS estático ----------

_CSS = """
  :root {
    --bg: #f4f1ec;
    --card: #ffffff;
    --borde: #e6e1d8;
    --texto: #2b2823;
    --texto-sub: #8a8377;
    --acento: #33302a;
    --acento-suave: #cbc3b3;
    --destacado-bg: #ece5d8;
    --verde: #4d7358;
    --verde-bg: #e3ebe4;
    --ambar: #a97b34;
    --ambar-bg: #f3e6d0;
    --rojo: #b0503f;
    --rojo-bg: #f4ded9;
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--texto);
    margin: 0;
    padding: 2.5rem 3rem 4rem;
  }
  header.header-top { margin-bottom: 0; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; }
  .header-badges { display: flex; align-items: center; gap: .7rem; }
  .live-badge {
    display: flex; align-items: center; gap: .45rem; font-size: .74rem; color: var(--texto-sub);
    text-transform: uppercase; letter-spacing: .04em; padding: .4rem .8rem;
    border: 1px solid var(--borde); border-radius: 999px; background: var(--card);
  }
  .live-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--verde); animation: pulso-vivo 1.8s infinite; }
  @keyframes pulso-vivo {
    0% { box-shadow: 0 0 0 0 rgba(77, 115, 88, .55); }
    70% { box-shadow: 0 0 0 8px rgba(77, 115, 88, 0); }
    100% { box-shadow: 0 0 0 0 rgba(77, 115, 88, 0); }
  }
  .logout-btn {
    padding: .5rem 1rem; border-radius: 999px; border: 1px solid var(--borde);
    background: var(--card); color: var(--texto); font-size: .78rem; cursor: pointer;
  }
  .logout-btn:hover { background: var(--destacado-bg); }
  .marca-central { display: flex; flex-direction: column; align-items: center; text-align: center; margin: 1.6rem 0 2.4rem; }
  .logo-central { display: block; margin: 0 auto .9rem; }
  .marca-actualizado { display: flex; align-items: baseline; gap: .5rem; font-size: .85rem; color: var(--texto-sub); }
  .marca-actualizado-label { text-transform: uppercase; letter-spacing: .04em; font-size: .72rem; }
  .marca-actualizado-valor { font-weight: 600; color: var(--texto); }
  .powered-by {
    text-align: center; margin-top: .6rem; padding-top: 1rem;
    font-size: .7rem; letter-spacing: .04em; color: var(--texto-sub); text-transform: uppercase;
  }
  .nav-hamburger {
    width: 42px; height: 42px; flex-shrink: 0;
    border-radius: 8px; border: 1px solid var(--borde);
    background: var(--card); cursor: pointer; font-size: 1.15rem;
  }
  .nav-hamburger:hover { background: var(--destacado-bg); }
  .nav-overlay {
    position: fixed; inset: 0; background: rgba(30, 27, 22, .35);
    opacity: 0; pointer-events: none; transition: opacity .2s; z-index: 40;
  }
  .nav-overlay.abierto { opacity: 1; pointer-events: auto; }
  .nav-panel {
    position: fixed; top: 0; left: 0; bottom: 0; width: 270px;
    background: var(--card); border-right: 1px solid var(--borde);
    transform: translateX(-104%); transition: transform .22s ease;
    z-index: 45; padding: 1.6rem 1rem; overflow-y: auto;
  }
  .nav-panel.abierto { transform: translateX(0); }
  .nav-panel-titulo { font-family: Georgia, serif; text-transform: uppercase; letter-spacing: .04em; font-size: 1rem; padding: 0 .6rem 1rem; }
  .nav-item {
    padding: .8rem .9rem; border-radius: 8px; cursor: pointer;
    font-size: .92rem; display: flex; align-items: center; gap: .7rem; color: var(--texto);
  }
  .nav-item:hover { background: var(--bg); }
  .nav-item.activo { background: var(--destacado-bg); font-weight: 600; }

  h1 {
    font-family: Georgia, "Times New Roman", serif;
    letter-spacing: .04em; font-weight: 400; font-size: 1.9rem;
    margin: 0 0 .3rem 0; text-transform: uppercase;
  }
  .subtitulo { color: var(--texto-sub); font-size: .95rem; }
  h2 {
    font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 1.2rem;
    text-transform: uppercase; letter-spacing: .03em;
    border-bottom: 1px solid var(--borde); padding-bottom: .5rem; margin: 2.5rem 0 1.2rem 0;
  }
  .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; }
  .kpi-card { background: var(--card); border: 1px solid var(--borde); border-radius: 10px; padding: 1.2rem 1.4rem; }
  .kpi-label { font-size: .8rem; color: var(--texto-sub); text-transform: uppercase; letter-spacing: .03em; }
  .kpi-valor { font-size: 1.5rem; margin-top: .3rem; font-weight: 600; }
  .kpi-sub { font-size: .78rem; color: var(--texto-sub); margin-top: .2rem; }

  .venta-hoy { margin-top: 1.5rem; background: var(--destacado-bg); border: 1px solid var(--acento-suave); border-radius: 12px; padding: 1.4rem 1.6rem; }
  .venta-hoy-label { font-size: .78rem; text-transform: uppercase; letter-spacing: .03em; color: var(--texto-sub); }
  .venta-hoy-valor { font-size: 2.4rem; font-weight: 700; margin: .2rem 0; }
  .venta-hoy-comp { font-size: .9rem; color: var(--texto-sub); }
  .venta-hoy-desglose { font-size: .85rem; color: var(--texto-sub); margin-top: .6rem; }
  .pos { color: var(--verde); font-weight: 600; }
  .neg { color: var(--rojo); font-weight: 600; }

  .filtro-rango { display: flex; gap: .5rem; flex-wrap: wrap; }
  .filtro-btn {
    padding: .5rem 1rem; border-radius: 999px; border: 1px solid var(--borde);
    background: var(--card); color: var(--texto); font-size: .82rem; cursor: pointer;
  }
  .filtro-btn:hover { background: var(--destacado-bg); }
  .filtro-btn.activo { background: var(--acento); color: #fff; border-color: var(--acento); }

  .filtro-bar {
    display: flex; align-items: center; flex-wrap: wrap; gap: 1rem;
    background: var(--card); border: 1px solid var(--borde); border-radius: 10px;
    padding: 1rem 1.2rem; margin-bottom: 1.5rem;
  }
  .filtro-mes-label { display: flex; align-items: center; gap: .5rem; font-size: .8rem; color: var(--texto-sub); }
  .filtro-mes-select, .filtro-rango-fechas input[type="date"] {
    padding: .45rem .7rem; border-radius: 8px; border: 1px solid var(--borde);
    background: var(--card); color: var(--texto); font-size: .82rem;
  }
  .filtro-rango-fechas { display: flex; align-items: center; gap: .5rem; color: var(--texto-sub); font-size: .82rem; }
  .filtro-btn-suc {
    padding: .5rem 1rem; border-radius: 999px; border: 1px solid var(--borde);
    background: var(--card); color: var(--texto); font-size: .82rem; cursor: pointer;
  }
  .filtro-btn-suc:hover { background: var(--destacado-bg); }
  .filtro-btn-suc.activo { background: var(--acento); color: #fff; border-color: var(--acento); }

  .suc-fila { display: grid; grid-template-columns: 160px 1fr 220px; align-items: center; gap: 1rem; padding: .7rem 0; border-bottom: 1px solid var(--borde); }
  .suc-nombre { font-weight: 600; font-size: .92rem; }
  .suc-barra-wrap { background: #ece7dd; border-radius: 6px; height: 14px; overflow: hidden; }
  .suc-barra { background: var(--acento); height: 100%; border-radius: 6px; }
  .suc-barra-inv { background: #a89f8c; }
  .suc-cifras { text-align: right; font-size: .92rem; font-variant-numeric: tabular-nums; }
  .suc-trans { color: var(--texto-sub); font-size: .8rem; }

  .expandible { cursor: pointer; border-radius: 8px; }
  .expandible:hover { background: var(--destacado-bg); }
  .chevron { display: inline-block; font-size: .7rem; color: var(--texto-sub); transition: transform .15s; width: 1em; }
  .expandible.abierto .chevron { transform: rotate(90deg); }
  .detalle-vacio { color: var(--texto-sub); font-size: .8rem; padding: .5rem .3rem; }
  .detalle-titulo { font-size: .72rem; text-transform: uppercase; letter-spacing: .03em; color: var(--texto-sub); margin: .4rem 0 .3rem; }
  .detalle-item { display: flex; justify-content: space-between; font-size: .82rem; padding: .3rem .3rem; border-bottom: 1px dotted var(--borde); }

  .cat-fila { display: grid; grid-template-columns: 150px 1fr 60px 150px; align-items: center; gap: .8rem; padding: .55rem .4rem; }
  .cat-nombre { font-weight: 600; font-size: .85rem; }
  .cat-barra-wrap { background: #ece7dd; border-radius: 6px; height: 10px; overflow: hidden; }
  .cat-barra { height: 100%; border-radius: 6px; }
  .cat-margen { font-size: .8rem; font-weight: 700; text-align: right; }
  .cat-valor { text-align: right; font-size: .88rem; font-variant-numeric: tabular-nums; }
  .cat-barra.margen-alto { background: var(--verde); }
  .cat-barra.margen-medio { background: var(--ambar); }
  .cat-barra.margen-bajo { background: var(--rojo); }
  .cat-margen.margen-alto { color: var(--verde); }
  .cat-margen.margen-medio { color: var(--ambar); }
  .cat-margen.margen-bajo { color: var(--rojo); }
  .cat-detalle, .ref-detalle { display: none; padding: 0 .4rem .6rem 2.2rem; }
  .cat-wrap.abierto .cat-detalle, .ref-wrap.abierto .ref-detalle { display: block; }

  .ref-fila { display: grid; grid-template-columns: 28px 1fr 90px 130px; align-items: center; gap: .8rem; padding: .5rem .4rem; font-size: .88rem; }
  .ref-rank { color: var(--texto-sub); font-weight: 700; }
  .ref-nombre { font-weight: 500; }
  .ref-unidades { color: var(--texto-sub); text-align: right; }
  .ref-valor { text-align: right; font-weight: 600; font-variant-numeric: tabular-nums; }

  .subseccion { font-size: .85rem; text-transform: uppercase; letter-spacing: .03em; color: var(--texto-sub); margin: 1.8rem 0 .8rem 0; font-weight: 600; }
  .tabla-categorias { width: 100%; border-collapse: collapse; background: var(--card); border: 1px solid var(--borde); border-radius: 10px; overflow: hidden; }
  .tabla-categorias th, .tabla-categorias td { padding: .6rem 1rem; text-align: left; font-size: .88rem; border-bottom: 1px solid var(--borde); }
  .tabla-categorias th { color: var(--texto-sub); text-transform: uppercase; font-size: .72rem; letter-spacing: .03em; font-weight: 600; }
  .tabla-categorias td.num, .tabla-categorias th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .tabla-categorias tr:last-child td { border-bottom: none; }

  .tabla-scroll { overflow-x: auto; border: 1px solid var(--borde); border-radius: 10px; background: var(--card); }
  .tabla-historico { width: 100%; border-collapse: collapse; font-size: .78rem; min-width: 900px; background: var(--card); }
  .tabla-historico th, .tabla-historico td { padding: .5rem .6rem; border-bottom: 1px solid var(--borde); text-align: right; white-space: nowrap; }
  .tabla-historico th { color: var(--texto-sub); text-transform: uppercase; font-size: .68rem; letter-spacing: .02em; font-weight: 600; position: sticky; top: 0; background: var(--card); text-align: right; }
  .tabla-historico th.hist-th-suc, .tabla-historico td.hist-td-suc { text-align: left; }
  .tabla-historico tr:last-child td { border-bottom: none; }
  .hist-td-suc { font-weight: 600; position: sticky; left: 0; background: var(--card); }
  .hist-v-main { font-weight: 600; display: block; }
  .hist-v-cmp { color: var(--texto-sub); font-size: .85em; display: block; }
  .hist-v-meta { color: var(--texto-sub); font-style: italic; }
  .hist-meta-lbl { color: var(--acento-suave); font-size: .65em; text-transform: uppercase; letter-spacing: .03em; }
  .hist-td-meta { background: var(--bg); }
  .hist-var-up { color: var(--verde); font-size: .82em; font-weight: 600; display: block; }
  .hist-var-dn { color: var(--rojo); font-size: .82em; font-weight: 600; display: block; }
  .tabla-historico tfoot td { font-weight: 700; border-top: 2px solid var(--borde); border-bottom: none; }

  .hist-controles { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem; }
  .hist-selects { display: flex; gap: 1.2rem; flex-wrap: wrap; }
  .hist-selects label { font-size: .78rem; color: var(--texto-sub); display: flex; align-items: center; gap: .4rem; }
  .hist-selects select { padding: .35rem .6rem; border-radius: 6px; border: 1px solid var(--borde); background: var(--card); font-size: .82rem; font-weight: 600; }
  .hist-legend { font-size: .82rem; font-weight: 600; }
  .hist-meses { display: flex; gap: .35rem; flex-wrap: wrap; margin-bottom: 1rem; }
  .hmf-btn { padding: .3rem .65rem; border-radius: 999px; border: 1px solid var(--borde); background: var(--card); color: var(--texto-sub); font-size: .74rem; cursor: pointer; }
  .hmf-btn.hmf-on { background: var(--acento); color: #fff; border-color: var(--acento); }
  .hmf-todos { font-weight: 700; }

  .grid-2col { display: grid; grid-template-columns: 1.3fr 1fr; gap: 2rem; align-items: start; }
  @media (max-width: 900px) { .grid-2col { grid-template-columns: 1fr; } }
  .lista-scroll { max-height: 520px; overflow-y: auto; border: 1px solid var(--borde); border-radius: 10px; background: var(--card); padding: 0 1rem; }
  .lista-scroll::-webkit-scrollbar { width: 8px; }
  .lista-scroll::-webkit-scrollbar-thumb { background: var(--acento-suave); border-radius: 4px; }

  .suc-wrap { background: var(--card); border: 1px solid var(--borde); border-radius: 10px; padding: 1.4rem 1.6rem; }
  .suc-wrap .suc-fila:last-of-type { border-bottom: none; }
  .suc-total-linea { display: flex; justify-content: space-between; font-weight: 700; font-size: .92rem; padding-top: 1rem; margin-top: .3rem; border-top: 1px solid var(--borde); }
  .card-titulo { font-family: Georgia, "Times New Roman", serif; font-weight: 400; font-size: 1rem; text-transform: uppercase; letter-spacing: .03em; align-self: flex-start; margin-bottom: 1rem; }
  .com-inner { width: 100%; display: flex; flex-direction: column; align-items: center; }
  .donut-wrap { background: var(--card); border: 1px solid var(--borde); border-radius: 10px; padding: 1.4rem; display: flex; flex-direction: column; align-items: center; }
  .donut-container { position: relative; width: 180px; height: 180px; }
  .donut-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
  .donut-pct { font-size: 1.5rem; font-weight: 700; }
  .donut-sub-label { font-size: .72rem; color: var(--texto-sub); text-transform: uppercase; letter-spacing: .03em; }
  .donut-legend { width: 100%; max-width: 220px; margin-top: 1.2rem; }
  .legend-item { display: flex; align-items: center; gap: .5rem; padding: .3rem 0; font-size: .85rem; }
  .legend-item-separada { margin-top: .5rem; padding-top: .6rem; border-top: 1px solid var(--borde); }
  .legend-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .legend-name { flex: 1; color: var(--texto-sub); }
  .legend-pct { font-weight: 700; font-variant-numeric: tabular-nums; }

  .reo-cat-wrap { border: 1px solid var(--borde); border-radius: 10px; background: var(--card); margin-bottom: .7rem; overflow: hidden; }
  .reo-cat-wrap:hover { background: var(--card); }
  .reo-cat-header { display: flex; align-items: center; gap: .8rem; padding: .9rem 1.1rem; flex-wrap: wrap; }
  .reo-cat-nombre { font-weight: 700; font-size: .9rem; }
  .reo-cat-meta { color: var(--texto-sub); font-size: .78rem; }
  .reo-badge { font-size: .72rem; font-weight: 700; padding: .2rem .6rem; border-radius: 999px; margin-left: auto; }
  .reo-badge + .reo-badge { margin-left: .4rem; }
  .reo-badge.critico { background: var(--rojo-bg); color: var(--rojo); margin-left: auto; }
  .reo-badge.alerta { background: var(--ambar-bg); color: var(--ambar); }
  .reo-badge.sugerido { background: var(--verde-bg); color: var(--verde); }
  .reo-cat-detalle { display: none; border-top: 1px solid var(--borde); padding: .3rem 1.1rem .8rem; }
  .reo-cat-wrap.abierto .reo-cat-detalle { display: block; }
  .reo-fila { display: grid; grid-template-columns: 1fr 100px 120px 110px 70px; gap: .7rem; align-items: center; padding: .5rem 0; border-bottom: 1px dotted var(--borde); font-size: .82rem; }
  .reo-nombre { font-weight: 500; }
  .reo-disp, .reo-rot { color: var(--texto-sub); text-align: right; }
  .reo-estado { text-align: center; font-weight: 700; font-size: .72rem; padding: .2rem .4rem; border-radius: 6px; }
  .reo-estado.critico { background: var(--rojo-bg); color: var(--rojo); }
  .reo-estado.alerta { background: var(--ambar-bg); color: var(--ambar); }
  .reo-sug { text-align: right; font-weight: 700; }
  .reo-ref-wrap.expandible { cursor: pointer; }
  .reo-ref-wrap.expandible:hover .reo-fila { background: var(--destacado-bg); }
  .reo-tallas-count { color: var(--texto-sub); font-weight: 400; font-size: .78em; }
  .reo-variantes { display: none; padding: .4rem 0 .6rem 1.6rem; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: .3rem .8rem; }
  .reo-ref-wrap.abierto .reo-variantes { display: grid; }
  .reo-variantes .detalle-item { border-bottom: none; padding: .15rem 0; font-size: .78rem; }

  .ref-suc-wrap.expandible { cursor: pointer; }
  .ref-suc-wrap.expandible:hover .detalle-item { background: var(--destacado-bg); }
  .ref-variantes { display: none; padding: .3rem 0 .5rem 1.4rem; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: .25rem .7rem; }
  .ref-suc-wrap.abierto .ref-variantes { display: grid; }
  .ref-variantes .detalle-item { border-bottom: none; padding: .12rem 0; font-size: .76rem; }

  .nota { margin-top: 1.5rem; padding: 1rem 1.2rem; border: 1px dashed var(--acento-suave); border-radius: 8px; font-size: .85rem; color: var(--texto-sub); }
  footer { margin-top: 2rem; font-size: .75rem; color: var(--texto-sub); }

  .login-overlay {
    position: fixed; inset: 0; background: var(--bg);
    display: flex; align-items: center; justify-content: center; z-index: 100;
  }
  .login-card {
    background: var(--card); border: 1px solid var(--borde); border-radius: 14px;
    padding: 2.4rem 2.2rem; width: 320px; max-width: 88vw; text-align: center;
  }
  .login-logo { display: block; margin: 0 auto; }
  .login-subtitulo { color: var(--texto-sub); font-size: .85rem; margin: .6rem 0 1.6rem; }
  .login-card input[type="text"], .login-card input[type="password"] {
    width: 100%; padding: .7rem .9rem; margin-bottom: .8rem; border-radius: 8px;
    border: 1px solid var(--borde); background: var(--bg); color: var(--texto); font-size: .9rem;
  }
  .login-pass-wrap { position: relative; }
  .login-pass-wrap input { padding-right: 2.2rem; }
  .login-eye { position: absolute; right: .8rem; top: 50%; transform: translateY(-50%); translate: 0 -.4rem; cursor: pointer; font-size: .9rem; }
  .login-recordar { display: flex; align-items: center; gap: .4rem; font-size: .78rem; color: var(--texto-sub); margin-bottom: 1.2rem; text-align: left; }
  .login-btn {
    width: 100%; padding: .75rem; border-radius: 8px; border: none;
    background: var(--acento); color: #fff; font-weight: 600; font-size: .9rem; cursor: pointer;
  }
  .login-btn:hover { opacity: .9; }
  .login-error { color: var(--rojo); font-size: .8rem; margin-top: .8rem; min-height: 1em; }

  .com-meses { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: 1.2rem; }
  .com-mes-btn { padding: .4rem .9rem; border-radius: 999px; border: 1px solid var(--borde); background: var(--card); color: var(--texto-sub); font-size: .82rem; cursor: pointer; }
  .com-mes-btn.com-mes-on { background: var(--acento); color: #fff; border-color: var(--acento); }
  .com-total-card { background: var(--destacado-bg); border: 1px solid var(--acento-suave); border-radius: 12px; padding: 1.1rem 1.4rem; margin-bottom: 1.5rem; max-width: 320px; }
  .com-total-valor { font-size: 1.8rem; font-weight: 700; margin-top: .2rem; }
  .com-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1.2rem; }
  .comision-card { background: var(--card); border: 1px solid var(--borde); border-radius: 12px; padding: 1.3rem 1.4rem; }
  .comision-card-top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: .3rem; }
  .comision-suc { font-weight: 700; font-size: 1rem; }
  .comision-pct { font-size: 1.3rem; font-weight: 700; color: var(--ambar); }
  .comision-pct.pos { color: var(--verde); }
  .comision-pct.neg { color: var(--rojo); }
  .comision-cifras { font-size: .88rem; color: var(--texto-sub); margin-bottom: .5rem; }
  .comision-meta-txt { color: var(--texto-sub); }
  .comision-barra-wrap { background: #ece7dd; border-radius: 6px; height: 10px; overflow: hidden; margin-bottom: 1rem; }
  .comision-barra { background: var(--acento); height: 100%; border-radius: 6px; }
  .comision-admin { display: flex; justify-content: space-between; font-size: .85rem; font-weight: 600; padding-bottom: .6rem; border-bottom: 1px solid var(--borde); margin-bottom: .6rem; }
  .comision-desglose { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem .8rem; font-size: .82rem; margin-bottom: .6rem; }
  .comision-desglose > div { display: flex; justify-content: space-between; }
  .comision-desglose-lbl { color: var(--texto-sub); }
  .comision-total-linea { display: flex; justify-content: space-between; font-weight: 700; font-size: .88rem; padding: .6rem 0; border-top: 1px solid var(--borde); margin-bottom: .8rem; }
  .comision-chart-legend { display: flex; gap: 1rem; font-size: .74rem; color: var(--texto-sub); margin-bottom: .3rem; }
  .comision-chart-legend span { display: flex; align-items: center; gap: .3rem; }
  .com-dot-dash, .com-dot-solid { width: 10px; height: 2px; display: inline-block; }
  .com-dot-dash { background: repeating-linear-gradient(to right, var(--verde) 0 3px, transparent 3px 5px); }
  .com-dot-solid { background: var(--acento); height: 2.5px; }
  .com-chart { width: 100%; height: auto; display: block; margin-bottom: .5rem; }
  .com-chart-eje { font-size: 7px; fill: var(--texto-sub); }
  .comision-avance-sub { font-size: .74rem; color: var(--texto-sub); text-transform: uppercase; letter-spacing: .02em; }
  .comision-avance-meta { font-size: .84rem; font-weight: 600; margin-top: .15rem; }

  /* ---- Mobile: todas las filas de datos vienen de grids con columnas en px
     (suc-fila, cat-fila, ref-fila, reo-fila) pensadas para escritorio; en un
     viewport angosto esas columnas fijas se salen de la pantalla. Se
     colapsan a una sola columna aquí en vez de tocar el HTML/JS que las
     genera (parte se arma en Python, parte en JS — una sola regla CSS
     cubre ambos casos sin duplicar lógica). ---- */
  @media (max-width: 640px) {
    body { padding: 1.4rem 1rem 3rem; }
    header.header-top { gap: .6rem; }
    .live-badge { font-size: .68rem; padding: .35rem .6rem; }
    .logout-btn { padding: .4rem .8rem; font-size: .72rem; }
    .marca-central { margin: 1.1rem 0 1.6rem; }
    .logo-central { height: 56px !important; }
    .marca-actualizado { flex-direction: column; gap: .1rem; }
    h2 { font-size: 1rem; margin: 1.8rem 0 1rem 0; }

    .kpi-grid { grid-template-columns: 1fr 1fr; gap: .7rem; }
    .kpi-card { padding: .9rem 1rem; }
    .kpi-valor { font-size: 1.15rem; }

    .venta-hoy { padding: 1.1rem 1.2rem; }
    .venta-hoy-valor { font-size: 1.9rem; }

    .filtro-bar { flex-direction: column; align-items: stretch; padding: .9rem; }
    .filtro-mes-label { flex-direction: column; align-items: stretch; }
    .filtro-rango, .filtro-rango-fechas { width: 100%; }
    .filtro-rango-fechas input[type="date"] { flex: 1 1 120px; min-width: 0; }

    .suc-fila, .cat-fila, .ref-fila, .reo-fila {
      grid-template-columns: 1fr !important; row-gap: .3rem; padding: .8rem 0;
    }
    .suc-cifras, .cat-valor, .cat-margen, .ref-unidades, .ref-valor,
    .reo-disp, .reo-rot, .reo-sug { text-align: left; }
    .reo-estado { justify-self: start; }

    .reo-cat-header { flex-direction: column; align-items: flex-start; gap: .4rem; }
    .reo-badge, .reo-badge + .reo-badge { margin-left: 0; }
    .reo-variantes { grid-template-columns: 1fr 1fr; }
    .ref-variantes { grid-template-columns: 1fr 1fr; }

    .donut-legend { max-width: 100%; }
    .hist-controles { flex-direction: column; align-items: flex-start; }
    .nav-panel { width: 84vw; max-width: 300px; }

    .com-total-card { max-width: 100%; }
    .com-grid { grid-template-columns: 1fr; }
  }
"""


# ---------- generador principal ----------

def generar_dashboard_html(datos: dict = None) -> str:
    ventas = _cargar_json(REPORTES_DIR / "ventas_procesado.json")
    inventario = _cargar_json(REPORTES_DIR / "inventario_procesado.json")
    historico_mensual = _cargar_json(REPORTES_DIR / "historico_mensual.json")
    cat_ref = _cargar_json(REPORTES_DIR / "categorias_referencias.json")
    ventas_diarias = _cargar_json(REPORTES_DIR / "ventas_diarias.json", {"sucursales": [], "por_dia": {}})
    reorden = _cargar_json(REPORTES_DIR / "reorden.json")
    metas_cfg = _cargar_json(CONFIG_DIR / "metas_mensuales.json", {})
    sucursales_cfg = _cargar_json(CONFIG_DIR / "sucursales.json", {"sucursales": []})["sucursales"]
    comisiones_cfg = _cargar_json(CONFIG_DIR / "comisiones_config.json", {})

    if not ventas:
        return _html_sin_datos()

    anio = ventas["anio_actual"]
    mes = ventas["mes_actual"]
    hoy = ventas["hoy"]
    cartera = ventas["cartera"]
    fecha_ref = ventas["actualizado_hasta"].split(" ")[0]
    anio_num = int(fecha_ref.split("-")[0])
    marmol_uri = _marmol_data_uri()
    icono_uri = _icono_app_data_uri()
    manifest_uri = _manifest_data_uri(icono_uri)
    body_style = (
        f'background-color:#f4f1ec; background-image:url({marmol_uri}); '
        f'background-repeat:repeat; background-size:900px auto; background-blend-mode:multiply;'
        if marmol_uri else ""
    )

    unidades_anio = cat_ref["anio_actual"]["unidades_totales"] if cat_ref else None
    kpis_anio_html = _grupo_kpis(anio["kpis"], unidades_anio)
    kpis_mes_html = _grupo_kpis(mes["kpis"])

    venta_hoy_html = _seccion_venta_hoy(hoy)
    ventas_recientes_html = _seccion_ventas_recientes()

    por_sucursal_anio = sorted(anio["por_sucursal"], key=lambda r: -r["ingreso"])
    maximo_suc = max((r["ingreso"] for r in por_sucursal_anio), default=1)
    total_ventas_suc = sum(r["ingreso"] for r in por_sucursal_anio)
    total_trans_suc = sum(r["transacciones"] for r in por_sucursal_anio)
    sucursales_html = "".join([
        _fila_sucursal(r["sucursal"], r["ingreso"], r["transacciones"], maximo_suc,
                        pct_total=(r["ingreso"] / total_ventas_suc * 100) if total_ventas_suc else None)
        for r in por_sucursal_anio
    ])
    if por_sucursal_anio:
        sucursales_html += (
            f'<div class="suc-total-linea"><span>Total</span>'
            f'<span>{_cop(total_ventas_suc)} · {_miles(total_trans_suc)} ventas</span></div>'
        )

    composicion_html = ""
    if anio.get("composicion"):
        composicion_html = _seccion_composicion_venta(anio["composicion"], anio["kpis"]["margen_promedio"])

    opciones_mes_filtro_html = _opciones_mes_filtro(ventas_diarias, anio_num)

    rentabilidad_html = ""
    referencias_html = ""
    if cat_ref:
        productos_por_categoria = cat_ref["anio_actual"].get("productos_por_categoria", {})
        categorias = cat_ref["anio_actual"]["categorias"]
        maximo_margen = max((c["margen"] for c in categorias), default=1)
        rentabilidad_html = "".join(_fila_categoria_rentabilidad(c, maximo_margen, productos_por_categoria) for c in categorias)

        por_sucursal_ref = cat_ref["anio_actual"].get("top_referencias_por_sucursal", {})
        referencias = cat_ref["anio_actual"]["top_referencias"]
        referencias_html = "".join(_fila_referencia(i + 1, r, por_sucursal_ref) for i, r in enumerate(referencias))

    comparativo_html = _seccion_comparativo_historico(historico_mensual, metas_cfg, sucursales_cfg, datetime.now())
    comisiones_html = _seccion_comisiones(comisiones_cfg, sucursales_cfg, datetime.now())
    inventario_resumen_html = _seccion_inventario_resumen(inventario)
    reorden_html = _seccion_reorden(reorden)

    generado = datetime.now().strftime("%Y-%m-%d %H:%M")
    diarias_json = json.dumps(ventas_diarias, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="theme-color" content="#f4f1ec">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Divina Intuición">
{f'<link rel="icon" type="image/png" sizes="512x512" href="{icono_uri}">' if icono_uri else ""}
{f'<link rel="apple-touch-icon" href="{icono_uri}">' if icono_uri else ""}
{f'<link rel="manifest" href="{manifest_uri}">' if manifest_uri else ""}
<title>Divina Intuición — Dashboard Gerencial</title>
<style>{_CSS}</style>
</head>
<body data-hoy="{fecha_ref}" style="{body_style}">
  {_LOGIN_HTML}
  <div id="app-contenido" style="display:none">

  <div class="nav-overlay" id="nav-overlay" onclick="closeNav()"></div>
  <div class="nav-panel" id="nav-panel">
    <div class="nav-panel-titulo">Divina Intuición</div>
    <div class="nav-item activo" data-nav="gerencia" onclick="navTo('gerencia')">🏛️&nbsp; Mesa de Gerencia</div>
    <div class="nav-item" data-nav="inventario" onclick="navTo('inventario')">📦&nbsp; Inventario</div>
    <div class="nav-item" data-nav="comisiones" onclick="navTo('comisiones')">💼&nbsp; Comisiones</div>
  </div>

  <header class="header-top">
    <button class="nav-hamburger" onclick="toggleNav()" aria-label="Menú">☰</button>
    <div class="header-badges">
      <div class="live-badge"><span class="live-dot"></span>En vivo</div>
      <button class="logout-btn" onclick="cerrarSesion()">Cerrar sesión</button>
    </div>
  </header>

  <div class="marca-central">
    {_logo_img_html("logo-central", "84px")}
    <div class="marca-actualizado">
      <span class="marca-actualizado-label">Datos actualizados hasta</span>
      <span class="marca-actualizado-valor">{ventas["actualizado_hasta"]}</span>
    </div>
  </div>

  <div id="sec-gerencia" class="seccion">
    <h2>Indicadores clave · Año {anio_num}</h2>
    <div class="kpi-grid">{kpis_anio_html}</div>

    <h2>Mes en curso</h2>
    <div class="kpi-grid">{kpis_mes_html}</div>

    {venta_hoy_html}

    {ventas_recientes_html}

    <h2>Ventas por Punto de Venta · Año {anio_num}</h2>
    <div class="filtro-bar">
      <label class="filtro-mes-label" for="filtro-mes-select">Filtrar por mes
        <select id="filtro-mes-select" class="filtro-mes-select" onchange="filtrarPorMes(this.value)">
          <option value="">Año completo {anio_num}</option>
          {opciones_mes_filtro_html}
        </select>
      </label>
      <div class="filtro-rango-fechas">
        <input type="date" id="filtro-fecha-desde" onchange="filtrarPorRangoFechas()">
        <span>—</span>
        <input type="date" id="filtro-fecha-hasta" onchange="filtrarPorRangoFechas()">
      </div>
      <div class="filtro-rango">
        <button class="filtro-btn-suc" data-desde="0" data-hasta="0" onclick="filtrarSucursales(0,0,this)">Hoy</button>
        <button class="filtro-btn-suc" data-desde="1" data-hasta="1" onclick="filtrarSucursales(1,1,this)">Ayer</button>
        <button class="filtro-btn-suc" data-desde="6" data-hasta="0" onclick="filtrarSucursales(6,0,this)">7 días</button>
        <button class="filtro-btn-suc" data-desde="29" data-hasta="0" onclick="filtrarSucursales(29,0,this)">30 días</button>
        <button class="filtro-btn-suc" onclick="limpiarFiltroSucursales()">Limpiar</button>
      </div>
    </div>

    <div class="grid-2col">
      <div>
        <div class="suc-wrap">
          <div id="suc-punto-venta-bars">{sucursales_html}</div>
        </div>
      </div>
      <div>
        <div class="donut-wrap">
          <div class="card-titulo">Composición de Venta · Año {anio_num}</div>
          <div id="composicion-wrap" class="com-inner">{composicion_html}</div>
        </div>
      </div>
    </div>

    <div class="grid-2col">
      <div>
        <h2>Rentabilidad por categoría · Año {anio_num}</h2>
        <div class="subtitulo">Clic en una categoría para ver sus productos top · desliza para ver todas</div>
        <div class="lista-scroll">{rentabilidad_html}</div>
      </div>
      <div>
        <h2>Referencias · ventas netas · Año {anio_num}</h2>
        <div class="subtitulo">Clic en una referencia para ver el detalle por sucursal · desliza para ver todas</div>
        <div class="lista-scroll">{referencias_html}</div>
      </div>
    </div>

    {comparativo_html}

    <div class="nota">
      Cartera: {_miles(cartera["num_pendiente_de_cobro"])} remisiones pendientes de cobro por {_cop(cartera["pendiente_de_cobro"])} ·
      {_miles(cartera["num_anuladas_historico"])} remisiones anuladas excluidas del histórico.
    </div>
  </div>

  <div id="sec-inventario" class="seccion" style="display:none">
    <h2>Inventario</h2>
    {inventario_resumen_html}
    {reorden_html}
  </div>

  <div id="sec-comisiones" class="seccion" style="display:none">
    {comisiones_html}
  </div>

  <footer>Generado el {generado} · datos de Effi Systems</footer>
  <div class="powered-by">Powered by Divina Intuición IA</div>

  </div>

  <script type="application/json" id="data-diarias">{diarias_json}</script>
  <script>var LOGIN_USUARIO = {json.dumps(LOGIN_USUARIO)}; var LOGIN_CLAVE = {json.dumps(LOGIN_CLAVE)};</script>
  <script>{_JS}</script>
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
