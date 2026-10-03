"""
Planeación de temporada (oct-nov-dic) -> reportes/planeacion_temporada.json

Estima cuántas unidades se van a vender por familia (categoría de ropa, y
accesorios como una sola familia con sus subcategorías) en cada local y
mes de la temporada, y cuánto hay que comprar -- y en qué referencias,
colores y tallas -- descontando el stock que ya hay.

Cómo se estima la venta (en unidades, no en pesos: el precio por prenda
subió ~23% en 2026, así que la plata no sirve para dimensionar mercancía):

- Local 144 y 433 (tienen oct-dic 2025): unidades del mismo mes 2025 x
  la tendencia de esa categoría en ese local (jul-sep 2026 vs jul-sep 2025).
  La tendencia por categoría se "encoge" hacia la del local completo
  cuando la categoría vende poco (si no, una categoría con 5 unidades
  podía salir con +300%) y se limita a 0.5x-2x de la del local.
- Local 107 (abrió abr-2026, sin año anterior) y cualquier categoría sin
  historia 2025 en 144/433 (ej. accesorios): venta de septiembre 2026 x el
  salto estacional sep->oct/nov/dic que tuvieron 144+433 en 2025 -- mismo
  método que se usó para la meta de octubre del 107.

Las unidades del "Reporte de conceptos" se escalan al total oficial de
cada local/mes (historico_mensual.json): ese reporte incluye las líneas de
remisiones anuladas y sobrecuenta entre 0.5% y 4.7%.

El dashboard deja ajustar el % de crecimiento de cada local (escenario
"tendencia" vs "metas de octubre") y el colchón de seguridad, y recalcula
compra e inversión en el navegador -- por eso aquí se guarda la venta del
escenario "tendencia" y los factores de cada escenario, no solo un número
final.
"""

import json
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd

from common.procesamiento import (
    cargar_conceptos_combinados, cargar_config, leer_excel_effi, asegurar_columnas_articulos,
    referencia_base, _RE_TALLA_GRANDE, _RE_TALLA, _RE_COLOR,
)

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_ARTICULOS = BASE_DIR / "reportes" / "raw" / "raw_articulos.xlsx"
HISTORICO = BASE_DIR / "reportes" / "historico_mensual.json"
OUT = BASE_DIR / "reportes" / "planeacion_temporada.json"

MESES_ES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
MESES_TEMPORADA = [10, 11, 12]
MIN_UNIDADES_TENDENCIA = 100  # por debajo, la tendencia de la categoría se mezcla con la del local
MIN_UNIDADES_ESTACIONAL = 40  # mínimo en sep-2025 para usar la estacionalidad propia de la categoría
MAX_REFERENCIAS = 12
COBERTURA_REFERENCIAS = 0.80
REFERENCIAS_EXCLUIDAS = {"PROMOCIONES", "PROMOCION"}

TALLAS_ORDEN = ["XS", "S", "M", "L", "XL", "4", "6", "8", "10", "12", "14", "16", "Única", "Pequeña", "Grande"]


def _sin_tilde(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


_COLOR_NORMALIZADO = {
    "NEGRA": "NEGRO", "BLANCA": "BLANCO", "ROJA": "ROJO", "AMARILLA": "AMARILLO",
    "MORADA": "MORADO", "DORADA": "DORADO", "PLATEADA": "PLATEADO",
    "CLARA": "CLARO", "OSCURA": "OSCURO",
}


def _color_y_talla(nombre: str) -> tuple:
    """(color, talla) a partir del nombre del artículo en Effi -- mismos
    patrones que referencia_base(), pero devolviendo lo que se quita en vez
    de descartarlo. Sin talla en el nombre = prenda de talla única."""
    n = (nombre or "").strip()
    talla = "Única"
    m = _RE_TALLA_GRANDE.search(n) or _RE_TALLA.search(n)
    if m:
        bruto = _sin_tilde(m.group(0).strip().upper())
        n = n[:m.start()]
        if "GRANDE" in bruto:
            talla = "Grande"
        elif "PEQUE" in bruto:
            talla = "Pequeña"
        else:
            t = bruto.replace("TALLA", "").replace("T-", "").lstrip("T").strip()
            talla = "Única" if t in ("U", "") else t
    color = None
    m2 = _RE_COLOR.search(n)
    if m2:
        palabras = _sin_tilde(m2.group(0).strip().upper()).split()
        color = " ".join(_COLOR_NORMALIZADO.get(p, p) for p in palabras)
    return color, talla


def _mix(serie_unidades: pd.Series, top: int = 6) -> list:
    """[[etiqueta, participación], ...] ordenado de mayor a menor."""
    total = serie_unidades.sum()
    if total <= 0:
        return []
    s = (serie_unidades / total).sort_values(ascending=False)
    return [[str(k), round(float(v), 4)] for k, v in s.head(top).items()]


def _orden_tallas(mix: list) -> list:
    return sorted(mix, key=lambda kv: TALLAS_ORDEN.index(kv[0]) if kv[0] in TALLAS_ORDEN else 99)


def _pesos(v) -> str:
    return f"${v:,.0f}".replace(",", ".") if v else "sin meta"


def _primera_palabra(nombre) -> str:
    partes = _sin_tilde(str(nombre or "")).upper().split()
    return partes[0] if partes else ""


def _inferir_categorias(nombres_cat: pd.DataFrame) -> dict:
    """{primera palabra del nombre: categoría} aprendido de los artículos que
    SÍ tienen categoría -- en Effi hay ~140 artículos creados sin categoría
    (oct-2026), casi todos prendas normales ("BLUSA SANTORINI...", "BODY
    ESTRAPLE...") que se perdían como "SIN CATEGORÍA". Solo se usa cuando
    la palabra apunta claramente (>=70%) a una categoría."""
    d = nombres_cat.dropna().copy()
    d["palabra"] = d["nombre"].apply(_primera_palabra)
    conteo = d.groupby(["palabra", "categoria"]).size()
    mapa = {}
    for palabra, grupo in conteo.groupby(level=0):
        total = grupo.sum()
        cat, n = grupo.droplevel(0).idxmax(), grupo.max()
        if palabra and total >= 3 and n / total >= 0.7:
            mapa[palabra] = cat
    return mapa


def _cargar_ventas(nombre_map: dict, codigo_map: dict, historico: dict) -> pd.DataFrame:
    df = cargar_conceptos_combinados()
    df["Fecha creación"] = pd.to_datetime(df["Fecha creación"])
    df = df[df["Estado CXC"] == "Pago total"].copy()
    df["suc"] = df["Sucursal"].map(nombre_map)
    df["cod"] = df["Sucursal"].map(codigo_map)
    df["anio"] = df["Fecha creación"].dt.year
    df["mes"] = df["Fecha creación"].dt.month
    for col in ("Cantidad", "Precio neto total", "Costo manual total", "Costo manual unitario"):
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Escala de anuladas: unidades x (neto oficial / neto del reporte de conceptos)
    neto = df.groupby(["cod", "anio", "mes"])["Precio neto total"].sum()
    escala = {}
    for (cod, anio, mes), valor in neto.items():
        oficial = historico.get(cod, {}).get("por_anio_mes", {}).get(str(anio), {}).get(MESES_ES[mes - 1], {}).get("neto")
        escala[(cod, anio, mes)] = (oficial / valor) if oficial and valor > 0 else 1.0
    df["unid"] = df["Cantidad"] * [escala.get(k, 1.0) for k in zip(df["cod"], df["anio"], df["mes"])]

    df["ref"] = df["Descripción artículo"].apply(referencia_base)
    ct = df["Descripción artículo"].apply(_color_y_talla)
    df["color"] = [c for c, _ in ct]
    df["talla"] = [t for _, t in ct]
    return df


def main():
    sucursales = cargar_config("sucursales.json")["sucursales"]
    nombre_map = {s["nombre_effi"]: s["nombre"] for s in sucursales}
    codigo_map = {s["nombre_effi"]: s["codigo"] for s in sucursales}
    nombre_por_codigo = {s["codigo"]: s["nombre"] for s in sucursales}
    cat_acc = set(cargar_config("categorias_accesorios.json")["categorias"])
    metas = cargar_config("metas_mensuales.json")
    historico = json.loads(HISTORICO.read_text(encoding="utf-8"))

    hoy = pd.Timestamp.now().normalize()
    anio = hoy.year
    df = _cargar_ventas(nombre_map, codigo_map, historico)
    art = asegurar_columnas_articulos(leer_excel_effi(RAW_ARTICULOS))

    mapa_cat = _inferir_categorias(pd.concat([
        pd.DataFrame({"nombre": art["Nombre"], "categoria": art["Categoría"]}),
        pd.DataFrame({"nombre": df["Descripción artículo"], "categoria": df["Categoría artículo"]}),
    ]))
    sin_cat_ventas = df["Categoría artículo"].isna()
    df.loc[sin_cat_ventas, "Categoría artículo"] = df.loc[sin_cat_ventas, "Descripción artículo"].apply(_primera_palabra).map(mapa_cat)
    sin_cat_art = art["Categoría"].isna()
    art.loc[sin_cat_art, "Categoría"] = art.loc[sin_cat_art, "Nombre"].apply(_primera_palabra).map(mapa_cat)
    print(f"Categoría inferida por nombre: {sin_cat_ventas.sum() - df['Categoría artículo'].isna().sum()} líneas de venta "
          f"y {sin_cat_art.sum() - art['Categoría'].isna().sum()} artículos del catálogo (de {sin_cat_art.sum()} sin categoría en Effi).")

    df["Categoría artículo"] = df["Categoría artículo"].fillna("SIN CATEGORÍA")
    df["familia"] = df["Categoría artículo"].where(~df["Categoría artículo"].isin(cat_acc), "ACCESORIOS")

    def periodo(a, meses):
        return df[(df["anio"] == a) & (df["mes"].isin(meses))]

    js_prev, js_act = periodo(anio - 1, [7, 8, 9]), periodo(anio, [7, 8, 9])
    sep_prev, sep_act = periodo(anio - 1, [9]), periodo(anio, [9])
    temp_prev = periodo(anio - 1, MESES_TEMPORADA)
    locales_hist = ["144", "433"]  # con oct-dic del año anterior
    ref_prev = df[(df["anio"] == anio - 1) & df["cod"].isin(locales_hist)]

    # Estacionalidad sep -> oct/nov/dic del año anterior (144+433), total y por categoría
    def indices(sub_sep, sub_temp):
        base = sub_sep["unid"].sum()
        if base <= 0:
            return None
        return [float(sub_temp[sub_temp["mes"] == m]["unid"].sum() / base) for m in MESES_TEMPORADA]

    sep_hist = sep_prev[sep_prev["cod"].isin(locales_hist)]
    temp_hist = temp_prev[temp_prev["cod"].isin(locales_hist)]
    idx_total = indices(sep_hist, temp_hist)

    def idx_categoria(cat):
        s = sep_hist[sep_hist["Categoría artículo"] == cat]
        if s["unid"].sum() < MIN_UNIDADES_ESTACIONAL:
            return idx_total
        return indices(s, temp_hist[temp_hist["Categoría artículo"] == cat]) or idx_total

    # Factores por local
    locales_out = []
    tendencia_local = {}
    for s in sucursales:
        cod = s["codigo"]
        meta_oct = (metas.get(cod) or {}).get("10")
        if cod in locales_hist:
            u_prev = js_prev[js_prev["cod"] == cod]["unid"].sum()
            u_act = js_act[js_act["cod"] == cod]["unid"].sum()
            pesos_prev = sum(historico[cod]["por_anio_mes"][str(anio - 1)][m]["neto"] for m in ("Jul", "Ago", "Sep"))
            pesos_act = sum(historico[cod]["por_anio_mes"][str(anio)][m]["neto"] for m in ("Jul", "Ago", "Sep"))
            tendencia = u_act / u_prev
            alza_precio = (pesos_act / u_act) / (pesos_prev / u_prev)
            oct_prev = historico[cod]["por_anio_mes"][str(anio - 1)]["Oct"]["neto"]
            factor_meta = (meta_oct / oct_prev) / alza_precio if meta_oct else None
            tendencia_local[cod] = tendencia
            locales_out.append({
                "codigo": cod, "nombre": s["nombre"], "metodo": "anio_anterior",
                "pct_tendencia": round(tendencia - 1, 4),
                "pct_meta": round(factor_meta - 1, 4) if factor_meta else None,
                "alza_precio_unidad": round(alza_precio - 1, 4),
                "detalle": (f"Mismo mes {anio - 1} x tendencia jul-sep ({(tendencia - 1) * 100:+.1f}% en unidades; "
                            f"el precio por prenda subió {(alza_precio - 1) * 100:.0f}%). Escenario metas: las unidades "
                            f"que hacen que octubre llegue a la meta ({_pesos(meta_oct)})."),
            })
        else:
            pesos_sep = historico[cod]["por_anio_mes"][str(anio)]["Sep"]["neto"]
            pesos_sep_hist = sum(historico[c]["por_anio_mes"][str(anio - 1)]["Sep"]["neto"] for c in locales_hist)
            pesos_oct_hist = sum(historico[c]["por_anio_mes"][str(anio - 1)]["Oct"]["neto"] for c in locales_hist)
            esperado_oct = pesos_sep * pesos_oct_hist / pesos_sep_hist
            factor_meta = meta_oct / esperado_oct if meta_oct else None
            tendencia_local[cod] = 1.0
            sep_local = sep_act[sep_act["cod"] == cod]
            pct_ropa = (sep_local[sep_local["familia"] != "ACCESORIOS"]["unid"].sum() / sep_local["unid"].sum()) if sep_local["unid"].sum() else 0
            locales_out.append({
                "codigo": cod, "nombre": s["nombre"], "metodo": "ritmo_actual",
                "pct_tendencia": 0.0,
                "pct_meta": round(factor_meta - 1, 4) if factor_meta else None,
                "alza_precio_unidad": None,
                "detalle": (f"Sin año anterior: venta de septiembre {anio} categoría por categoría (en septiembre "
                            f"{pct_ropa * 100:.0f}% de sus unidades ya fueron ropa) x el salto estacional sep->oct/nov/dic "
                            f"que tuvieron 144+433 en {anio - 1}. Escenario metas: las unidades que hacen que octubre "
                            f"llegue a la meta ({_pesos(meta_oct)})."),
            })

    # Stock actual (catálogo)
    art["Stock total empresa"] = pd.to_numeric(art["Stock total empresa"], errors="coerce").fillna(0)
    art["Costo manual"] = pd.to_numeric(art["Costo manual"], errors="coerce").fillna(0)
    art["Categoría"] = art["Categoría"].fillna("SIN CATEGORÍA")
    art["familia"] = art["Categoría"].where(~art["Categoría"].isin(cat_acc), "ACCESORIOS")
    art["ref"] = art["Nombre"].apply(referencia_base)
    # Stock "con rotación": referencias que vendieron algo en los últimos 12
    # meses -- cubre lo de temporada que no se movió en jul-sep (ej. abrigos)
    # pero deja fuera lo que ya es candidato a liquidar.
    refs_vivas = set(df[df["Fecha creación"] >= hoy - pd.Timedelta(days=365)]["ref"])
    art["vivo"] = art["ref"].isin(refs_vivas)

    ventana_90 = df[df["Fecha creación"] >= hoy - pd.Timedelta(days=90)]
    ytd = df[df["anio"] == anio]

    familias_out = []
    for familia in sorted(set(df[df["anio"] == anio]["familia"]) | set(temp_hist["familia"])):
        es_acc = familia == "ACCESORIOS"
        cats = sorted(cat_acc) if es_acc else [familia]

        # Venta base (escenario tendencia) por local y mes
        base = {}
        for s in sucursales:
            cod, nombre = s["codigo"], s["nombre"]
            meses_out = [0.0, 0.0, 0.0]
            for cat in cats:
                prev_cat = temp_prev[(temp_prev["cod"] == cod) & (temp_prev["Categoría artículo"] == cat)]
                if cod in locales_hist and prev_cat["unid"].sum() > 0:
                    u_prev = js_prev[(js_prev["cod"] == cod) & (js_prev["Categoría artículo"] == cat)]["unid"].sum()
                    u_act = js_act[(js_act["cod"] == cod) & (js_act["Categoría artículo"] == cat)]["unid"].sum()
                    t_local = tendencia_local[cod]
                    if u_prev > 0:
                        t_cat = u_act / u_prev
                        peso = min(1.0, min(u_prev, u_act) / MIN_UNIDADES_TENDENCIA)
                        relativo = 1 + (t_cat / t_local - 1) * peso
                        relativo = max(0.5, min(2.0, relativo))
                    else:
                        relativo = 1.0
                    for i, m in enumerate(MESES_TEMPORADA):
                        meses_out[i] += prev_cat[prev_cat["mes"] == m]["unid"].sum() * t_local * relativo
                else:
                    # Ritmo actual: la venta de septiembre tal cual, categoría por
                    # categoría. NO un promedio jul-sep: el 107 cambió de formato
                    # en sep-2026 (jul: 99% accesorios; sep: 78% ropa) y promediar
                    # proyectaba una tienda de accesorios que ya no existe.
                    nivel = sep_act[(sep_act["cod"] == cod) & (sep_act["Categoría artículo"] == cat)]["unid"].sum()
                    if nivel <= 0:
                        continue
                    for i, ix in enumerate(idx_categoria(cat)):
                        meses_out[i] += nivel * ix
            base[nombre] = [round(v, 1) for v in meses_out]

        # Stock
        art_f = art[art["familia"] == familia]
        stock_total = int(art_f["Stock total empresa"].sum())
        stock_vivo = int(art_f[art_f["vivo"]]["Stock total empresa"].sum())

        # Costo y precio promedio por unidad (ventas del año, con costo registrado)
        v_ytd = ytd[ytd["familia"] == familia]
        con_costo = v_ytd[v_ytd["Costo manual unitario"] > 0]
        costo_u = float(con_costo["Costo manual total"].sum() / con_costo["Cantidad"].sum()) if len(con_costo) else 0.0
        precio_u = float(v_ytd["Precio neto total"].sum() / v_ytd["Cantidad"].sum()) if v_ytd["Cantidad"].sum() else 0.0

        v90 = ventana_90[ventana_90["familia"] == familia]
        muestra_mix = v90 if v90["unid"].sum() >= 50 else v_ytd

        # Precio y margen ACTUALES (90 días) para pasar unidades a pesos -- el
        # precio por prenda viene subiendo en el año, el promedio YTD lo
        # subestima. Margen solo con líneas que tienen costo registrado (las
        # de costo 0 inflarían la utilidad al 100%).
        muestra_precio = v90 if v90["Cantidad"].sum() >= 30 else v_ytd
        precio_actual = float(muestra_precio["Precio neto total"].sum() / muestra_precio["Cantidad"].sum()) if muestra_precio["Cantidad"].sum() else precio_u
        con_c = muestra_precio[muestra_precio["Costo manual unitario"] > 0]
        margen = float(1 - con_c["Costo manual total"].sum() / con_c["Precio neto total"].sum()) if con_c["Precio neto total"].sum() > 0 else 0.0

        # Referencias (ropa) o subcategorías (accesorios -- demasiados SKU para ir uno por uno)
        clave = "Categoría artículo" if es_acc else "ref"
        por_item = v90[~v90["ref"].str.upper().isin(REFERENCIAS_EXCLUIDAS)].groupby(clave)["unid"].sum().sort_values(ascending=False)
        total_90 = v90["unid"].sum()
        items = []
        acumulado = 0.0
        for nombre_item, unid in por_item.items():
            if total_90 <= 0 or (not es_acc and (len(items) >= MAX_REFERENCIAS or acumulado >= COBERTURA_REFERENCIAS)):
                break
            if unid < 3:
                break
            part = unid / total_90
            acumulado += part
            sub_v = v90[v90[clave] == nombre_item]
            sub_ytd = v_ytd[v_ytd[clave] == nombre_item]
            sub_art = art_f[art_f["Categoría" if es_acc else "ref"] == nombre_item]
            con_c = sub_art[sub_art["Costo manual"] > 0]
            costo_item = float(con_c["Costo manual"].mean()) if len(con_c) else costo_u
            items.append({
                "nombre": nombre_item,
                "participacion": round(float(part), 4),
                "venta_90d": int(round(unid)),
                "venta_ytd": int(round(sub_ytd["unid"].sum())),
                "stock": int(sub_art["Stock total empresa"].sum()),
                "costo_unitario": round(costo_item),
                "precio_promedio": round(float(sub_ytd["Precio neto total"].sum() / sub_ytd["Cantidad"].sum())) if sub_ytd["Cantidad"].sum() else 0,
                "colores": [] if es_acc else _mix(sub_v[sub_v["color"].notna()].groupby("color")["unid"].sum(), 4),
                "tallas": [] if es_acc else _orden_tallas(_mix(sub_v.groupby("talla")["unid"].sum(), 6)),
            })
        stock_items = sum(i["stock"] for i in items)
        otros_part = max(0.0, 1 - sum(i["participacion"] for i in items))

        familias_out.append({
            "familia": familia,
            "es_accesorio": es_acc,
            "base": base,
            "venta_90d": int(round(total_90)),
            "venta_ytd": int(round(v_ytd["unid"].sum())),
            "venta_temporada_anterior": int(round(temp_hist[temp_hist["familia"] == familia]["unid"].sum())),
            "stock_total": stock_total,
            "stock_vivo": stock_vivo,
            "costo_unitario": round(costo_u),
            "precio_promedio": round(precio_u),
            "precio_actual": round(precio_actual),
            "margen": round(margen, 4),
            "items": items,
            "otros": {"participacion": round(otros_part, 4), "stock": max(0, stock_vivo - stock_items)},
            "mix_colores": [] if es_acc else _mix(muestra_mix[muestra_mix["color"].notna()].groupby("color")["unid"].sum(), 8),
            "mix_tallas": [] if es_acc else _orden_tallas(_mix(muestra_mix.groupby("talla")["unid"].sum(), 10)),
        })

    familias_out.sort(key=lambda f: -sum(sum(v) for v in f["base"].values()))

    # Unidades -> pesos por local: precio actual de cada familia x un ajuste
    # por local calibrado contra septiembre real (cada local tiene su propia
    # mezcla de precios dentro de la familia). Verificado 2026-10-02: el
    # método sin ajuste ya daba +-1% de la venta real de septiembre.
    precio_fam = {f["familia"]: f["precio_actual"] for f in familias_out}
    for l in locales_out:
        sub = sep_act[sep_act["cod"] == l["codigo"]]
        estimado = sum(u * precio_fam.get(fam, 0) for fam, u in sub.groupby("familia")["unid"].sum().items())
        real = historico[l["codigo"]]["por_anio_mes"][str(anio)]["Sep"]["neto"]
        l["ajuste_precio"] = round(real / estimado, 4) if estimado else 1.0

        # Escenario metas calibrado en pesos: el % en unidades que hace que
        # OCTUBRE llegue exactamente a la meta, con los mismos precios que usa
        # el dashboard para la venta esperada. Antes se calculaba con el alza
        # de precio promedio del local y quedaba en ~93% de la meta.
        meta_oct = (metas.get(l["codigo"]) or {}).get("10")
        oct_tendencia = sum(f["base"].get(l["nombre"], [0])[0] * precio_fam[f["familia"]] for f in familias_out) * l["ajuste_precio"]
        if meta_oct and oct_tendencia > 0:
            l["pct_meta"] = round((1 + l["pct_tendencia"]) * meta_oct / oct_tendencia - 1, 4)
            l["detalle"] += f" Con la tendencia, octubre daría {_pesos(oct_tendencia)}."

        # % vs base por mes en cada escenario. "gradual": para un local que
        # viene cayendo, la caída se va cerrando de la tendencia actual hasta
        # el ritmo de su meta de octubre en diciembre (1/3, 2/3, 3/3 del camino).
        t = l["pct_tendencia"]
        m = l["pct_meta"] if l["pct_meta"] is not None else t
        gradual = [t + (m - t) * k / 3 for k in (1, 2, 3)] if (t < 0 and m > t) else [t] * 3
        l["pct_meses"] = {
            "tendencia": [round(t, 4)] * 3,
            "gradual": [round(x, 4) for x in gradual],
            "meta": [round(m, 4)] * 3,
        }

    salida = {
        "generado_al": str(hoy.date()),
        "anio": anio,
        "meses": [{"idx": m, "lbl": MESES_ES[m - 1]} for m in MESES_TEMPORADA],
        "estacionalidad_total": [round(x, 3) for x in idx_total],
        "locales": locales_out,
        "familias": familias_out,
    }
    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Estacionalidad sep->oct/nov/dic {anio - 1} (144+433): {[round(x, 2) for x in idx_total]}")
    for l in locales_out:
        meta = f"{l['pct_meta'] * 100:+.1f}%" if l["pct_meta"] is not None else "-"
        gradual = " / ".join(f"{x * 100:+.1f}%" for x in l["pct_meses"]["gradual"])
        print(f"{l['nombre']}: tendencia {l['pct_tendencia'] * 100:+.1f}%  |  gradual {gradual}  |  metas {meta}  |  ajuste precio {l['ajuste_precio']}")
    print(f"\n{'Familia':<14}{'Oct':>8}{'Nov':>8}{'Dic':>8}{'Stock vivo':>12}{'Costo u.':>12}")
    for f in familias_out:
        tot = [sum(v[i] for v in f["base"].values()) for i in range(3)]
        print(f"{f['familia']:<14}{tot[0]:>8.0f}{tot[1]:>8.0f}{tot[2]:>8.0f}{f['stock_vivo']:>12}{f['costo_unitario']:>12,.0f}")
    print(f"\nGuardado en {OUT}")


if __name__ == "__main__":
    main()
