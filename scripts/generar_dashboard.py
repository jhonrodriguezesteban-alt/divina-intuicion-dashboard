"""
Motor de generación del dashboard.html — un solo archivo estático, sin build step.
Ver JR ARQUITECTURA_REPLICABLE.md sección 4 para las trampas de f-strings/JS embebido.

Estado actual: esqueleto. Los módulos reales (Mesa de Gerencia, Ventas por Punto de
Venta, Inventario/Rotación, Comisiones) se completan a medida que confirmemos
columnas y datos reales de Effi.
"""

from pathlib import Path

REPORTES_DIR = Path(__file__).resolve().parent.parent / "reportes"
DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "dashboard.html"


def generar_dashboard_html(datos: dict) -> str:
    """Construye el HTML completo del dashboard a partir de los JSON intermedios en reportes/."""
    # TODO: Mesa de Gerencia (KPIs financieros)
    # TODO: Ventas por Punto de Venta (Local 144 / 107 / 433)
    # TODO: Inventario / Rotación (índice de cobertura, alertas de reorden)
    # TODO: Comercial / Comisiones (pendiente escalafón del negocio)
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Divina Intuición — Dashboard Gerencial</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; padding: 2rem; background:#f7f5f3; color:#2b2b2b; }}
  h1 {{ margin-bottom: .25rem; }}
  .placeholder {{ padding: 3rem; text-align:center; border: 2px dashed #ccc; border-radius: 12px; color:#888; }}
</style>
</head>
<body>
  <h1>Divina Intuición — Dashboard Gerencial</h1>
  <p>Local 144 · Local 107 · Local 433</p>
  <div class="placeholder">
    Aún sin datos reales de Effi. Este HTML se regenera con
    <code>python3 scripts/reporte_completo.py</code> una vez tengamos acceso confirmado.
  </div>
</body>
</html>
"""


def publicar(html: str):
    """Escribe dashboard.html. La publicación a GitHub Pages (git commit + push) se hace
    aparte, y solo desde reporte_completo.py / actualizar_dashboard.py — nunca desde un script de prueba."""
    DASHBOARD_PATH.write_text(html, encoding="utf-8")
    print(f"dashboard.html generado en {DASHBOARD_PATH}")


if __name__ == "__main__":
    publicar(generar_dashboard_html({}))
