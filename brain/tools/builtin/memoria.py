from brain.modules.memoria import Memoria
from brain.tools.decorators import tool

memoria = Memoria()


@tool(
    descripcion=(
        "Guarda algo en la memoria permanente de BRAIN para recordarlo siempre "
        "(un dato sobre el usuario, una persona, una preferencia, un proyecto)."
    ),
    categoria="memoria",
    argumentos={
        "texto": "Lo que hay que recordar, redactado como una frase completa",
        "tipo": "personas, preferencias, contexto o proyectos. Por defecto contexto.",
    },
)
def recordar(texto: str, tipo: str = "contexto"):
    """Guarda un recuerdo."""

    return {"guardado": memoria.recordar(texto, tipo)}


@tool(
    descripcion="Consulta lo que BRAIN tiene guardado en su memoria permanente.",
    categoria="memoria",
    argumentos={"tipo": "personas, preferencias, contexto o proyectos. Omitir para ver todo."},
)
def consultar_memoria(tipo: str = None):
    """Consulta la memoria."""

    recuerdos = memoria.consultar(tipo)

    if not recuerdos or not any(recuerdos.values()):
        return {"mensaje": "No hay nada guardado en la memoria."}

    return recuerdos


@tool(
    descripcion="Borra de la memoria los recuerdos que contengan un texto.",
    categoria="memoria",
    argumentos={"texto": "Palabra o frase que aparece en el recuerdo a borrar"},
)
def olvidar(texto: str):
    """Borra recuerdos."""

    return memoria.olvidar(texto)
