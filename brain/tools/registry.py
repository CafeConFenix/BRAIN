import re

from brain.tools.decorators import REGISTRO_HERRAMIENTAS, TIPOS_JSON


NUMEROS_EN_PALABRAS = {
    "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
    "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "media": 0.5, "medio": 0.5,
}  # fmt: skip


def _numero_desde_texto(valor):
    """
    Saca el primer número de un texto como "1 unidad", "2 uds", "1,5 kg" o
    "dos". Los modelos pequeños suelen mandar la cantidad con su unidad.
    """

    texto = valor.strip().lower()

    coincidencia = re.search(r"[-+]?\d+(?:[.,]\d+)?", texto)

    if coincidencia:
        return float(coincidencia.group(0).replace(",", "."))

    for palabra in re.findall(r"[a-záéíóú]+", texto):
        if palabra in NUMEROS_EN_PALABRAS:
            return float(NUMEROS_EN_PALABRAS[palabra])

    raise ValueError(valor)


def _convertir(nombre, valor, tipo):
    """
    Convierte el valor recibido de la IA al tipo que espera la herramienta.

    Los modelos suelen enviar los números como texto ("188.5") y, al ser
    españoles, a veces con coma decimal ("188,5").
    """

    if valor is None:
        return None

    try:
        if tipo == "float":
            if isinstance(valor, str):
                return _numero_desde_texto(valor)

            return float(valor)

        if tipo == "int":
            numero = _numero_desde_texto(valor) if isinstance(valor, str) else float(valor)

            if numero != int(numero):
                raise ValueError

            return int(numero)

        if tipo == "bool":
            if isinstance(valor, str):
                return valor.strip().lower() in {
                    "true",
                    "1",
                    "si",
                    "sí",
                    "yes",
                    "verdadero",
                }

            return bool(valor)

        if tipo == "str":
            return str(valor)

    except (ValueError, TypeError, OverflowError):
        raise ValueError(f"El argumento '{nombre}' debe ser de tipo {tipo}, pero se recibió {valor!r}.") from None

    return valor


class ToolRegistry:
    """
    Registro central de herramientas de BRAIN.

    Lee siempre del registro global, así las herramientas añadidas
    después de crear el registro también aparecen.
    """

    def listar(self):
        """Devuelve todas las herramientas registradas."""
        return list(REGISTRO_HERRAMIENTAS)

    def obtener(self, nombre):
        """Obtiene una herramienta por nombre."""

        for herramienta in REGISTRO_HERRAMIENTAS:
            if herramienta["nombre"] == nombre:
                return herramienta

        return None

    def esquemas(self):
        """
        Describe las herramientas en el formato de "tool calling" de
        Ollama (JSON Schema), para que el modelo las pueda invocar.
        """

        esquemas = []

        for herramienta in REGISTRO_HERRAMIENTAS:
            propiedades = {}

            for parametro in herramienta["parametros"]:
                propiedad = {"type": TIPOS_JSON.get(parametro["tipo"], "string")}

                if parametro["descripcion"]:
                    propiedad["description"] = parametro["descripcion"]

                propiedades[parametro["nombre"]] = propiedad

            esquemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": herramienta["nombre"],
                        "description": herramienta["descripcion"],
                        "parameters": {
                            "type": "object",
                            "properties": propiedades,
                            "required": [p["nombre"] for p in herramienta["parametros"] if p["requerido"]],
                        },
                    },
                }
            )

        return esquemas

    def ejecutar(self, nombre, argumentos=None, /, **extra):
        """
        Ejecuta una herramienta registrada.

        Valida los argumentos y los convierte al tipo correcto antes
        de llamar a la función.
        """

        kwargs = {**(argumentos or {}), **extra}

        herramienta = self.obtener(nombre)

        if herramienta is None:
            raise ValueError(f"Herramienta '{nombre}' no encontrada.")

        parametros = {p["nombre"]: p for p in herramienta.get("parametros", [])}

        if not parametros:
            # Herramienta sin argumentos: se ignora lo que envíe el modelo.
            return herramienta["funcion"]()

        # Los modelos pequeños a veces inventan argumentos ("unidad", "nota"...).
        # Se ignoran en vez de fallar: lo importante es que la acción se haga.
        kwargs = {n: v for n, v in kwargs.items() if n in parametros}

        faltan = [n for n, p in parametros.items() if p["requerido"] and kwargs.get(n) in (None, "")]

        if faltan:
            raise ValueError(f"Faltan argumentos obligatorios para '{nombre}': {faltan}.")

        # Los argumentos opcionales vacíos ("" o None) se descartan para
        # que se aplique su valor por defecto.
        convertidos = {
            n: _convertir(n, valor, parametros[n]["tipo"]) for n, valor in kwargs.items() if valor not in (None, "")
        }

        return herramienta["funcion"](**convertidos)
