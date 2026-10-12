from datetime import date, datetime

DIAS = (
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo",
)

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def hoy():
    """Fecha de hoy en formato AAAA-MM-DD."""

    return date.today().isoformat()


def ahora_texto():
    """Fecha y hora actuales en lenguaje natural, para la IA."""

    ahora = datetime.now()

    return f"{DIAS[ahora.weekday()]} {ahora.date().isoformat()}, " f"{ahora.strftime('%H:%M')}"


def validar_fecha(valor, defecto_hoy=True):
    """
    Devuelve una fecha AAAA-MM-DD válida.

    Acepta también DD/MM/AAAA, DD-MM-AAAA y expresiones como "hoy",
    "ayer" y "mañana". Si no se indica fecha se usa la de hoy.
    """

    if valor in (None, ""):
        if defecto_hoy:
            return hoy()

        return None

    texto = str(valor).strip().lower()

    if texto in {"hoy", "today"}:
        return hoy()

    if texto in {"ayer", "yesterday"}:
        return date.fromordinal(date.today().toordinal() - 1).isoformat()

    if texto in {"mañana", "manana", "tomorrow"}:
        return date.fromordinal(date.today().toordinal() + 1).isoformat()

    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue

    partes = texto.replace(" de ", " ").split()

    if len(partes) in (2, 3) and partes[0].isdigit() and partes[1] in MESES:
        anio = int(partes[2]) if len(partes) == 3 and partes[2].isdigit() else date.today().year

        try:
            return date(anio, MESES[partes[1]], int(partes[0])).isoformat()
        except ValueError:
            pass

    raise ValueError(f"La fecha '{valor}' no es válida. Usa el formato AAAA-MM-DD, por ejemplo 2026-08-10.")
