"""
Marca de "última corrida exitosa" por tipo de job (hora/cierre).

Existe porque StartCalendarInterval de launchd solo dispara si el Mac está
despierto (y con internet) en el minuto exacto programado -- si estaba
dormido o la wifi no había reconectado todavía, esa corrida se pierde sin
avisar y sin reintentar. verificar_automatizacion.py corre cada pocos
minutos y usa estas marcas para saber si ya se cubrió la hora/el cierre de
hoy o si hay que ponerse al día.
"""

import socket
from datetime import datetime
from pathlib import Path

REPORTES_DIR = Path(__file__).resolve().parent.parent.parent / "reportes"


def marcar_ok(nombre: str) -> None:
    REPORTES_DIR.mkdir(exist_ok=True)
    (REPORTES_DIR / f".ultima_{nombre}_ok").write_text(datetime.now().isoformat())


def ultima_ok(nombre: str) -> datetime | None:
    ruta = REPORTES_DIR / f".ultima_{nombre}_ok"
    if not ruta.exists():
        return None
    try:
        return datetime.fromisoformat(ruta.read_text().strip())
    except ValueError:
        return None


def hay_internet(host: str = "effi.com.co", puerto: int = 443, timeout: float = 5.0) -> bool:
    """Chequeo rápido de conectividad antes de lanzar un scrape pesado.

    Sin esto, si el Mac acaba de despertar y el wifi todavía está
    reconectando, el intento se cuelga hasta el timeout de descarga (900s)
    en vez de fallar rápido -- eso bloquea el ciclo del vigía por 15
    minutos en lugar de reintentar limpio en el siguiente tick (10 min)."""
    try:
        with socket.create_connection((host, puerto), timeout=timeout):
            return True
    except OSError:
        return False
