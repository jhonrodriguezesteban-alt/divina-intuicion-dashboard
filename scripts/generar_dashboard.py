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


def _detalle_categoria_html(productos: list) -> str:
    if not productos:
        return '<div class="detalle-vacio">Sin detalle de productos.</div>'
    filas = "".join(
        f'<div class="detalle-item"><span>{p["nombre"].title()}</span>'
        f'<span>{_miles(p["unidades"])} und. · {_cop(p["ventas_netas"])}</span></div>'
        for p in productos
    )
    return f'<div class="cat-detalle"><div class="detalle-titulo">Top productos de la categoría</div>{filas}</div>'


def _fila_categoria_rentabilidad(cat: dict, maximo: float, productos_por_categoria: dict) -> str:
    pct_barra = round((cat["ventas_netas"] / maximo) * 100, 1) if maximo else 0
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
    if not por_sucursal:
        return '<div class="detalle-vacio">Sin detalle por sucursal.</div>'
    filas = "".join(
        f'<div class="detalle-item"><span>{s["sucursal"]}</span>'
        f'<span>{_miles(s["unidades"])} und. · {_cop(s["ventas_netas"])}</span></div>'
        for s in por_sucursal
    )
    return f'<div class="ref-detalle"><div class="detalle-titulo">Ventas por sucursal</div>{filas}</div>'


def _fila_referencia(rank: int, ref: dict, por_sucursal_ref: dict) -> str:
    clave = f'{ref["codigo"]}::{ref["nombre"]}'
    detalle = _detalle_referencia_html(por_sucursal_ref.get(clave, []))
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
    return f"""
      <div class="reo-fila">
        <div class="reo-nombre">{ref["nombre"].title()}</div>
        <div class="reo-disp">{_miles(ref["disponible"])} disp.</div>
        <div class="reo-rot">{rot}</div>
        <div class="reo-estado {estado}">{ref["estado_label"]}</div>
        <div class="reo-sug">{sug}</div>
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


# ---------- login (pantalla de acceso, protección de fricción — ver nota en el README) ----------
# Credenciales de acceso al dashboard (no las de Effi). Cambiar aquí si hace falta.
LOGIN_USUARIO = "divina"
LOGIN_CLAVE = "DivinaIntuicion2026"

_LOGIN_HTML = """
  <div class="login-overlay" id="login-overlay">
    <div class="login-card">
      <div class="login-marca">DIVINA INTUICIÓN</div>
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

function toggleAbierto(el){
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
  header { margin-bottom: 1rem; display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 1rem; }
  .header-left { display: flex; align-items: center; gap: 1rem; }
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
  .actualizado { color: var(--texto-sub); font-size: .8rem; text-align: right; }
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
  .tabla-historico { width: 100%; border-collapse: collapse; font-size: .78rem; min-width: 900px; }
  .tabla-historico th, .tabla-historico td { padding: .5rem .6rem; border-bottom: 1px solid var(--borde); text-align: left; white-space: nowrap; }
  .tabla-historico th { color: var(--texto-sub); text-transform: uppercase; font-size: .68rem; letter-spacing: .02em; font-weight: 600; position: sticky; top: 0; background: var(--card); }
  .tabla-historico td.num { text-align: right; }
  .tabla-historico tr:last-child td { border-bottom: none; }
  .hist-sucursal { font-weight: 600; position: sticky; left: 0; background: var(--card); }
  .hist-actual { font-weight: 600; }
  .hist-anterior { color: var(--texto-sub); font-size: .85em; }
  .hist-var { font-size: .85em; }
  .hist-vacio { color: var(--acento-suave); }

  .grid-2col { display: grid; grid-template-columns: 1.3fr 1fr; gap: 2rem; align-items: start; }
  @media (max-width: 900px) { .grid-2col { grid-template-columns: 1fr; } }

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

  .nota { margin-top: 1.5rem; padding: 1rem 1.2rem; border: 1px dashed var(--acento-suave); border-radius: 8px; font-size: .85rem; color: var(--texto-sub); }
  footer { margin-top: 2rem; font-size: .75rem; color: var(--texto-sub); }

  .login-overlay {
    position: fixed; inset: 0; background: var(--bg);
    display: flex; align-items: center; justify-content: center; z-index: 100;
  }
  .login-card {
    background: var(--card); border: 1px solid var(--borde); border-radius: 14px;
    padding: 2.4rem 2.2rem; width: 320px; text-align: center;
  }
  .login-marca { font-family: Georgia, serif; text-transform: uppercase; letter-spacing: .06em; font-size: 1.2rem; }
  .login-subtitulo { color: var(--texto-sub); font-size: .85rem; margin-bottom: 1.6rem; }
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
"""


# ---------- generador principal ----------

def generar_dashboard_html(datos: dict = None) -> str:
    ventas = _cargar_json(REPORTES_DIR / "ventas_procesado.json")
    inventario = _cargar_json(REPORTES_DIR / "inventario_procesado.json")
    historico_mensual = _cargar_json(REPORTES_DIR / "historico_mensual.json")
    cat_ref = _cargar_json(REPORTES_DIR / "categorias_referencias.json")
    ventas_diarias = _cargar_json(REPORTES_DIR / "ventas_diarias.json", {"sucursales": [], "por_dia": {}})
    reorden = _cargar_json(REPORTES_DIR / "reorden.json")

    if not ventas:
        return _html_sin_datos()

    anio = ventas["anio_actual"]
    mes = ventas["mes_actual"]
    hoy = ventas["hoy"]
    cartera = ventas["cartera"]
    fecha_ref = ventas["actualizado_hasta"].split(" ")[0]
    anio_num = int(fecha_ref.split("-")[0])

    unidades_anio = cat_ref["anio_actual"]["unidades_totales"] if cat_ref else None
    kpis_anio_html = _grupo_kpis(anio["kpis"], unidades_anio)
    kpis_mes_html = _grupo_kpis(mes["kpis"])

    venta_hoy_html = _seccion_venta_hoy(hoy)
    ventas_recientes_html = _seccion_ventas_recientes()

    por_sucursal_anio = sorted(anio["por_sucursal"], key=lambda r: -r["ingreso"])
    maximo_suc = max((r["ingreso"] for r in por_sucursal_anio), default=1)
    sucursales_html = "".join([
        _fila_sucursal(r["sucursal"], r["ingreso"], r["transacciones"], maximo_suc)
        for r in por_sucursal_anio
    ])

    rentabilidad_html = ""
    referencias_html = ""
    if cat_ref:
        productos_por_categoria = cat_ref["anio_actual"].get("productos_por_categoria", {})
        categorias = cat_ref["anio_actual"]["categorias"][:10]
        maximo_cat = max((c["ventas_netas"] for c in categorias), default=1)
        rentabilidad_html = "".join(_fila_categoria_rentabilidad(c, maximo_cat, productos_por_categoria) for c in categorias)

        por_sucursal_ref = cat_ref["anio_actual"].get("top_referencias_por_sucursal", {})
        referencias = cat_ref["anio_actual"]["top_referencias"][:10]
        referencias_html = "".join(_fila_referencia(i + 1, r, por_sucursal_ref) for i, r in enumerate(referencias))

    comparativo_html = _seccion_comparativo_historico(historico_mensual)
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
<title>Divina Intuición — Dashboard Gerencial</title>
<style>{_CSS}</style>
</head>
<body data-hoy="{fecha_ref}">
  {_LOGIN_HTML}
  <div id="app-contenido" style="display:none">

  <div class="nav-overlay" id="nav-overlay" onclick="closeNav()"></div>
  <div class="nav-panel" id="nav-panel">
    <div class="nav-panel-titulo">Divina Intuición</div>
    <div class="nav-item activo" data-nav="gerencia" onclick="navTo('gerencia')">🏛️&nbsp; Mesa de Gerencia</div>
    <div class="nav-item" data-nav="inventario" onclick="navTo('inventario')">📦&nbsp; Inventario</div>
    <div class="nav-item" data-nav="comisiones" onclick="navTo('comisiones')">💼&nbsp; Comisiones</div>
  </div>

  <header>
    <div class="header-left">
      <button class="nav-hamburger" onclick="toggleNav()" aria-label="Menú">☰</button>
      <div>
        <h1>Divina Intuición</h1>
        <div class="subtitulo">Dashboard Gerencial de Ventas · Local 144 · Local 433 · Local 107 (Divina Accesorios)</div>
      </div>
    </div>
    <div class="actualizado">Datos actualizados hasta<br>{ventas["actualizado_hasta"]}</div>
  </header>

  <div id="sec-gerencia" class="seccion">
    <h2>Indicadores clave · Año {anio_num}</h2>
    <div class="kpi-grid">{kpis_anio_html}</div>
    {venta_hoy_html}

    {ventas_recientes_html}

    <h2>Mes en curso</h2>
    <div class="kpi-grid">{kpis_mes_html}</div>

    <h2>Ventas por Punto de Venta · Año {anio_num}</h2>
    <div>{sucursales_html}</div>

    <div class="grid-2col">
      <div>
        <h2>Rentabilidad por categoría · Año {anio_num}</h2>
        <div class="subtitulo">Clic en una categoría para ver sus productos top</div>
        <div>{rentabilidad_html}</div>
      </div>
      <div>
        <h2>Top referencias · ventas netas</h2>
        <div class="subtitulo">Clic en una referencia para ver el detalle por sucursal</div>
        <div>{referencias_html}</div>
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
    <h2>Comisiones</h2>
    <div class="nota">Pendiente: definir con el negocio el escalafón de comisiones por vendedor/sucursal en config/metas_comisiones.json.</div>
  </div>

  <footer>Generado el {generado} · datos de Effi Systems</footer>

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
