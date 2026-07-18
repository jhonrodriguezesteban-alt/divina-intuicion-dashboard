"""
Publica dashboard.html + los JSON intermedios a GitHub (git add/commit/push).
Solo debe llamarse desde actualizar_dashboard.py / cierre_dia.py / reporte_completo.py
— nunca desde un script de prueba, para que un experimento no le "pise" el
dashboard real a los usuarios (regla de oro, JR ARQUITECTURA_REPLICABLE.md sección 3).
"""

import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent

ARCHIVOS_A_PUBLICAR = [
    "dashboard.html",
    "reportes/ventas_procesado.json",
    "reportes/ventas_diarias.json",
    "reportes/inventario_procesado.json",
    "reportes/historico_mensual.json",
    "reportes/categorias_referencias.json",
    "reportes/reorden.json",
    "reportes/resumen_dia.txt",
]


def _git(*args):
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True)


def publicar(mensaje: str) -> bool:
    """Hace commit + push de los archivos publicables si hay cambios. Devuelve True si publicó algo nuevo."""
    existentes = [a for a in ARCHIVOS_A_PUBLICAR if (RAIZ / a).exists()]
    resumenes = list((RAIZ / "reportes" / "resumenes").glob("*.txt")) if (RAIZ / "reportes" / "resumenes").exists() else []
    existentes += [str(p.relative_to(RAIZ)) for p in resumenes]
    if not existentes:
        print("Nada que publicar (no hay archivos generados).")
        return False

    _git("add", *existentes)
    diff = _git("diff", "--cached", "--quiet")
    if diff.returncode == 0:
        print("Sin cambios respecto al último commit, no se publica nada nuevo.")
        return False

    commit = _git("commit", "-m", mensaje)
    if commit.returncode != 0:
        print("Error al hacer commit:", commit.stderr)
        return False

    push = _git("push", "origin", "main")
    if push.returncode != 0:
        print("Error al hacer push:", push.stderr)
        return False

    print(f"Publicado: {mensaje}")
    return True
