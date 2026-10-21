import json
import re
<<<<<<< HEAD
import unicodedata

from brain.ai.herramientas_relevantes import categorias_relevantes, filtrar
=======

<<<<<<< HEAD
from brain.ai.herramientas_relevantes import categorias_relevantes, filtrar
=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
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
<<<<<<< HEAD
- NUNCA anuncies lo que vas a hacer ("voy a revisar la despensa", "déjame comprobar...", "un momento"). O llamas ya a la herramienta que necesitas, o contestas ya con el resultado completo. Una respuesta que solo dice lo que vas a hacer es un error.
- Si el usuario pide una receta, una idea para comer o cenar, o qué puede cocinar: RESPONDE DIRECTAMENTE con la receta completa (ingredientes con cantidades y pasos numerados). Si el usuario nombra un plato ("receta de tortilla"), dásela tal cual aunque no tenga todos los ingredientes y dile qué le falta. Si pide ideas, propón 2 o 3 platos hechos con la despensa más los básicos de casa (los datos de la despensa se te dan en este mensaje o con ingredientes_disponibles). Si falta algo, dilo y ofrece apuntarlo en la lista de la compra.
=======
<<<<<<< HEAD
- Si el usuario pide una receta, una idea para comer o cenar, o qué puede cocinar: llama PRIMERO a ingredientes_disponibles. Propón platos hechos solo con esos ingredientes (la despensa más los básicos de casa), con pasos claros y cantidades. Si falta algo, dilo y ofrece apuntarlo en la lista de la compra.
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
- Si el usuario elige una receta y quiere comprar lo que le falta (o pide "apunta lo que me falta"), llama a anadir_faltantes_receta_a_compra con TODOS los ingredientes de la receta: ella compara con la despensa y los básicos y apunta solo lo necesario. No vayas ingrediente por ingrediente.
- Si la pregunta puede estar en las notas o manuales del usuario (lavadora, caldera, wifi, apuntes), llama a buscar_en_documentos antes de contestar y di de qué documento sale. Si no hay nada, dilo; no inventes.
- Para copias de seguridad usa crear_copia_seguridad. Antes de restaurar_copia_seguridad pide confirmación al usuario: sustituye sus datos actuales.
- Para borrar la lista de la compra entera usa vaciar_lista_compra; para quitar un solo producto, quitar_de_compra. Para el inventario, borrar_del_inventario o vaciar_inventario. Solo cuando el usuario lo pida.
<<<<<<< HEAD
=======
=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
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


<<<<<<< HEAD
def _sin_acentos(texto):
    normal = unicodedata.normalize("NFD", str(texto or ""))

    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower()


# El mensaje del usuario pide una receta o una idea para comer.
_PIDE_RECETA = re.compile(
    r"receta|cocinar|cocino|\bcocin|para cenar|para comer|de cenar|de comer|que ceno|que como\b|que preparo|que hago de|menu|plato"
)

# Respuestas que solo cuentan lo que el modelo va a hacer, en vez de hacerlo.
_ANUNCIO = re.compile(
    r"\b(voy a|vamos a|ire a|primero (voy|debo|necesito|tengo|hay que)|dejame|permiteme|deja que|dame un (momento|segundo|segundito)|"
    r"un momento|un segundito|ahora mismo (voy|te|reviso|compruebo)|"
    r"(revisare|comprobare|consultare|mirare|buscare|verificare|preparare|calculare|apuntare|anadire|guardare|"
    r"revisar|comprobar|consultar) (primero|antes|la despensa|tu despensa|el inventario|que|lo que))\b"
)


def parece_anuncio(texto):
    """True si el texto solo anuncia una acción futura ("voy a revisar tu despensa...") en lugar de responder."""

    limpio = _sin_acentos(texto).strip()

    if not limpio or len(limpio) > 450:
        return False

    return bool(_ANUNCIO.search(limpio)) or limpio.endswith(":")


def pide_receta(mensaje):
    return bool(_PIDE_RECETA.search(_sin_acentos(mensaje)))


=======
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
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

<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
        # Tema de la conversación en curso ("solo recetas"...), si lo tiene.
        self.contexto_extra = None

        # Categorías de herramientas que se enseñan en la pregunta en curso.
        self._categorias = None

<<<<<<< HEAD
=======
=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
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

<<<<<<< HEAD
        herramientas = filtrar(self._herramientas(), self._categorias)
=======
<<<<<<< HEAD
        herramientas = filtrar(self._herramientas(), self._categorias)
=======
        herramientas = self._herramientas()
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80

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

<<<<<<< HEAD
        if self.contexto_extra:
            partes.append("TEMA DE ESTA CONVERSACIÓN (síguelo): " + self.contexto_extra)

=======
<<<<<<< HEAD
        if self.contexto_extra:
            partes.append("TEMA DE ESTA CONVERSACIÓN (síguelo): " + self.contexto_extra)

=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
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

<<<<<<< HEAD
    def _precargar_despensa(self, mensaje):
        """Texto con la despensa ya consultada si el usuario pide una receta; "" en otro caso."""

        if self.tools is None or not pide_receta(mensaje):
            return ""

        if self.tools.obtener("ingredientes_disponibles") is None:
            return ""

        resultado = self._ejecutar_herramienta("ingredientes_disponibles", {})

        if isinstance(resultado, dict) and "error" in resultado:
            return ""

        return (
            "DESPENSA DEL USUARIO (ya consultada por ti; no vuelvas a consultarla ni anuncies que vas a hacerlo):\n"
            f"{self._json(resultado)}\n"
            "Responde AHORA con la receta o las ideas completas: ingredientes con cantidades y pasos numerados. "
            "Si el usuario nombró un plato concreto, da ese plato aunque falten ingredientes y di cuáles faltan."
        )

=======
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
    def _resumen_sin_texto(self):
        """Respuesta de emergencia si el modelo no escribe texto final."""

        if not self.herramientas_usadas:
<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
            return (
                "No he sabido qué hacer con eso. Prueba a pedírmelo de otra forma, por ejemplo: "
                "«enciende la luz del salón», «apunta leche en la compra» o «qué puedo cocinar hoy»."
            )
<<<<<<< HEAD
=======
=======
            return "No he podido generar una respuesta. Prueba a reformular la pregunta."
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80

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
<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
        # Solo se describen las herramientas de los temas de los que se habla:
        # con todas, las descripciones llenan la memoria de trabajo del modelo.
        self._categorias = categorias_relevantes(mensaje, historial)

<<<<<<< HEAD
=======
=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
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
<<<<<<< HEAD
            esquemas = self.tools.esquemas(self._categorias)

        # Receta o idea para comer: los datos de la despensa se consultan aquí, en código, y se
        # le dan al modelo ya leídos. Así no puede quedarse en "voy a revisar tu despensa".
        despensa = self._precargar_despensa(mensaje)

        if despensa:
            mensajes[0]["content"] += "\n\n" + despensa

        vacios = 0
        anuncios = 0
=======
<<<<<<< HEAD
            esquemas = self.tools.esquemas(self._categorias)

        vacios = 0
=======
            esquemas = self.tools.esquemas()
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80

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
<<<<<<< HEAD
                if contenido.strip() and parece_anuncio(contenido) and anuncios < 2:
                    # Solo cuenta lo que va a hacer: se le exige que lo haga ya.
                    anuncios += 1
                    mensajes.append({"role": "assistant", "content": contenido})
                    mensajes.append(
                        {
                            "role": "user",
                            "content": (
                                "No me cuentes lo que vas a hacer: hazlo ahora. Si necesitas una herramienta, llámala ya. "
                                "Si no, responde directamente con el resultado completo (la receta entera, la respuesta "
                                "con todos los datos...), sin avisos previos."
                            ),
                        }
                    )

                    continue

=======
<<<<<<< HEAD
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
                if contenido.strip():
                    return contenido.strip()

                # Los modelos pequeños a veces devuelven una respuesta vacía.
                # Se les pide una vez más que contesten con texto.
                vacios += 1

                if vacios > 1:
                    return self._resumen_sin_texto()

                mensajes.append(
                    {
                        "role": "user",
                        "content": (
                            "No has escrito ninguna respuesta. Contesta ahora al usuario en español, con una frase "
                            "clara. Si necesitas una herramienta para hacerlo, úsala."
                        ),
                    }
                )

                continue
<<<<<<< HEAD
=======
=======
                return contenido.strip() or self._resumen_sin_texto()
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80

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
