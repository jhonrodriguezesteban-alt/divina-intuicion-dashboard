"""
Cierre total del día (LaunchAgent, 8pm): refresca TODO — ventas, inventario,
detalle por artículo y reporte mensual por sucursal —, regenera el
dashboard, genera el resumen del día y publica. Al terminar, notifica por
el Centro de Notificaciones de macOS.

Es la corrida más pesada del día (inventario + conceptos pueden tardar
varios minutos); las corridas horarias (actualizar_dashboard.py) solo
refrescan ventas para no cargar Effi innecesariamente. Por eso el aviso de
reposición de martes/viernes también va aquí (necesita reorden.json recién
calculado) y no en la corrida horaria.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common.notificar import notificar_mac
from common.publicar_git import publicar
from common.estado_automatizacion import marcar_ok
from generar_resumen_dia import generar_texto as generar_resumen_texto

SCRIPTS_DIR = Path(__file__).resolve().parent
REPORTES_DIR = SCRIPTS_DIR.parent / "reportes"
PYTHON = sys.executable

DIAS_PEDIDO = (1, 4)  # martes, viernes (Python: lunes=0)


def _run(script: str) -> bool:
    resultado = subprocess.run([PYTHON, str(SCRIPTS_DIR / script)], cwd=SCRIPTS_DIR)
    return resultado.returncode == 0


def _resumen_reposicion() -> str:
    ruta = REPORTES_DIR / "reorden.json"
    if not ruta.exists():
        return "reorden.json no encontrado."
    reorden = json.loads(ruta.read_text(encoding="utf-8"))
    ropa = reorden["ropa"]["resumen"]
    acc = reorden["accesorios"]["resumen"]
    return (
        f"Ropa: {ropa['criticos']} críticas, {ropa['alerta']} en alerta, "
        f"{ropa['unidades_sugeridas_total']} und. sugeridas. · "
        f"Accesorios: {acc['criticos']} categorías críticas, {acc['alerta']} en alerta, "
        f"{acc['unidades_sugeridas_total']} und. sugeridas."
    )


def main():
    pasos = [
        "descargar_remisiones_completas.py",
        "descargar_facturas_completas.py",
        "procesar_ventas.py",
        "procesar_ventas_diarias.py",
        "descargar_articulos.py",
        "procesar_inventario.py",
        "descargar_conceptos.py",
        "descargar_conceptos_facturas.py",
        "procesar_categorias_referencias.py",
        "procesar_liquidacion.py",
        "descargar_mensual_por_sucursal.py",
        "procesar_historico_mensual.py",
        "procesar_reorden.py",
        "procesar_planeacion_temporada.py",
        "generar_resumen_dia.py",
        "generar_dashboard.py",
    ]
    # Pasos cuya falla NO debe tumbar el cierre completo: si el catálogo de
    # artículos no baja, los procesadores siguen con el último archivo bueno
    # -- abortar ahí congelaba también ventas e histórico (pasó 10 días
    # seguidos en sep-2026). Se avisa igual para que no quede en silencio.
    no_bloqueantes = {"descargar_articulos.py", "procesar_planeacion_temporada.py"}
    advertencias = []

    for paso in pasos:
        print(f"--- {paso} ---")
        if not _run(paso):
            if paso in no_bloqueantes:
                print(f"Falló '{paso}' (no bloqueante) -- se sigue con el último archivo disponible.")
                advertencias.append(paso)
                continue
            print(f"Falló '{paso}'. Abortando sin publicar el cierre.")
            notificar_mac("Divina Intuición — Cierre falló", f"'{paso}' falló. Revisar manualmente.")
            return

    if advertencias:
        notificar_mac(
            "Divina Intuición — Cierre con advertencias",
            f"Falló: {', '.join(advertencias)}. Se publicó con los últimos datos disponibles de ese paso.",
        )

    marcar_ok("cierre")
    hora = datetime.now().strftime("%Y-%m-%d %H:%M")
    publicado = publicar(f"Cierre del día {hora}")

    resumen = generar_resumen_texto()
    primera_linea_venta = next((l for l in resumen.splitlines() if l.startswith("Venta de hoy")), "")
    if publicado:
        notificar_mac("Divina Intuición — Cierre completado", primera_linea_venta or "Cierre del día publicado.")
    else:
        notificar_mac("Divina Intuición — Cierre sin cambios", "El cierre corrió pero no hubo cambios que publicar.")

    if datetime.now().weekday() in DIAS_PEDIDO:
        notificar_mac("Divina Intuición — Qué surtir (martes/viernes) 📦", _resumen_reposicion())


if __name__ == "__main__":
    main()
