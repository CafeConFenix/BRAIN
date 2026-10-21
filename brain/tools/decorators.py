import inspect

REGISTRO_HERRAMIENTAS = []

# Tipo de Python -> tipo de JSON Schema (para el "tool calling" de Ollama).
TIPOS_JSON = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
}


def _parametros(func, descripciones):
    """
    Obtiene los parámetros de una función para describirlos a la IA.

    Devuelve una lista de diccionarios con nombre, tipo, descripción y si
    es obligatorio.
    """

    parametros = []

    for nombre, parametro in inspect.signature(func).parameters.items():
        if parametro.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        anotacion = parametro.annotation

        if isinstance(anotacion, type):
            tipo = anotacion.__name__
        else:
            tipo = "str"

        if tipo not in TIPOS_JSON:
            tipo = "str"

        parametros.append(
            {
                "nombre": nombre,
                "tipo": tipo,
                "descripcion": descripciones.get(nombre, ""),
                "requerido": parametro.default is inspect.Parameter.empty,
            }
        )

    return parametros


def tool(nombre=None, descripcion="", categoria="general", argumentos=None):
    """
    Decorador para registrar automáticamente una herramienta.

    Cada herramienta queda registrada con:
    - nombre
    - descripción
    - categoría
    - parámetros (tomados de la firma de la función)
    - función original

    `argumentos` es un diccionario opcional {parámetro: explicación} que
    ayuda a la IA a rellenar cada argumento correctamente.
    """

    def decorator(func):
        nombre_final = nombre or func.__name__

        # Si el módulo se recarga, la herramienta se reemplaza.
        REGISTRO_HERRAMIENTAS[:] = [h for h in REGISTRO_HERRAMIENTAS if h["nombre"] != nombre_final]

        REGISTRO_HERRAMIENTAS.append(
            {
                "nombre": nombre_final,
                "descripcion": descripcion,
                "categoria": categoria,
                "parametros": _parametros(func, argumentos or {}),
                "funcion": func,
            }
        )

        return func

    return decorator
