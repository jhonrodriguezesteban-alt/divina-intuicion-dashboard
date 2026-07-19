"""
Reemplaza el disparo por StartCalendarInterval (que solo corre si el Mac está
despierto en el minuto exacto) por un vigía que corre cada pocos minutos vía
StartInterval y se pone al día si hace falta.

Por qué: si el computador está dormido o sin internet justo a la hora en
punto, esa corrida se pierde para siempre y nadie se entera. Este script
en cambio pregunta "¿ya se cubrió esta hora / el cierre de hoy?" cada vez
que corre -- apenas el Mac despierta y hay internet, el siguiente tick lo
detecta y dispara la actualización, sin publicar duplicado si ya estaba al
día (ver common/estado_automatizacion.py).
"""

import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.estado_automatizacion import ultima_ok

SCRIPTS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable

HORA_INICIO = 9
HORA_FIN = 19  # última corrida horaria programada
HORA_CIERRE = 20  # a partir de aquí, se busca hacer el cierre si no ha corrido
VENTANA_HORA_MIN = 50  # si el último "hora" OK fue hace menos de esto, no repetir


def _ejecutar(script: str):
    print(f"[{datetime.now():%H:%M:%S}] Disparando {script}...")
    subprocess.run([PYTHON, str(SCRIPTS_DIR / script)], cwd=SCRIPTS_DIR)


def main():
    ahora = datetime.now()

    if HORA_INICIO <= ahora.hour <= HORA_FIN:
        ultima = ultima_ok("hora")
        if not ultima or (ahora - ultima) > timedelta(minutes=VENTANA_HORA_MIN):
            _ejecutar("actualizar_dashboard.py")
        else:
            print(f"[{ahora:%H:%M:%S}] Reporte horario al día (última corrida OK: {ultima:%H:%M}).")

    if ahora.hour >= HORA_CIERRE:
        ultimo_cierre = ultima_ok("cierre")
        if not ultimo_cierre or ultimo_cierre.date() != ahora.date():
            _ejecutar("cierre_dia.py")
        else:
            print(f"[{ahora:%H:%M:%S}] Cierre del día ya hecho ({ultimo_cierre:%H:%M}).")


if __name__ == "__main__":
    main()
