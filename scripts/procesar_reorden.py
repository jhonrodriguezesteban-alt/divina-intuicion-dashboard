"""
Cruza inventario actual (raw_articulos.xlsx) con velocidad de venta
reciente (conceptos combinados, últimos 90 días) para calcular el índice
de cobertura y una sugerencia de cantidad a pedir — el módulo de
"solicitud de pedidos a proveedores" que Divina Intuición pidió priorizar.

Ropa vs accesorios se tratan distinto (config/categorias_accesorios.json):
- Ropa: por REFERENCIA (nombre del artículo sin la talla). Effi trae una
  fila por combinación artículo+talla, y mostrarlas sueltas hace que un
  mismo diseño en varias tallas aparezca como "productos" distintos en la
  lista — ver common.procesamiento.referencia_base(). Cada referencia
  agregada trae sus tallas/variantes como detalle expandible.
- Accesorios: por CATEGORÍA completa (aretes, anillos, pulseras...) --
  demasiada variedad de SKU para que el seguimiento por referencia
  individual sea manejable; lo que importa ahí es el ritmo de la
  categoría completa, no de cada diseño puntual.

Estructura de salida inspirada en el acordeón de Programación del
dashboard de referencia (Grupo Bentley): categoría -> lista de
referencias con estado (crítico/alerta/ok/sin rotación/nuevo) y sugerido.

La cantidad sugerida no solo mira el ritmo plano de los últimos 90 días:
se ajusta por la tendencia interanual (misma ventana de 90 días vs hace un
año, ver _tendencia_interanual) para no quedarse corto pidiendo si un
producto viene creciendo, ni sobre-pedir si viene cayendo. Los días de
cobertura (para saber qué tan urgente es) sí usan el ritmo real reciente,
sin ajustar -- son preguntas distintas. También se calcula el costo/
inversión sugerida (Costo manual x sugerido) para dimensionar en pesos
cuánto implica surtir lo que aparece en la lista.

Umbrales en config/inventario_config.json.
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_conceptos_combinados, cargar_config, referencia_base, talla_de

RAW_ARTICULOS = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_articulos.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "reorden.json"

HOY = pd.Timestamp.now().normalize()
VENTANA_DIAS = 90
INICIO_VENTANA = HOY - pd.Timedelta(days=VENTANA_DIAS)
# Misma ventana de 90 días pero de hace un año, para comparar manzanas con
# manzanas (estacionalidad) al medir si un producto viene creciendo o cayendo.
INICIO_VENTANA_ANIO_PASADO = INICIO_VENTANA - pd.Timedelta(days=365)
FIN_VENTANA_ANIO_PASADO = HOY - pd.Timedelta(days=365)
INICIO_ANIO = pd.Timestamp(year=HOY.year, month=1, day=1)


def _clasificar(disponible, venta_diaria, dias_cobertura, cfg):
    if venta_diaria == 0:
        return ("sin_rotacion", "Sin rotación 90d") if disponible > 0 else ("agotado", "Agotado, sin rotación")
    if dias_cobertura <= cfg["dias_cobertura_critico"]:
        return "critico", "Crítico"
    if dias_cobertura <= cfg["dias_cobertura_alerta"]:
        return "alerta", "Alerta"
    return "ok", "Cobertura ok"


def _estado_fila(disponible, venta_diaria, dias_cobertura, vendido_alguna_vez, cfg):
    if venta_diaria == 0 and not vendido_alguna_vez:
        return ("nuevo", "Nuevo / evaluar") if disponible > 0 else ("sin_datos", "Sin datos")
    return _clasificar(disponible, venta_diaria, dias_cobertura or 0, cfg)


def _tendencia_interanual(venta_actual, venta_anio_pasado, minimo_base=3, tope=(-0.6, 2.0)):
    """% de crecimiento comparando la ventana de 90 días actual contra la
    misma ventana de hace un año. Un promedio plano de los últimos 90 días
    no distingue un producto que viene en caída de uno que viene en alza --
    esto captura esa tendencia para ajustar cuánto pedir, no solo cuánto se
    vendió últimamente. Se exige una base mínima el año pasado (si no, un
    salto de 1 a 4 unidades "creciera" 300% sin significar nada) y se acota
    el rango para que un caso extremo no dispare el sugerido."""
    if venta_anio_pasado < minimo_base:
        return None
    crecimiento = (venta_actual - venta_anio_pasado) / venta_anio_pasado
    return max(tope[0], min(tope[1], crecimiento))


def _venta_diaria_ajustada(venta_diaria, crecimiento):
    """Cuánto pedir mira hacia adelante, así que se ajusta por la tendencia
    interanual; cuántos días de cobertura quedan (_clasificar) sigue usando
    el ritmo real de los últimos 90 días -- son preguntas distintas."""
    if crecimiento is None:
        return venta_diaria
    return venta_diaria * (1 + crecimiento)


def _sugerido(venta_diaria_ajustada, disponible, cfg):
    if venta_diaria_ajustada <= 0:
        return 0
    objetivo = venta_diaria_ajustada * cfg["dias_cobertura_objetivo"]
    return max(0, round(objetivo - disponible))


def _costo_unitario(grupo: pd.DataFrame) -> float:
    costos_validos = grupo.loc[grupo["Costo manual"] > 0, "Costo manual"]
    return float(costos_validos.mean()) if len(costos_validos) else 0.0


def _distribuir_sugerido_variantes(disponibles: list, sugerido: int) -> list:
    """El sugerido se calcula por REFERENCIA (ej. "Jean Melisa: +2"), pero
    Jenifer necesita saber qué talla/color pedir, no solo cuántas unidades
    en total -- "+2" sin más no dice si son 2 de la misma talla o una de
    cada una. Se reparte nivelando primero las variantes con menos stock
    (como llenar de agua los vasos más vacíos hasta que quedan parejos),
    sin usar venta por variante: con 90 días de ventana, la venta de una
    sola combinación color+talla es demasiado poca para proyectar algo
    confiable -- el nivel de stock ya disponible sí es un dato sólido."""
    n = len(disponibles)
    if n == 0 or sugerido <= 0:
        return [0] * n
    if n == 1:
        return [sugerido]

    orden = sorted(range(n), key=lambda i: disponibles[i])
    niveles = [float(disponibles[i]) for i in orden]
    restante = float(sugerido)
    nivel_actual = niveles[0]
    i = 0
    while i < n - 1 and restante > 0:
        siguiente = niveles[i + 1]
        tam_grupo = i + 1
        necesario = (siguiente - nivel_actual) * tam_grupo
        if restante >= necesario:
            restante -= necesario
            nivel_actual = siguiente
            i += 1
        else:
            nivel_actual += restante / tam_grupo
            restante = 0
    if restante > 0:
        nivel_actual += restante / n
        restante = 0

    asignado_orden = [max(0.0, nivel_actual - niveles[k]) for k in range(n)]
    base = [int(a) for a in asignado_orden]  # trunca; se completa abajo por mayor resto
    falta = sugerido - sum(base)
    restos_desc = sorted(range(n), key=lambda k: (asignado_orden[k] - base[k]), reverse=True)
    for k in restos_desc[:falta]:
        base[k] += 1

    resultado = [0] * n
    for pos, idx_original in enumerate(orden):
        resultado[idx_original] = base[pos]
    return resultado


def _limpiar_nan(obj):
    """pandas convierte los None de dias_cobertura/tendencia_interanual en
    NaN al pasar por un DataFrame (aunque la columna venga de una lista de
    dicts con None explícito) -- json.dumps escribe eso como el literal
    `NaN`, que rompe el contrato "null = sin dato" que espera el dashboard.
    Se limpia recursivo justo antes de guardar, ya con todo en dicts/listas."""
    if isinstance(obj, float) and pd.isna(obj):
        return None
    if isinstance(obj, dict):
        return {k: _limpiar_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_limpiar_nan(v) for v in obj]
    return obj


def _procesar_ropa(articulos: pd.DataFrame, cfg: dict) -> dict:
    filas = []
    for (categoria, referencia), grupo in articulos.groupby(["Categoría", "referencia"]):
        disponible = int(grupo["Stock total empresa"].sum())
        venta_ventana = float(grupo["venta_90d"].sum())
        venta_diaria = venta_ventana / VENTANA_DIAS
        venta_ventana_anio_pasado = float(grupo["venta_90d_anio_pasado"].sum())
        venta_ytd = int(grupo["venta_ytd"].sum())
        dias_cobertura = (disponible / venta_diaria) if venta_diaria > 0 else None
        vendido_alguna_vez = bool(grupo["vendido_alguna_vez"].any())

        if disponible == 0 and venta_diaria == 0 and not vendido_alguna_vez:
            continue  # sin stock, nunca vendido: no aporta al reorden

        estado, etiqueta = _estado_fila(disponible, venta_diaria, dias_cobertura, vendido_alguna_vez, cfg)
        crecimiento = _tendencia_interanual(venta_ventana, venta_ventana_anio_pasado)
        venta_diaria_ajustada = _venta_diaria_ajustada(venta_diaria, crecimiento)
        sugerido = int(_sugerido(venta_diaria_ajustada, disponible, cfg))
        costo_unitario = _costo_unitario(grupo)

        filas_variantes = grupo.sort_values("Nombre")
        disponibles_variantes = [int(v) for v in filas_variantes["Stock total empresa"]]
        sugerido_por_variante = _distribuir_sugerido_variantes(disponibles_variantes, sugerido)
        variantes = [
            {
                "id": int(r["ID"]),
                "talla": talla_de(r["Nombre"], referencia),
                "disponible": int(r["Stock total empresa"]),
                "sugerido": sugerido_por_variante[idx],
            }
            for idx, (_, r) in enumerate(filas_variantes.iterrows())
        ]

        filas.append({
            "referencia": referencia,
            "categoria": categoria,
            "disponible": disponible,
            "venta_90d": int(venta_ventana),
            "venta_ytd": venta_ytd,
            "rotacion_anualizada": round(venta_diaria * 365) if venta_diaria > 0 else 0,
            "dias_cobertura": round(dias_cobertura, 1) if dias_cobertura is not None else None,
            "tendencia_interanual": round(crecimiento * 100) if crecimiento is not None else None,
            "estado": estado,
            "estado_label": etiqueta,
            "sugerido": sugerido,
            "costo_unitario": round(costo_unitario),
            "inversion_sugerida": round(sugerido * costo_unitario),
            "num_variantes": len(variantes),
            "variantes": variantes,
        })

    df = pd.DataFrame(filas)
    if not len(df):
        return {"resumen": {"total_referencias": 0, "criticos": 0, "alerta": 0, "sin_rotacion": 0,
                             "nuevos": 0, "unidades_sugeridas_total": 0, "inversion_sugerida_total": 0},
                "categorias": []}

    categorias = []
    for cat, grupo in df.groupby("categoria"):
        categorias.append({
            "categoria": cat,
            "num_refs": int(len(grupo)),
            "uds_disponibles": int(grupo["disponible"].sum()),
            "num_criticos": int((grupo["estado"] == "critico").sum()),
            "num_alerta": int((grupo["estado"] == "alerta").sum()),
            "unidades_sugeridas": int(grupo["sugerido"].sum()),
            "inversion_sugerida": round(float(grupo["inversion_sugerida"].sum())),
            "referencias": grupo.sort_values(
                by=["estado", "dias_cobertura"], key=lambda s: s if s.name != "dias_cobertura" else s.fillna(999999)
            ).to_dict(orient="records"),
        })
    categorias.sort(key=lambda c: -(c["num_criticos"] * 1000 + c["num_alerta"]))

    return {
        "resumen": {
            "total_referencias": int(len(df)),
            "criticos": int((df["estado"] == "critico").sum()),
            "alerta": int((df["estado"] == "alerta").sum()),
            "sin_rotacion": int((df["estado"] == "sin_rotacion").sum()),
            "nuevos": int((df["estado"] == "nuevo").sum()),
            "unidades_sugeridas_total": int(df["sugerido"].sum()),
            "inversion_sugerida_total": round(float(df["inversion_sugerida"].sum())),
        },
        "categorias": _limpiar_nan(categorias),
    }


def _procesar_accesorios(articulos: pd.DataFrame, cfg: dict) -> dict:
    filas = []
    for categoria, grupo in articulos.groupby("Categoría"):
        disponible = int(grupo["Stock total empresa"].sum())
        venta_ventana = float(grupo["venta_90d"].sum())
        venta_diaria = venta_ventana / VENTANA_DIAS
        venta_ventana_anio_pasado = float(grupo["venta_90d_anio_pasado"].sum())
        venta_ytd = int(grupo["venta_ytd"].sum())
        dias_cobertura = (disponible / venta_diaria) if venta_diaria > 0 else None
        vendido_alguna_vez = bool(grupo["vendido_alguna_vez"].any())

        if disponible == 0 and venta_diaria == 0 and not vendido_alguna_vez:
            continue

        estado, etiqueta = _estado_fila(disponible, venta_diaria, dias_cobertura, vendido_alguna_vez, cfg)
        crecimiento = _tendencia_interanual(venta_ventana, venta_ventana_anio_pasado)
        venta_diaria_ajustada = _venta_diaria_ajustada(venta_diaria, crecimiento)
        sugerido = int(_sugerido(venta_diaria_ajustada, disponible, cfg))
        costo_unitario = _costo_unitario(grupo)

        filas.append({
            "categoria": categoria,
            "disponible": disponible,
            "venta_90d": int(venta_ventana),
            "venta_ytd": venta_ytd,
            "rotacion_anualizada": round(venta_diaria * 365) if venta_diaria > 0 else 0,
            "dias_cobertura": round(dias_cobertura, 1) if dias_cobertura is not None else None,
            "tendencia_interanual": round(crecimiento * 100) if crecimiento is not None else None,
            "estado": estado,
            "estado_label": etiqueta,
            "sugerido": sugerido,
            "costo_unitario": round(costo_unitario),
            "inversion_sugerida": round(sugerido * costo_unitario),
            "num_referencias": int(grupo["referencia"].nunique()),
        })

    df = pd.DataFrame(filas)
    if not len(df):
        return {"resumen": {"total_categorias": 0, "criticos": 0, "alerta": 0, "sin_rotacion": 0,
                             "nuevos": 0, "unidades_sugeridas_total": 0, "inversion_sugerida_total": 0},
                "categorias": []}

    df = df.sort_values(
        by=["estado", "dias_cobertura"], key=lambda s: s if s.name != "dias_cobertura" else s.fillna(999999)
    )

    return {
        "resumen": {
            "total_categorias": int(len(df)),
            "criticos": int((df["estado"] == "critico").sum()),
            "alerta": int((df["estado"] == "alerta").sum()),
            "sin_rotacion": int((df["estado"] == "sin_rotacion").sum()),
            "nuevos": int((df["estado"] == "nuevo").sum()),
            "unidades_sugeridas_total": int(df["sugerido"].sum()),
            "inversion_sugerida_total": round(float(df["inversion_sugerida"].sum())),
        },
        "categorias": _limpiar_nan(df.to_dict(orient="records")),
    }


def main():
    cfg = cargar_config("inventario_config.json")
    categorias_accesorios = set(cargar_config("categorias_accesorios.json")["categorias"])

    articulos = leer_excel_effi(RAW_ARTICULOS)
    articulos["Stock total empresa"] = pd.to_numeric(articulos["Stock total empresa"], errors="coerce").fillna(0)
    articulos["Costo manual"] = pd.to_numeric(articulos["Costo manual"], errors="coerce").fillna(0)
    articulos["Categoría"] = articulos["Categoría"].fillna("SIN CATEGORÍA")
    articulos["referencia"] = articulos["Nombre"].apply(referencia_base)
    articulos["es_accesorio"] = articulos["Categoría"].isin(categorias_accesorios)

    conceptos = cargar_conceptos_combinados()
    conceptos["Fecha creación"] = pd.to_datetime(conceptos["Fecha creación"])
    pagadas = conceptos[conceptos["Estado CXC"] == "Pago total"]

    ventas_recientes = pagadas[pagadas["Fecha creación"] >= INICIO_VENTANA]
    venta_por_sku = ventas_recientes.groupby("Cod. artículo")["Cantidad"].sum()

    ventas_anio_pasado = pagadas[
        (pagadas["Fecha creación"] >= INICIO_VENTANA_ANIO_PASADO) & (pagadas["Fecha creación"] < FIN_VENTANA_ANIO_PASADO)
    ]
    venta_por_sku_anio_pasado = ventas_anio_pasado.groupby("Cod. artículo")["Cantidad"].sum()

    ventas_ytd = pagadas[pagadas["Fecha creación"] >= INICIO_ANIO]
    venta_por_sku_ytd = ventas_ytd.groupby("Cod. artículo")["Cantidad"].sum()

    algo_vendido_historico = set(pagadas["Cod. artículo"].unique())

    articulos["venta_90d"] = articulos["ID"].map(venta_por_sku).fillna(0)
    articulos["venta_90d_anio_pasado"] = articulos["ID"].map(venta_por_sku_anio_pasado).fillna(0)
    articulos["venta_ytd"] = articulos["ID"].map(venta_por_sku_ytd).fillna(0)
    articulos["vendido_alguna_vez"] = articulos["ID"].isin(algo_vendido_historico)

    ropa_salida = _procesar_ropa(articulos[~articulos["es_accesorio"]], cfg)
    accesorios_salida = _procesar_accesorios(articulos[articulos["es_accesorio"]], cfg)

    salida = {
        "ventana_dias": VENTANA_DIAS,
        "generado_al": str(HOY.date()),
        "ropa": ropa_salida,
        "accesorios": accesorios_salida,
    }

    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Ropa:", json.dumps(ropa_salida["resumen"], ensure_ascii=False))
    print("Accesorios:", json.dumps(accesorios_salida["resumen"], ensure_ascii=False))
    print(f"{len(ropa_salida['categorias'])} categorías de ropa, "
          f"{len(accesorios_salida['categorias'])} categorías de accesorios. Guardado en {OUT}")


if __name__ == "__main__":
    main()
