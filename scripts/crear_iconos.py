"""
Dibuja el logo de BRAIN y genera todos los iconos (PNG de la web y brain.ico de Windows).

Uso:  python scripts/crear_iconos.py
Necesita Pillow solo para esto (BRAIN no lo necesita para funcionar).
"""

import struct
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parents[1]
ESTATICOS = RAIZ / "brain" / "web" / "static" / "iconos"
ESCRITORIO = RAIZ / "brain" / "escritorio"

GRANDE = 2048  # se dibuja grande y se reduce: bordes suaves


def _degradado(tam, arriba, abajo):
    base = Image.new("RGB", (1, tam))
    for y in range(tam):
        t = y / (tam - 1)
        base.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(arriba, abajo)))
    return base.resize((tam, tam))


def _mascara_redondeada(tam, radio):
    m = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, tam - 1, tam - 1), radius=radio, fill=255)
    return m


def dibujar(tam=GRANDE):
    k = tam / 1000.0

    def c(x):
        return round(x * k)

    # Fondo: violeta muy oscuro con degradado y un brillo suave arriba a la izquierda.
    fondo = _degradado(tam, (74, 24, 140), (22, 6, 48)).convert("RGBA")
    brillo = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(brillo).ellipse((c(-200), c(-250), c(700), c(500)), fill=70)
    brillo = brillo.filter(ImageFilter.GaussianBlur(c(120)))
    fondo.paste(Image.new("RGBA", (tam, tam), (196, 160, 255, 255)), (0, 0), brillo)

    # Cerebro: dos hemisferios (uniones de círculos) con una hendidura en el centro.
    lobulos = [(375, 395, 168), (300, 548, 142), (412, 640, 138), (470, 470, 150), (330, 420, 150)]
    hemisferio = Image.new("L", (tam, tam), 0)
    d = ImageDraw.Draw(hemisferio)
    for x, y, r in lobulos:
        d.ellipse((c(x - r), c(y - r), c(x + r), c(y + r)), fill=255)
    mitad = hemisferio.crop((0, 0, c(488), tam))
    izquierdo = Image.new("L", (tam, tam), 0)
    izquierdo.paste(mitad, (0, 0))
    derecho = ImageChops.offset(izquierdo.transpose(Image.FLIP_LEFT_RIGHT), 0, 0)
    cerebro = ImageChops.lighter(izquierdo, derecho)

    # Tronco del cerebro
    ImageDraw.Draw(cerebro).rounded_rectangle((c(462), c(700), c(538), c(808)), radius=c(36), fill=255)

    relleno = _degradado(tam, (233, 213, 255), (167, 139, 250)).convert("RGBA")
    sombra = cerebro.filter(ImageFilter.GaussianBlur(c(26)))
    capa_sombra = Image.new("RGBA", (tam, tam), (10, 0, 30, 255))
    fondo.paste(capa_sombra, (c(0), c(22)), sombra.point(lambda v: v * 0.55))
    fondo.paste(relleno, (0, 0), cerebro)

    # Red neuronal dentro: nodos y conexiones en violeta oscuro.
    nodos_i = [(300, 390), (390, 520), (270, 560), (420, 640), (440, 380)]
    conexiones = [(0, 1), (1, 2), (1, 3), (0, 4), (4, 1), (2, 3)]
    trazo = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    t = ImageDraw.Draw(trazo)
    oscuro = (59, 16, 120, 255)

    def espejo(p):
        return (1000 - p[0], p[1])

    for a, b in conexiones:
        for f in (lambda p: p, espejo):
            pa, pb = f(nodos_i[a]), f(nodos_i[b])
            t.line((c(pa[0]), c(pa[1]), c(pb[0]), c(pb[1])), fill=oscuro, width=c(15))
    # puentes entre hemisferios
    for y in (390, 520, 640):
        t.line((c(nodos_i[0][0] if y == 390 else nodos_i[1][0] if y == 520 else nodos_i[3][0]), c(y), c(1000 - (nodos_i[0][0] if y == 390 else nodos_i[1][0] if y == 520 else nodos_i[3][0])), c(y)), fill=oscuro, width=c(15))
    for p in nodos_i:
        for q in (p, espejo(p)):
            t.ellipse((c(q[0] - 24), c(q[1] - 24), c(q[0] + 24), c(q[1] + 24)), fill=oscuro)
    fondo.alpha_composite(trazo)

    # Chispa: un nodo brillante rosa-lila en el centro.
    resplandor = Image.new("L", (tam, tam), 0)
    ImageDraw.Draw(resplandor).ellipse((c(500 - 120), c(455 - 120), c(500 + 120), c(455 + 120)), fill=255)
    resplandor = resplandor.filter(ImageFilter.GaussianBlur(c(46)))
    fondo.paste(Image.new("RGBA", (tam, tam), (245, 160, 255, 255)), (0, 0), resplandor.point(lambda v: v * 0.9))
    chispa = ImageDraw.Draw(fondo)
    chispa.ellipse((c(500 - 40), c(455 - 40), c(500 + 40), c(455 + 40)), fill=(255, 245, 255, 255))

    # Esquinas redondeadas
    forma = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    forma.paste(fondo, (0, 0), _mascara_redondeada(tam, c(225)))

    return forma


def _frame_bmp(img):
    """Imagen -> fotograma de ICO en formato BMP de 32 bits (el más compatible con System.Drawing.Icon)."""

    ancho, alto = img.size
    pixeles = img.convert("RGBA").load()
    filas = bytearray()

    for y in range(alto - 1, -1, -1):  # BMP va de abajo arriba
        for x in range(ancho):
            r, g, b, a = pixeles[x, y]
            filas += bytes((b, g, r, a))

    mascara = bytearray(((ancho + 31) // 32) * 4 * alto)  # máscara AND vacía: la transparencia va en el alfa
    cabecera = struct.pack("<IiiHHIIiiII", 40, ancho, alto * 2, 1, 32, 0, len(filas) + len(mascara), 0, 0, 0, 0)

    return cabecera + bytes(filas) + bytes(mascara)


def guardar_ico(logo, destino, tamanos=(16, 24, 32, 48, 64, 128, 256)):
    frames = [_frame_bmp(logo.resize((s, s), Image.LANCZOS)) for s in tamanos]
    cabecera = struct.pack("<HHH", 0, 1, len(frames))
    posicion = 6 + 16 * len(frames)
    entradas = b""

    for s, datos in zip(tamanos, frames):
        entradas += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(datos), posicion)
        posicion += len(datos)

    Path(destino).write_bytes(cabecera + entradas + b"".join(frames))


def main():
    logo = dibujar()
    ESTATICOS.mkdir(parents=True, exist_ok=True)

    for nombre, lado in (("icono-512.png", 512), ("icono-192.png", 192), ("apple-touch-icon.png", 180)):
        fondo_plano = logo if nombre != "apple-touch-icon.png" else logo
        fondo_plano.resize((lado, lado), Image.LANCZOS).save(ESTATICOS / nombre, optimize=True)

    logo.resize((1024, 1024), Image.LANCZOS).save(RAIZ / "docs" / "img" / "logo.png", optimize=True)
    guardar_ico(logo, ESTATICOS / "brain.ico")
    guardar_ico(logo, ESCRITORIO / "brain.ico")
    print("Iconos generados.")


if __name__ == "__main__":
    main()
