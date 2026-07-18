"""
Cruza inventario actual (raw_articulos.xlsx) con velocidad de venta
reciente (raw_conceptos.xlsx, últimos 90 días) para calcular el índice de
cobertura y una sugerencia de cantidad a pedir — el módulo de "solicitud
de pedidos a proveedores" que Divina Intuición pidió priorizar.

Se agrupa por REFERENCIA (nombre del artículo sin la talla), no por SKU:
Effi trae una fila por combinación artículo+talla, y mostrarlas sueltas
hace que un mismo diseño en varias tallas aparezca como "productos"
distintos en la lista. El campo "Texto auxiliar" de Effi debería servir
para esto pero viene inconsistente (a veces incluye el color, a veces
no), así que la talla se quita del nombre con una regla propia — ver
_referencia_base(). Cada referencia agregada trae sus tallas/variantes
como detalle expandible (mismo patrón que el resto del dashboard).

Estructura de salida inspirada en el acordeón de Programación del
dashboard de referencia (Grupo Bentley): categoría -> lista de
referencias con estado (crítico/alerta/ok/sin rotación/nuevo) y sugerido.

Umbrales en config/inventario_config.json.
"""

import json
import re
from pathlib import Path

import pandas as pd

from common.procesamiento import leer_excel_effi, cargar_config

RAW_ARTICULOS = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_articulos.xlsx"
RAW_CONCEPTOS = Path(__file__).resolve().parent.parent / "reportes" / "raw" / "raw_conceptos.xlsx"
OUT = Path(__file__).resolve().parent.parent / "reportes" / "reorden.json"

HOY = pd.Timestamp.now().normalize()
VENTANA_DIAS = 90
INICIO_VENTANA = HOY - pd.Timedelta(days=VENTANA_DIAS)

_RE_TALLA_GRANDE = re.compile(r"\s+TALLA\s+\w+(\s+\w+)?$", re.IGNORECASE)
_RE_TALLA = re.compile(r"\s+T(U|S|\d{1,2})$", re.IGNORECASE)


def _referencia_base(nombre: str) -> str:
    """Nombre del artículo sin el sufijo de talla (T6, T10, TU, "TALLA GRANDE"...).
    Mantiene el color — dos colores del mismo diseño quedan como referencias
    separadas, que es lo útil para decidir qué pedir a proveedores."""
    n = (nombre or "").strip()
    n = _RE_TALLA_GRANDE.sub("", n)
    n = _RE_TALLA.sub("", n)
    return n.strip() or (nombre or "").strip()


def _talla_de(nombre: str, referencia: str) -> str:
    """Lo que sobra del nombre completo al quitarle la referencia — la talla."""
    resto = (nombre or "").strip()
    if resto.startswith(referencia):
        resto = resto[len(referencia):].strip()
    return resto or "Única"


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
    articulos["Categoría"] = articulos["Categoría"].fillna("SIN CATEGORÍA")
    articulos["referencia"] = articulos["Nombre"].apply(_referencia_base)

    conceptos = leer_excel_effi(RAW_CONCEPTOS)
    conceptos["Fecha creación"] = pd.to_datetime(conceptos["Fecha creación"])
    ventas_recientes = conceptos[
        (conceptos["Estado CXC"] == "Pago total") & (conceptos["Fecha creación"] >= INICIO_VENTANA)
    ]
    venta_por_sku = ventas_recientes.groupby("Cod. artículo")["Cantidad"].sum()
    algo_vendido_historico = set(conceptos.loc[conceptos["Estado CXC"] == "Pago total", "Cod. artículo"].unique())

    articulos["venta_90d"] = articulos["ID"].map(venta_por_sku).fillna(0)
    articulos["vendido_alguna_vez"] = articulos["ID"].isin(algo_vendido_historico)

    filas = []
    for (categoria, referencia), grupo in articulos.groupby(["Categoría", "referencia"]):
        disponible = int(grupo["Stock total empresa"].sum())
        venta_ventana = float(grupo["venta_90d"].sum())
        venta_diaria = venta_ventana / VENTANA_DIAS
        dias_cobertura = (disponible / venta_diaria) if venta_diaria > 0 else None
        vendido_alguna_vez = bool(grupo["vendido_alguna_vez"].any())

        if venta_diaria == 0 and not vendido_alguna_vez:
            estado, etiqueta = ("nuevo", "Nuevo / evaluar") if disponible > 0 else ("sin_datos", "Sin datos")
        else:
            estado, etiqueta = _clasificar(disponible, venta_diaria, dias_cobertura or 0, cfg)

        if venta_diaria > 0:
            objetivo = venta_diaria * cfg["dias_cobertura_objetivo"]
            sugerido = max(0, round(objetivo - disponible))
        else:
            sugerido = 0

        if disponible == 0 and venta_diaria == 0 and not vendido_alguna_vez:
            continue  # sin stock, nunca vendido: no aporta al reorden

        variantes = [
            {
                "id": int(r["ID"]),
                "talla": _talla_de(r["Nombre"], referencia),
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
            "sugerido": int(sugerido),
            "num_variantes": len(variantes),
            "variantes": variantes,
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
    print(f"{len(categorias)} categorías, {len(df)} referencias (antes por SKU individual). Guardado en {OUT}")


if __name__ == "__main__":
    main()
