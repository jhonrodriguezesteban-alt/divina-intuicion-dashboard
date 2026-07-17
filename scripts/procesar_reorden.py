"""
Cruza inventario actual (raw_articulos.xlsx) con velocidad de venta
reciente (raw_conceptos.xlsx, últimos 90 días) para calcular el índice de
cobertura por referencia y una sugerencia de cantidad a pedir — el módulo
de "solicitud de pedidos a proveedores" que Divina Intuición pidió
priorizar. Estructura de salida inspirada en el acordeón de Programación
del dashboard de referencia (Grupo Bentley): categoría -> lista de
referencias con estado (crítico/alerta/ok/sin rotación/nuevo) y sugerido.

Umbrales en config/inventario_config.json.
"""

import json
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_config

RAW_ARTICULOS = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_articulos.xlsx"
RAW_CONCEPTOS = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_conceptos.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "reorden.json"

HOY = pd.Timestamp("2026-07-16")
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


def main():
    cfg = cargar_config("inventario_config.json")

    articulos = leer_excel_effi(RAW_ARTICULOS)
    articulos["Stock total empresa"] = pd.to_numeric(articulos["Stock total empresa"], errors="coerce").fillna(0)
    articulos["Costo manual"] = pd.to_numeric(articulos["Costo manual"], errors="coerce").fillna(0)

    conceptos = leer_excel_effi(RAW_CONCEPTOS)
    conceptos["Fecha creación"] = pd.to_datetime(conceptos["Fecha creación"])
    ventas_recientes = conceptos[
        (conceptos["Estado CXC"] == "Pago total") & (conceptos["Fecha creación"] >= INICIO_VENTANA)
    ]
    venta_por_sku = ventas_recientes.groupby("Cod. artículo")["Cantidad"].sum()

    # también: ¿alguna vez se ha vendido? (para distinguir "nuevo sin rotar" de "agotado sin rotar")
    algo_vendido_historico = set(conceptos.loc[conceptos["Estado CXC"] == "Pago total", "Cod. artículo"].unique())

    filas = []
    for _, row in articulos.iterrows():
        sku = row["ID"]
        disponible = int(row["Stock total empresa"])
        venta_ventana = float(venta_por_sku.get(sku, 0))
        venta_diaria = venta_ventana / VENTANA_DIAS
        dias_cobertura = (disponible / venta_diaria) if venta_diaria > 0 else None

        if venta_diaria == 0 and sku not in algo_vendido_historico:
            estado, etiqueta = ("nuevo", "Nuevo / evaluar") if disponible > 0 else ("sin_datos", "Sin datos")
        else:
            estado, etiqueta = _clasificar(disponible, venta_diaria, dias_cobertura or 0, cfg)

        if venta_diaria > 0:
            objetivo = venta_diaria * cfg["dias_cobertura_objetivo"]
            sugerido = max(0, round(objetivo - disponible))
        else:
            sugerido = 0

        if disponible == 0 and venta_diaria == 0 and sku not in algo_vendido_historico:
            continue  # sin stock, nunca vendido: no aporta al reorden

        filas.append({
            "id": int(sku),
            "nombre": row["Nombre"],
            "categoria": row["Categoría"] or "SIN CATEGORÍA",
            "disponible": disponible,
            "venta_90d": int(venta_ventana),
            "rotacion_anualizada": round(venta_diaria * 365) if venta_diaria > 0 else 0,
            "dias_cobertura": round(dias_cobertura, 1) if dias_cobertura is not None else None,
            "estado": estado,
            "estado_label": etiqueta,
            "sugerido": int(sugerido),
        })

    df = pd.DataFrame(filas)

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

    salida = {
        "ventana_dias": VENTANA_DIAS,
        "generado_al": str(HOY.date()),
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

    OUT.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(salida["resumen"], ensure_ascii=False, indent=2))
    print(f"{len(categorias)} categorías. Guardado en {OUT}")


if __name__ == "__main__":
    main()
