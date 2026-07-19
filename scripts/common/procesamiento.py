"""
Utilidades de limpieza/agregación de los Excel exportados por Effi.
Ver JR ARQUITECTURA_REPLICABLE.md sección 2.3 para el porqué de cada trampa.
"""

import json
import re
from pathlib import Path

import pandas as pd

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

_RE_TALLA_GRANDE = re.compile(r"\s+TALLA\s+\w+(\s+\w+)?$", re.IGNORECASE)
_RE_TALLA = re.compile(r"\s+T(U|S|\d{1,2})$", re.IGNORECASE)


def referencia_base(nombre: str) -> str:
    """Nombre del artículo sin el sufijo de talla (T6, T10, TU, "TALLA GRANDE"...).
    Effi trae una fila por combinación artículo+talla — sin esto, el mismo diseño en
    varias tallas aparece repetido como si fueran productos distintos en cualquier
    listado (top referencias, rentabilidad por categoría, reorden de inventario).
    Mantiene el color: dos colores del mismo diseño quedan como referencias separadas,
    que es lo útil para decidir qué pedir a proveedores o qué se vende más."""
    n = (nombre or "").strip()
    n = _RE_TALLA_GRANDE.sub("", n)
    n = _RE_TALLA.sub("", n)
    return n.strip() or (nombre or "").strip()


def talla_de(nombre: str, referencia: str) -> str:
    """Lo que sobra del nombre completo al quitarle la referencia — la talla."""
    resto = (nombre or "").strip()
    if resto.startswith(referencia):
        resto = resto[len(referencia):].strip()
    return resto or "Única"


def leer_excel_effi(ruta: Path) -> pd.DataFrame:
    """
    Effi tiene DOS formatos de exportación según el flujo:
    - Export síncrono (botón directo en un listado): HTML con extensión .xls/.xlsx,
      números en formato colombiano (3.000.000,00) -> exige decimal="," o pandas
      infla los montos 100x.
    - Export asíncrono (catálogos grandes, se genera en segundo plano y llega por
      notificación): binario .xlsx real (ZIP/PK), números ya como floats nativos.
    Se detecta por la firma de archivo (PK\\x03\\x04 = zip/xlsx real).
    """
    with open(ruta, "rb") as f:
        es_xlsx_real = f.read(4) == b"PK\x03\x04"

    if es_xlsx_real:
        return pd.read_excel(ruta)
    return pd.read_html(str(ruta), encoding="ISO-8859-1", decimal=",", thousands=".")[0]


def encontrar_columna(df: pd.DataFrame, *nombres_posibles: str):
    """Busca una columna por coincidencia aproximada (Effi no siempre exporta el mismo nombre)."""
    candidatos = [n.lower() for n in nombres_posibles]
    for c in df.columns:
        if c.lower().strip() in candidatos or any(n in c.lower() for n in candidatos):
            return c
    return None


def cargar_config(nombre_archivo: str) -> dict:
    ruta = CONFIG_DIR / nombre_archivo
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def calcular_cobertura_inventario(df_inventario: pd.DataFrame, df_ventas: pd.DataFrame,
                                   col_sku: str, col_stock: str, col_sku_venta: str, col_cantidad_venta: str) -> pd.DataFrame:
    """
    Índice de cobertura general = stock_actual / venta_promedio_diaria.
    Usa la ventana definida en config/inventario_config.json (ventana_venta_promedio_dias).
    Devuelve el df de inventario con columnas adicionales: venta_promedio_diaria, dias_cobertura, alerta.
    """
    cfg = cargar_config("inventario_config.json")
    ventana_dias = cfg["ventana_venta_promedio_dias"]

    venta_por_sku = (
        df_ventas.groupby(col_sku_venta)[col_cantidad_venta].sum() / ventana_dias
    ).rename("venta_promedio_diaria")

    resultado = df_inventario.merge(venta_por_sku, left_on=col_sku, right_index=True, how="left")
    resultado["venta_promedio_diaria"] = resultado["venta_promedio_diaria"].fillna(0)
    resultado["dias_cobertura"] = resultado.apply(
        lambda r: (r[col_stock] / r["venta_promedio_diaria"]) if r["venta_promedio_diaria"] > 0 else float("inf"),
        axis=1,
    )

    def _alerta(dias):
        if dias <= cfg["dias_cobertura_critico"]:
            return "crítico"
        if dias <= cfg["dias_cobertura_alerta"]:
            return "alerta"
        return "ok"

    resultado["alerta"] = resultado["dias_cobertura"].apply(_alerta)
    return resultado
