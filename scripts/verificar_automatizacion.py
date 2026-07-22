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

from common.estado_automatizacion import ultima_ok, hay_internet

SCRIPTS_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable

HORA_INICIO = 8
HORA_FIN = 19  # última corrida horaria programada
HORA_CIERRE = 20  # a partir de aquí, se busca hacer el cierre si no ha corrido
VENTANA_HORA_MIN = 50  # si el último "hora" OK fue hace menos de esto, no repetir


def _ejecutar(script: str):
    print(f"[{datetime.now():%H:%M:%S}] Disparando {script}...")
    subprocess.run([PYTHON, str(SCRIPTS_DIR / script)], cwd=SCRIPTS_DIR)


def main():
    ahora = datetime.now()
    hace_falta_hora = HORA_INICIO <= ahora.hour <= HORA_FIN and (
        not (u := ultima_ok("hora")) or (ahora - u) > timedelta(minutes=VENTANA_HORA_MIN)
    )
    # "c.hour < HORA_CIERRE" cubre el caso de correr cierre_dia.py a mano en la
    # mañana para ponerse al día por una falla de días anteriores: eso marca
    # "cierre" con la fecha de HOY pero a una hora temprana, que no es el
    # cierre real de hoy -- sin este chequeo, el cierre real de las 8pm (con
    # las cifras finales del día y el aviso de martes/viernes) se saltaría.
    hace_falta_cierre = ahora.hour >= HORA_CIERRE and (
        not (c := ultima_ok("cierre")) or c.date() != ahora.date() or c.hour < HORA_CIERRE
    )

    if (hace_falta_hora or hace_falta_cierre) and not hay_internet():
        # Sin esto, un intento justo al despertar el Mac (wifi reconectando)
        # se cuelga hasta el timeout de descarga (900s) en vez de fallar
        # rápido -- eso bloqueaba el ciclo entero por 15 min en vez de
        # reintentar limpio en el siguiente tick (10 min).
        print(f"[{ahora:%H:%M:%S}] Sin internet todavía, se reintenta en el próximo ciclo.")
        return

    if HORA_INICIO <= ahora.hour <= HORA_FIN:
        if hace_falta_hora:
            _ejecutar("actualizar_dashboard.py")
        else:
            ultima = ultima_ok("hora")
            print(f"[{ahora:%H:%M:%S}] Reporte horario al día (última corrida OK: {ultima:%H:%M}).")

    if ahora.hour >= HORA_CIERRE:
        if hace_falta_cierre:
            _ejecutar("cierre_dia.py")
        else:
            ultimo_cierre = ultima_ok("cierre")
            print(f"[{ahora:%H:%M:%S}] Cierre del día ya hecho ({ultimo_cierre:%H:%M}).")


if __name__ == "__main__":
    main()
