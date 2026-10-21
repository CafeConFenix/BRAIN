from brain.modules.documentos import DocumentoError, Documentos
from brain.tools.decorators import tool

documentos = Documentos()


@tool(
    descripcion=(
        "Busca en las notas, manuales y documentos guardados del usuario (archivos .txt, .md y .json) y devuelve "
        "los fragmentos más relevantes. Úsala cuando la pregunta pueda estar respondida en sus notas o manuales "
        "('¿cómo se programa la lavadora?', '¿qué apunté sobre la caldera?'). Responde solo con lo que encuentres "
        "y di de qué documento sale."
    ),
    categoria="documentos",
    argumentos={
        "consulta": "Palabras clave de lo que se busca",
        "limite": "Cuántos fragmentos devolver. Por defecto 5.",
    },
)
def buscar_en_documentos(consulta: str, limite: int = 5):
    """Busca en los documentos guardados."""

    try:
        resultados = documentos.buscar(consulta, limite)
    except DocumentoError as error:
        return {"error": str(error)}

    if not resultados:
        disponibles = documentos.listar()

        if not disponibles:
            return {"mensaje": f"No hay documentos. Guarda archivos .txt, .md o .json en {documentos.carpeta}."}

        return {"mensaje": f"No he encontrado nada sobre '{consulta}'.", "documentos": [d["nombre"] for d in disponibles]}

    return {"resultados": resultados}


@tool(
    descripcion=(
        "Lee un documento guardado entero (por páginas) o lista los documentos disponibles si no se indica nombre. "
        "Úsala tras buscar_en_documentos cuando haga falta ver más contexto."
    ),
    categoria="documentos",
    argumentos={
        "nombre": "Nombre del documento, por ejemplo 'manual_lavadora.md'. Omitir para ver la lista.",
        "desde": "Carácter por el que empezar (para leer la siguiente página). Por defecto 0.",
    },
)
def leer_documento(nombre: str = None, desde: int = 0):
    """Lee un documento o lista los disponibles."""

    if not nombre:
        lista = documentos.listar()

        if not lista:
            return {"mensaje": f"No hay documentos. Guarda archivos .txt, .md o .json en {documentos.carpeta}."}

        return {"documentos": lista}

    try:
        return documentos.leer(nombre, desde)
    except DocumentoError as error:
        return {"error": str(error)}
