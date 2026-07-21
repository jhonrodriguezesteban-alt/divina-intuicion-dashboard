"""
Utilidades de limpieza/agregación de los Excel exportados por Effi.
Ver JR ARQUITECTURA_REPLICABLE.md sección 2.3 para el porqué de cada trampa.
"""

import json
import re
from pathlib import Path

import pandas as pd

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
RAW_DIR = Path(__file__).resolve().parent.parent.parent / "reportes" / "raw"

_COLUMNAS_CONCEPTOS = [
    "Sucursal", "Estado CXC", "Fecha creación", "Categoría artículo", "Cod. artículo",
    "Descripción artículo", "Cantidad", "Costo manual unitario", "Costo manual total",
    "Precio neto total", "Utilidad total (costo manual)",
]

_RE_TALLA_GRANDE = re.compile(r"\s+TALLA\s+\w+(\s+\w+)?$", re.IGNORECASE)
_RE_TALLA = re.compile(r"\s+T-?(XXL|XS|XL|U|S|M|L|\d{1,2})$", re.IGNORECASE)

# Vocabulario de color detectado analizando reportes/raw/raw_articulos.xlsx real
# (ver sesión de ajuste de referencia_base) -- una base ("VERDE") opcionalmente
# seguida de un segundo color separado por "/" ("NEGRO/BLANCO") y/o un
# modificador ("VERDE OLIVA", "AZUL CLARO", "ANIMAL PRINT").
_COLORES_BASE = [
    "NEGRO", "BLANCO", "BEIGE", "CAFE", "MARFIL", "VINOTINTO", "CAMEL", "GRIS",
    "AMARILLO", "VERDE", "ROSA", "ROSADO", "AZUL", "ROJO", "MULTICOLOR",
    "MORADO", "AVENA", "TERRACOTA", "NARANJA", "FUCSIA", "TURQUESA", "LILA",
    "CORAL", "PERLA", "PLATA", "DORADO", "CHOCOLATE", "KAKI", "CAQUI",
    "MOSTAZA", "VINO", "PLOMO", "HUESO", "CRUDO", "NUDE", "ARENA",
    "PETROLEO", "ESMERALDA", "GUAYABA", "LADRILLO", "TABACO", "ANIMAL",
]
_COLOR_MODIFICADORES = [
    "CLARO", "CLARA", "OSCURO", "OSCURA", "BEBE", "MILITAR", "NOCHE",
    "BRILLANTE", "REY", "OLIVA", "BOTELLA", "PINO", "PRINT",
]
_colores_pat = "|".join(sorted(_COLORES_BASE, key=len, reverse=True))
_mod_pat = "|".join(sorted(_COLOR_MODIFICADORES, key=len, reverse=True))
_RE_COLOR = re.compile(
    rf"\s+(?:{_colores_pat})(?:/(?:{_colores_pat}))?(?:\s+(?:{_mod_pat}))?$",
    re.IGNORECASE,
)


def referencia_base(nombre: str) -> str:
    """Nombre del artículo sin el sufijo de talla (T6, T10, TU, TL, TXS,
    "TALLA GRANDE"...) NI de color (NEGRO, AZUL CLARO, ANIMAL PRINT...).
    Effi trae una fila por combinación artículo+talla+color — sin esto, el
    mismo diseño en varias tallas/colores aparece repetido como si fueran
    productos distintos en cualquier listado (top referencias, rentabilidad
    por categoría, reorden de inventario). talla_de() se encarga de mostrar
    lo que sobra (color + talla juntos) como detalle expandible por variante.

    A propósito NO toca sufijos "$precio" pegados al nombre (error de
    captura de Effi en algunos accesorios, ej. "CADENA $12000"): si se
    quitara el precio, decenas de accesorios distintos que solo se
    diferencian por ese precio quedarían fusionados en una sola referencia
    genérica ("CADENA") -- verificado contra el catálogo real."""
    n = (nombre or "").strip()
    n = _RE_TALLA_GRANDE.sub("", n)
    n = _RE_TALLA.sub("", n)
    n = _RE_COLOR.sub("", n)
    return n.strip() or (nombre or "").strip()


def talla_de(nombre: str, referencia: str) -> str:
    """Lo que sobra del nombre completo al quitarle la referencia -- ahora que
    referencia_base() también quita el color, esto devuelve color+talla juntos
    (ej. "Negro T8"), que es justo la etiqueta de variante que se muestra al
    desplegar una referencia."""
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


def cargar_conceptos_combinados() -> pd.DataFrame:
    """Detalle por línea/artículo, remisiones + facturas, con el mismo esquema
    de columnas (Sucursal, Estado CXC, Fecha creación, Categoría artículo,
    Cod. artículo, Descripción artículo, Cantidad, costos, Precio neto total,
    Utilidad total). Usan Top Referencias, Rentabilidad por categoría y Reorden.

    El "Reporte de conceptos" de facturas no trae Estado CXC por línea (solo
    "Vigencia factura": Vigente/Anulada) -- se cruza con el documento
    (raw_facturas_completo.xlsx, por "ID interno") para traer el Estado CXC
    real y poder filtrar "Pago total" igual que en remisiones. Sin esto, una
    factura "Pendiente de cobro" contaría como venta cerrada.
    """
    remisiones = leer_excel_effi(RAW_DIR / "raw_conceptos.xlsx")[_COLUMNAS_CONCEPTOS].copy()
    marcos = [remisiones]

    ruta_conceptos_facturas = RAW_DIR / "raw_conceptos_facturas.xlsx"
    ruta_facturas = RAW_DIR / "raw_facturas_completo.xlsx"
    if ruta_conceptos_facturas.exists() and ruta_facturas.exists():
        conceptos_f = leer_excel_effi(ruta_conceptos_facturas)
        facturas = leer_excel_effi(ruta_facturas)[["ID interno", "Estado CXC"]]
        conceptos_f = conceptos_f.merge(facturas, on="ID interno", how="left")
        conceptos_f = conceptos_f.rename(columns={"Fecha creación factura": "Fecha creación"})
        conceptos_f = conceptos_f[_COLUMNAS_CONCEPTOS]
        marcos.append(conceptos_f)

    return pd.concat(marcos, ignore_index=True)
