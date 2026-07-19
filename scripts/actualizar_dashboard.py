"""
Corrida automática horaria (LaunchAgent, 9am-7pm): reutiliza la sesión
guardada, descarga las remisiones completas (rápido, es un download
directo — no async), reprocesa ventas y publica. NO refresca inventario
ni el detalle por artículo (más pesado, se reserva para el cierre de
las 8pm en cierre_dia.py).

Si la sesión expiró y el auto-login falla (ej. captcha), se detiene sin
publicar — regla de oro de JR ARQUITECTURA_REPLICABLE.md sección 3.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.publicar_git import publicar
from common.estado_automatizacion import marcar_ok

SCRIPTS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable


def _run(script: str) -> bool:
    resultado = subprocess.run([PYTHON, str(SCRIPTS_DIR / script)], cwd=SCRIPTS_DIR)
    return resultado.returncode == 0


def main():
    pasos = [
        "descargar_remisiones_completas.py",
        "procesar_ventas.py",
        "procesar_ventas_diarias.py",
        "generar_dashboard.py",
    ]
    for paso in pasos:
        print(f"--- {paso} ---")
        if not _run(paso):
            print(f"Falló '{paso}'. Abortando sin publicar.")
            return

    marcar_ok("hora")
    hora = datetime.now().strftime("%Y-%m-%d %H:%M")
    publicar(f"Actualización automática {hora}")


if __name__ == "__main__":
    main()
