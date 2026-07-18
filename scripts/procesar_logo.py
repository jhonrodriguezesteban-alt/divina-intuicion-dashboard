"""
Extrae el logo "DIVINA INTUICIÓN" del archivo original (letras negras sobre
fondo de mármol) -> PNG con fondo transparente, recortado al contenido.
Se usa una sola vez (o cuando cambie el logo), no es parte del pipeline
diario de datos.
"""

from pathlib import Path

from PIL import Image

ORIGEN = Path(__file__).resolve().parent.parent / "LOGO DIVINA INTUICION PNG.jpg.jpeg"
DESTINO = Path(__file__).resolve().parent.parent / "assets" / "logo_divina.png"

UMBRAL_CLARO = 200  # luminancia >= esto -> totalmente transparente (fondo de mármol)
UMBRAL_OSCURO = 120  # luminancia <= esto -> totalmente opaco (letra negra)


def main():
    img = Image.open(ORIGEN).convert("RGBA")
    pixeles = img.load()
    ancho, alto = img.size

    for y in range(alto):
        for x in range(ancho):
            r, g, b, _ = pixeles[x, y]
            luminancia = 0.299 * r + 0.587 * g + 0.114 * b
            if luminancia >= UMBRAL_CLARO:
                alpha = 0
            elif luminancia <= UMBRAL_OSCURO:
                alpha = 255
            else:
                alpha = int(255 * (UMBRAL_CLARO - luminancia) / (UMBRAL_CLARO - UMBRAL_OSCURO))
            pixeles[x, y] = (20, 18, 15, alpha)  # negro cálido, tono --acento del dashboard

    caja = img.getbbox()
    if caja:
        img = img.crop(caja)

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    img.save(DESTINO)
    print(f"Logo recortado guardado en {DESTINO} — tamaño final {img.size}")


if __name__ == "__main__":
    main()
