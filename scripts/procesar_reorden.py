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


def _sugerido(venta_diaria, disponible, cfg):
    if venta_diaria <= 0:
        return 0
    objetivo = venta_diaria * cfg["dias_cobertura_objetivo"]
    return max(0, round(objetivo - disponible))


def _procesar_ropa(articulos: pd.DataFrame, cfg: dict) -> dict:
    filas = []
    for (categoria, referencia), grupo in articulos.groupby(["Categoría", "referencia"]):
        disponible = int(grupo["Stock total empresa"].sum())
        venta_ventana = float(grupo["venta_90d"].sum())
        venta_diaria = venta_ventana / VENTANA_DIAS
        dias_cobertura = (disponible / venta_diaria) if venta_diaria > 0 else None
        vendido_alguna_vez = bool(grupo["vendido_alguna_vez"].any())

        if disponible == 0 and venta_diaria == 0 and not vendido_alguna_vez:
            continue  # sin stock, nunca vendido: no aporta al reorden

        estado, etiqueta = _estado_fila(disponible, venta_diaria, dias_cobertura, vendido_alguna_vez, cfg)

        variantes = [
            {
                "id": int(r["ID"]),
                "talla": talla_de(r["Nombre"], referencia),
                "disponible": int(r["Stock total empresa"]),
            }
            for _, r in grupo.sort_values("Nombre").iterrows()
        ]

        filas.append({
            "referencia": referencia,
            "categoria": categoria,
            "disponible": disponible,
            "venta_90d": int(venta_ventana),
            "rotacion_anualizada": round(venta_diaria * 365) if venta_diaria > 0 else 0,
            "dias_cobertura": round(dias_cobertura, 1) if dias_cobertura is not None else None,
            "estado": estado,
            "estado_label": etiqueta,
            "sugerido": int(_sugerido(venta_diaria, disponible, cfg)),
            "num_variantes": len(variantes),
            "variantes": variantes,
        })

    df = pd.DataFrame(filas)
    if not len(df):
        return {"resumen": {"total_referencias": 0, "criticos": 0, "alerta": 0, "sin_rotacion": 0,
                             "nuevos": 0, "unidades_sugeridas_total": 0}, "categorias": []}

    categorias = []
    for cat, grupo in df.groupby("categoria"):
        categorias.append({
            "categoria": cat,
            "num_refs": int(len(grupo)),
            "uds_disponibles": int(grupo["disponible"].sum()),
            "num_criticos": int((grupo["estado"] == "critico").sum()),
            "num_alerta": int((grupo["estado"] == "alerta").sum()),
            "unidades_sugeridas": int(grupo["sugerido"].sum()),
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
        },
        "categorias": categorias,
    }


def _procesar_accesorios(articulos: pd.DataFrame, cfg: dict) -> dict:
    filas = []
    for categoria, grupo in articulos.groupby("Categoría"):
        disponible = int(grupo["Stock total empresa"].sum())
        venta_ventana = float(grupo["venta_90d"].sum())
        venta_diaria = venta_ventana / VENTANA_DIAS
        dias_cobertura = (disponible / venta_diaria) if venta_diaria > 0 else None
        vendido_alguna_vez = bool(grupo["vendido_alguna_vez"].any())

        if disponible == 0 and venta_diaria == 0 and not vendido_alguna_vez:
            continue

        estado, etiqueta = _estado_fila(disponible, venta_diaria, dias_cobertura, vendido_alguna_vez, cfg)

        filas.append({
            "categoria": categoria,
            "disponible": disponible,
            "venta_90d": int(venta_ventana),
            "rotacion_anualizada": round(venta_diaria * 365) if venta_diaria > 0 else 0,
            "dias_cobertura": round(dias_cobertura, 1) if dias_cobertura is not None else None,
            "estado": estado,
            "estado_label": etiqueta,
            "sugerido": int(_sugerido(venta_diaria, disponible, cfg)),
            "num_referencias": int(grupo["referencia"].nunique()),
        })

    df = pd.DataFrame(filas)
    if not len(df):
        return {"resumen": {"total_categorias": 0, "criticos": 0, "alerta": 0, "sin_rotacion": 0,
                             "nuevos": 0, "unidades_sugeridas_total": 0}, "categorias": []}

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
        },
        "categorias": df.to_dict(orient="records"),
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
    ventas_recientes = conceptos[
        (conceptos["Estado CXC"] == "Pago total") & (conceptos["Fecha creación"] >= INICIO_VENTANA)
    ]
    venta_por_sku = ventas_recientes.groupby("Cod. artículo")["Cantidad"].sum()
    algo_vendido_historico = set(conceptos.loc[conceptos["Estado CXC"] == "Pago total", "Cod. artículo"].unique())

    articulos["venta_90d"] = articulos["ID"].map(venta_por_sku).fillna(0)
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
