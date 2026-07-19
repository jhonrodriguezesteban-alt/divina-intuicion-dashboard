"""
Genera assets/icono_app.png: el logo de Divina Intuición centrado sobre un
fondo sólido color crema de marca (mismo --bg del dashboard), cuadrado.

Uso: como apple-touch-icon / favicon del dashboard, para que "Agregar a
pantalla de inicio" en el celular muestre el logo real en vez del ícono
genérico o una captura de pantalla recortada. Preparación de asset única
(no forma parte del pipeline de actualización diaria) -- se re-ejecuta a
mano solo si cambia el logo.
"""

from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LOGO = ASSETS / "logo_divina.png"
OUT = ASSETS / "icono_app.png"

TAMANO = 512
FONDO = (244, 241, 236, 255)  # --bg de la paleta del dashboard


def main():
    logo = Image.open(LOGO).convert("RGBA")
    lienzo = Image.new("RGBA", (TAMANO, TAMANO), FONDO)

    ancho_objetivo = int(TAMANO * 0.74)
    ratio = ancho_objetivo / logo.width
    alto_objetivo = int(logo.height * ratio)
    logo_r = logo.resize((ancho_objetivo, alto_objetivo), Image.LANCZOS)

    x = (TAMANO - ancho_objetivo) // 2
    y = (TAMANO - alto_objetivo) // 2
    lienzo.alpha_composite(logo_r, (x, y))

    lienzo.convert("RGB").save(OUT, "PNG")
    print(f"Guardado en {OUT} ({TAMANO}x{TAMANO})")


if __name__ == "__main__":
    main()
