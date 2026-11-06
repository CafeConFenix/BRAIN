"""
Basic text reading of PDF files with nothing to install.

Works with "normal" PDFs (manuals, invoices, instructions) that store
their text Flate-compressed. Scanned PDFs (images only) or ones with
special fonts may come out empty: that case raises an error.
"""

import re
import zlib

from brain.i18n import t

_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
_STRING = re.compile(rb"\((?:\\.|[^\\()])*\)|<([0-9A-Fa-f\s]+)>")
_ESCAPES = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"", b"f": b"", b"(": b"(", b")": b")", b"\\": b"\\"}


def _decode(token: bytes) -> str:
    if token.startswith(b"<"):
        hex_text = re.sub(rb"\s+", b"", token[1:-1])

        if len(hex_text) % 2:
            hex_text += b"0"

        raw = bytes.fromhex(hex_text.decode("ascii"))

        if len(raw) >= 2 and len(raw) % 2 == 0 and raw[0] == 0:
            return raw.decode("utf-16-be", errors="ignore")

        return raw.decode("latin-1", errors="ignore")

    body = token[1:-1]
    output = bytearray()
    i = 0

    while i < len(body):
        c = body[i : i + 1]

        if c == b"\\" and i + 1 < len(body):
            next_due = body[i + 1 : i + 2]

            if next_due.isdigit():
                octal = re.match(rb"[0-7]{1,3}", body[i + 1 :])
                output.append(int(octal.group(), 8) & 255)
                i += 1 + len(octal.group())
                continue

            output += _ESCAPES.get(next_due, next_due)
            i += 2
            continue

        output += c
        i += 1

    return bytes(output).decode("cp1252", errors="ignore")


def extract_text(data: bytes, maximum: int = 2_000_000) -> str:
    if not data.startswith(b"%PDF"):
        raise ValueError(t("That file does not look like a PDF."))

    parts = []

    for stream in _STREAM.findall(data):
        try:
            content = zlib.decompress(stream)
        except zlib.error:
            content = stream

        if b"BT" not in content:
            continue

        for block in re.findall(rb"BT(.*?)ET", content, re.S):
            line = []

            for operator in re.finditer(rb"(\[(?:.*?)\]|\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>)\s*(TJ|Tj|'|\")|(T\*|Td|TD|Tm)", block, re.S):
                if operator.group(3):
                    line.append("\n")
                    continue

                for string in _STRING.finditer(operator.group(1)):
                    line.append(_decode(string.group()))

            parts.append("".join(line))

        if sum(len(p) for p in parts) > maximum:
            break

    text = "\n".join(parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    return text[:maximum]
