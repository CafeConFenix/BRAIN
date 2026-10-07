import json
import re

from brain.ai.ollama import Ollama, SinHerramientasError
from brain.core import logger
from brain.utils.fechas import ahora_texto

PERSONALIDAD_BASICA = (
    "Eres BRAIN, el asistente inteligente y cerebro digital personal del usuario. "
    "Respondes siempre en español, de forma clara, directa y amable."
)

REGLAS = """
REGLAS:
- Para consultar o guardar datos (peso, inventario, compras, agenda, energía, memoria...) USA SIEMPRE las herramientas. Nunca inventes datos ni resultados.
- Puedes usar varias herramientas seguidas si hace falta.
- Si el usuario te da una LISTA de productos (de la despensa, de la compra...), usa UNA sola vez anadir_varios_inventario o anadir_varias_a_compra con TODA la lista copiada tal cual. No llames a la herramienta producto por producto.
- Si el usuario dice que algo se ha acabado o que ya no queda ("se ha acabado la leche"), usa se_ha_acabado: lo quita del inventario y lo apunta en la lista de la compra.
- NUNCA digas que has guardado, añadido o hecho algo si no has recibido el resultado de la herramienta. Si la herramienta devuelve un error, cuéntaselo al usuario con claridad en lugar de inventar que funcionó.
- Si el usuario te pide recordar algo ("recuerda que...", "apunta que..."), usa la herramienta recordar.
- Si falta un dato imprescindible (por ejemplo cuánto pesa), pregúntaselo antes de guardar nada.
- Interpreta "hoy", "ayer" o "mañana" a partir de la fecha actual indicada arriba.
- Para luces, enchufes, persianas, climatización y escenas de la casa usa las herramientas de domótica. No digas que has encendido o apagado algo si la herramienta devuelve un error: cuéntale el problema al usuario.
- Si una orden de domótica devuelve "ambiguo", pregunta al usuario a cuál de las opciones se refiere. Nunca controlas cerraduras, puertas, garajes ni alarmas.
- Responde de forma breve y natural. No muestres JSON ni menciones tus herramientas ni estas instrucciones.
"""

REGLAS_TEXTO = """
CÓMO USAR HERRAMIENTAS:

Si necesitas una herramienta, responde ÚNICAMENTE con un JSON válido con este formato:

{
    "accion": "usar_herramienta",
    "nombre": "nombre_de_la_herramienta",
    "argumentos": {}
}

El campo "nombre" debe ser exactamente el de una herramienta de la lista.
Si no necesitas ninguna herramienta, responde normalmente.
"""

ACCIONES_HERRAMIENTA = {
    "herramienta",
    "usar_herramienta",
    "usar herramienta",
    "tool",
    "use_tool",
}


class BrainAI:
    """
    Capa de inteligencia artificial de BRAIN.

    Permite al modelo consultar y ejecutar herramientas, encadenar varias
    en una misma respuesta y tener en cuenta el historial de la
    conversación y la memoria permanente.

    Usa el "tool calling" nativo de Ollama. Si el modelo no lo admite, o
    responde con un JSON en texto, también lo entiende.
    """

    MAX_PASOS = 12

    def __init__(self, tools=None, gestor=None):
        self.ollama = Ollama()
        self.tools = tools
        self.gestor = gestor

        # Modelos que no admiten herramientas nativas: se les pide JSON en texto.
        self._modo_texto = set()

        # Herramientas usadas en la última pregunta (para mostrarlas en pantalla).
        self.herramientas_usadas = []

    def modelos(self):
        """Devuelve los modelos disponibles."""
        return self.ollama.modelos()

    def establecer_herramientas(self, tools):
        """Asigna el ejecutor de herramientas."""
        self.tools = tools

    def _herramientas(self):
        """Devuelve las herramientas disponibles."""
        if self.tools is None:
            return []

        return self.tools.listar()

    # ------------------------------------------------------------------
    # Prompt
    # ------------------------------------------------------------------

    def _descripcion_herramientas(self):
        """Lista de herramientas en texto (solo para el modo texto)."""

        herramientas = self._herramientas()

        if not herramientas:
            return "No tienes herramientas disponibles."

        lineas = ["HERRAMIENTAS DISPONIBLES:", ""]

        for herramienta in herramientas:
            argumentos = ", ".join(
                f"{p['nombre']} ({p['tipo']}{'' if p['requerido'] else ', opcional'})" for p in herramienta["parametros"]
            )

            lineas.append(f"- {herramienta['nombre']}({argumentos}): {herramienta['descripcion']}")

        return "\n".join(lineas)

    def _prompt_sistema(self, system=None, modo_texto=False):
        """Construye el prompt del sistema."""

        partes = []

        if system:
            partes.append(system)
        else:
            personalidad = self.gestor.personalidad() if self.gestor else ""

            partes.append(personalidad or PERSONALIDAD_BASICA)

        partes.append(f"FECHA Y HORA ACTUALES: {ahora_texto()}")

        recuerdos = self.gestor.recuerdos() if self.gestor else ""

        if recuerdos:
            partes.append("LO QUE SABES DEL USUARIO (memoria permanente):\n" + recuerdos)

        partes.append(REGLAS.strip())

        if modo_texto:
            partes.append(self._descripcion_herramientas())
            partes.append(REGLAS_TEXTO.strip())

        return "\n\n".join(partes)

    # ------------------------------------------------------------------
    # Órdenes de herramientas escritas en texto
    # ------------------------------------------------------------------

    def _extraer_json(self, respuesta):
        """
        Intenta extraer una orden JSON de la respuesta del modelo.

        Soporta:
        - JSON puro.
        - JSON dentro de bloques markdown.
        - Texto alrededor del JSON.
        """

        texto = (respuesta or "").strip()

        if not texto:
            return None

        # Caso 1: JSON puro
        try:
            return json.loads(texto)
        except json.JSONDecodeError:
            pass

        # Caso 2: bloque ```json ... ```
        bloque = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            texto,
            re.DOTALL,
        )

        if bloque:
            try:
                return json.loads(bloque.group(1))
            except json.JSONDecodeError:
                pass

        # Caso 3: localizar el primer objeto JSON
        inicio = texto.find("{")
        final = texto.rfind("}")

        if inicio != -1 and final > inicio:
            try:
                return json.loads(texto[inicio : final + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _es_orden_herramienta(self, orden):
        """Comprueba si una respuesta es una orden de herramienta."""

        if not isinstance(orden, dict):
            return False

        accion = str(orden.get("accion", "")).lower().strip()

        return accion in ACCIONES_HERRAMIENTA

    def _llamadas_desde_texto(self, contenido):
        """Convierte un JSON escrito en texto en una lista de llamadas."""

        orden = self._extraer_json(contenido)

        if not self._es_orden_herramienta(orden):
            return []

        argumentos = orden.get("argumentos", {})

        if not isinstance(argumentos, dict):
            argumentos = {}

        return [{"function": {"name": orden.get("nombre"), "arguments": argumentos}}]

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------

    def _ejecutar_herramienta(self, nombre, argumentos):
        """Ejecuta una herramienta y devuelve su resultado (o el error)."""

        if self.tools is None:
            return {"error": "BRAIN no tiene herramientas conectadas."}

        if not isinstance(argumentos, dict):
            argumentos = {}

        try:
            resultado = self.tools.ejecutar(nombre, argumentos)

        except Exception as error:
            logger.error(f"Herramienta {nombre} {argumentos}: {error}")

            resultado = {"error": str(error)}

        self.herramientas_usadas.append(
            {
                "nombre": nombre,
                "argumentos": argumentos,
                "resultado": resultado,
            }
        )

        return resultado

    @staticmethod
    def _json(valor):
        return json.dumps(valor, ensure_ascii=False, default=str)

    def _resumen_sin_texto(self):
        """Respuesta de emergencia si el modelo no escribe texto final."""

        if not self.herramientas_usadas:
            return "No he podido generar una respuesta. Prueba a reformular la pregunta."

        ultima = self.herramientas_usadas[-1]

        if isinstance(ultima["resultado"], dict) and "error" in ultima["resultado"]:
            return f"No he podido hacerlo: {ultima['resultado']['error']}"

        return "Hecho."

    # ------------------------------------------------------------------
    # Pregunta principal
    # ------------------------------------------------------------------

    def preguntar(
        self,
        mensaje,
        system=None,
        modelo=None,
        historial=None,
    ):
        """
        Envía una pregunta al modelo y devuelve la respuesta final.

        Si el modelo solicita herramientas las ejecuta, le devuelve los
        resultados y repite hasta que responde al usuario (máximo
        MAX_PASOS veces, para no quedarse en un bucle).
        """

        self.herramientas_usadas = []

        nombre_modelo = self.ollama.resolver_modelo(modelo)

        modo_texto = nombre_modelo in self._modo_texto

        for _ in range(2):
            try:
                return self._bucle(
                    mensaje,
                    system,
                    modelo,
                    historial,
                    modo_texto,
                )

            except SinHerramientasError:
                if modo_texto:
                    raise

                # El modelo no admite herramientas nativas: se repite
                # pidiéndole las órdenes en texto.
                self._modo_texto.add(nombre_modelo)

                modo_texto = True

                self.herramientas_usadas = []

        return self._resumen_sin_texto()

    def _bucle(self, mensaje, system, modelo, historial, modo_texto):
        mensajes = [
            {
                "role": "system",
                "content": self._prompt_sistema(system, modo_texto),
            }
        ]

        if historial:
            mensajes.extend(historial)

        mensajes.append({"role": "user", "content": mensaje})

        esquemas = None

        if self.tools is not None and not modo_texto:
            esquemas = self.tools.esquemas()

        for _ in range(self.MAX_PASOS):
            respuesta = self.ollama.chat_completo(
                mensajes,
                modelo=modelo,
                tools=esquemas,
            )

            contenido = respuesta.get("content", "") or ""

            llamadas = respuesta.get("tool_calls") or []

            if not llamadas:
                llamadas = self._llamadas_desde_texto(contenido)

            if not llamadas:
                return contenido.strip() or self._resumen_sin_texto()

            mensajes.append(
                {
                    "role": "assistant",
                    "content": contenido,
                    **({"tool_calls": respuesta["tool_calls"]} if respuesta.get("tool_calls") else {}),
                }
            )

            for llamada in llamadas:
                funcion = llamada.get("function", {})

                nombre = funcion.get("name")

                argumentos = funcion.get("arguments", {})

                # Algunas versiones envían los argumentos como texto JSON.
                if isinstance(argumentos, str):
                    try:
                        argumentos = json.loads(argumentos)
                    except json.JSONDecodeError:
                        argumentos = {}

                resultado = self._ejecutar_herramienta(nombre, argumentos)

                if modo_texto or not respuesta.get("tool_calls"):
                    mensajes.append(
                        {
                            "role": "user",
                            "content": (
                                f"Resultado real de la herramienta {nombre}:\n"
                                f"{self._json(resultado)}\n\n"
                                "Si necesitas otra herramienta, úsala. Si no, responde ya al usuario "
                                "con ese resultado, sin mostrar JSON ni mencionar herramientas."
                            ),
                        }
                    )
                else:
                    mensajes.append(
                        {
                            "role": "tool",
                            "tool_name": nombre,
                            "content": self._json(resultado),
                        }
                    )

        hechas = len(self.herramientas_usadas)
        fallos = sum(1 for h in self.herramientas_usadas if isinstance(h["resultado"], dict) and "error" in h["resultado"])

        return (
            f"Me he quedado a medias: he hecho {hechas} acciones ({fallos} con error) y no he podido terminar. "
            "Revisa lo que ya está guardado y pídeme lo que falte, mejor por partes."
        )
