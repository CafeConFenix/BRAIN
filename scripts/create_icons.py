"""
Draws the BRAIN logo and generates all the icons (web PNGs and Windows brain.ico).

Usage:  python scripts/create_icons.py
Needs Pillow only for this (BRAIN does not need it to run).
"""

import struct
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "brain" / "web" / "static" / "iconos"
DESKTOP = ROOT / "brain" / "desktop"

LARGE = 2048  # drawn large and shrunk down: smooths the edges


def _degraded(size, up, down):
    base = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        base.putpixel((0, y), tuple(round(a + (b - a) * t) for a, b in zip(up, down)))
    return base.resize((size, size))


def _rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return m


def draw(size=LARGE):
    k = size / 1000.0

    def c(x):
        return round(x * k)

    # Background: very dark violet with a gradient and a soft glow at the top left.
    background = _degraded(size, (74, 24, 140), (22, 6, 48)).convert("RGBA")
    brightness = Image.new("L", (size, size), 0)
    ImageDraw.Draw(brightness).ellipse((c(-200), c(-250), c(700), c(500)), fill=70)
    brightness = brightness.filter(ImageFilter.GaussianBlur(c(120)))
    background.paste(Image.new("RGBA", (size, size), (196, 160, 255, 255)), (0, 0), brightness)

    # Brain: two hemispheres (unions of circles) with a notch in the middle.
    lobes = [(375, 395, 168), (300, 548, 142), (412, 640, 138), (470, 470, 150), (330, 420, 150)]
    hemisphere = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(hemisphere)
    for x, y, r in lobes:
        d.ellipse((c(x - r), c(y - r), c(x + r), c(y + r)), fill=255)
    half = hemisphere.crop((0, 0, c(488), size))
    left = Image.new("L", (size, size), 0)
    left.paste(half, (0, 0))
    right = ImageChops.offset(left.transpose(Image.FLIP_LEFT_RIGHT), 0, 0)
    brain = ImageChops.lighter(left, right)

    # Brain stem
    ImageDraw.Draw(brain).rounded_rectangle((c(462), c(700), c(538), c(808)), radius=c(36), fill=255)

    padding = _degraded(size, (233, 213, 255), (167, 139, 250)).convert("RGBA")
    shadow = brain.filter(ImageFilter.GaussianBlur(c(26)))
    shadow_layer = Image.new("RGBA", (size, size), (10, 0, 30, 255))
    background.paste(shadow_layer, (c(0), c(22)), shadow.point(lambda v: v * 0.55))
    background.paste(padding, (0, 0), brain)

    # Neural network inside: nodes and connections in dark violet.
    nodes_i = [(300, 390), (390, 520), (270, 560), (420, 640), (440, 380)]
    connections = [(0, 1), (1, 2), (1, 3), (0, 4), (4, 1), (2, 3)]
    stroke = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    t = ImageDraw.Draw(stroke)
    dark = (59, 16, 120, 255)

    def mirror(p):
        return (1000 - p[0], p[1])

    for a, b in connections:
        for f in (lambda p: p, mirror):
            pa, pb = f(nodes_i[a]), f(nodes_i[b])
            t.line((c(pa[0]), c(pa[1]), c(pb[0]), c(pb[1])), fill=dark, width=c(15))
    # bridges between hemispheres
    for y in (390, 520, 640):
        t.line((c(nodes_i[0][0] if y == 390 else nodes_i[1][0] if y == 520 else nodes_i[3][0]), c(y), c(1000 - (nodes_i[0][0] if y == 390 else nodes_i[1][0] if y == 520 else nodes_i[3][0])), c(y)), fill=dark, width=c(15))
    for p in nodes_i:
        for q in (p, mirror(p)):
            t.ellipse((c(q[0] - 24), c(q[1] - 24), c(q[0] + 24), c(q[1] + 24)), fill=dark)
    background.alpha_composite(stroke)

    # Spark: a bright pink-lilac node in the center.
    glow = Image.new("L", (size, size), 0)
    ImageDraw.Draw(glow).ellipse((c(500 - 120), c(455 - 120), c(500 + 120), c(455 + 120)), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(c(46)))
    background.paste(Image.new("RGBA", (size, size), (245, 160, 255, 255)), (0, 0), glow.point(lambda v: v * 0.9))
    spark = ImageDraw.Draw(background)
    spark.ellipse((c(500 - 40), c(455 - 40), c(500 + 40), c(455 + 40)), fill=(255, 245, 255, 255))

    # Rounded corners
    shape = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shape.paste(background, (0, 0), _rounded_mask(size, c(225)))

    return shape


def _frame_bmp(img):
    """Image -> ICO frame in 32-bit BMP format (the most compatible with System.Drawing.Icon)."""

    width, height = img.size
    pixels = img.convert("RGBA").load()
    rows = bytearray()

    for y in range(height - 1, -1, -1):  # BMP goes bottom to top
        for x in range(width):
            r, g, b, a = pixels[x, y]
            rows += bytes((b, g, r, a))

    mask = bytearray(((width + 31) // 32) * 4 * height)  # empty AND mask: transparency lives in the alpha channel
    header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0, len(rows) + len(mask), 0, 0, 0, 0)

    return header + bytes(rows) + bytes(mask)


def save_ico(logo, destination, sizes=(16, 24, 32, 48, 64, 128, 256)):
    frames = [_frame_bmp(logo.resize((s, s), Image.LANCZOS)) for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(frames))
    position = 6 + 16 * len(frames)
    inputs = b""

    for s, data in zip(sizes, frames):
        inputs += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), position)
        position += len(data)

    Path(destination).write_bytes(header + inputs + b"".join(frames))


def main():
    logo = draw()
    STATIC.mkdir(parents=True, exist_ok=True)

    for name, side in (("icono-512.png", 512), ("icono-192.png", 192), ("apple-touch-icon.png", 180)):
        logo.resize((side, side), Image.LANCZOS).save(STATIC / name, optimize=True)

    logo.resize((1024, 1024), Image.LANCZOS).save(ROOT / "docs" / "img" / "logo.png", optimize=True)
    save_ico(logo, STATIC / "brain.ico")
    save_ico(logo, DESKTOP / "brain.ico")
    print("Icons generated.")


if __name__ == "__main__":
    main()
