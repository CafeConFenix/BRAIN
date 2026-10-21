"""
Lectura básica de texto de archivos PDF sin instalar nada.

Funciona con los PDF "normales" (manuales, facturas, instrucciones) que
guardan el texto comprimido con Flate. Los PDF escaneados (solo imágenes) o
con fuentes especiales pueden salir vacíos: en ese caso se avisa.
"""

import re
import zlib

_FLUJO = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
_CADENA = re.compile(rb"\((?:\\.|[^\\()])*\)|<([0-9A-Fa-f\s]+)>")
_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"", b"f": b"", b"(": b"(", b")": b")", b"\\": b"\\"}


def _descifrar(token: bytes) -> str:
    if token.startswith(b"<"):
        hexa = re.sub(rb"\s+", b"", token[1:-1])

        if len(hexa) % 2:
            hexa += b"0"

        crudo = bytes.fromhex(hexa.decode("ascii"))

        if len(crudo) >= 2 and len(crudo) % 2 == 0 and crudo[0] == 0:
            return crudo.decode("utf-16-be", errors="ignore")

        return crudo.decode("latin-1", errors="ignore")

    cuerpo = token[1:-1]
    salida = bytearray()
    i = 0

    while i < len(cuerpo):
        c = cuerpo[i : i + 1]

        if c == b"\\" and i + 1 < len(cuerpo):
            siguiente = cuerpo[i + 1 : i + 2]

            if siguiente.isdigit():
                octal = re.match(rb"[0-7]{1,3}", cuerpo[i + 1 :])
                salida.append(int(octal.group(), 8) & 255)
                i += 1 + len(octal.group())
                continue

            salida += _ESCAPES.get(siguiente, siguiente)
            i += 2
            continue

        salida += c
        i += 1

    return bytes(salida).decode("cp1252", errors="ignore")


def extraer_texto(datos: bytes, maximo: int = 2_000_000) -> str:
    if not datos.startswith(b"%PDF"):
        raise ValueError("Ese archivo no parece un PDF.")

    partes = []

    for flujo in _FLUJO.findall(datos):
        try:
            contenido = zlib.decompress(flujo)
        except zlib.error:
            contenido = flujo

        if b"BT" not in contenido:
            continue

        for bloque in re.findall(rb"BT(.*?)ET", contenido, re.S):
            linea = []

            for operador in re.finditer(rb"(\[(?:.*?)\]|\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>)\s*(TJ|Tj|'|\")|(T\*|Td|TD|Tm)", bloque, re.S):
                if operador.group(3):
                    linea.append("\n")
                    continue

                for cadena in _CADENA.finditer(operador.group(1)):
                    linea.append(_descifrar(cadena.group()))

            partes.append("".join(linea))

        if sum(len(p) for p in partes) > maximo:
            break

    texto = "\n".join(partes)
    texto = re.sub(r"[ \t]+\n", "\n", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto).strip()

    return texto[:maximo]
