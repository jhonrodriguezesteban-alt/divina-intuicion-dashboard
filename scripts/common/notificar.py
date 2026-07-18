"""Notificación nativa de macOS (Centro de Notificaciones) al terminar un cierre."""

import subprocess


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace('"', '\\"')


def notificar_mac(titulo: str, mensaje: str):
    script = f'display notification "{_escapar(mensaje)}" with title "{_escapar(titulo)}" sound name "Glass"'
    subprocess.run(["osascript", "-e", script])
