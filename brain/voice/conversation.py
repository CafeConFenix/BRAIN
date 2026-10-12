# Un mensaje largo (una lista de 40 productos pegada, por ejemplo) se guarda
# recortado en el historial: ya está hecho y repetirlo en cada pregunta solo
# gasta la memoria de trabajo de la IA.
MAX_CARACTERES_HISTORIAL = 1200


def recortar(texto, limite=MAX_CARACTERES_HISTORIAL):
    if len(texto) <= limite:
        return texto

    return texto[: limite - 120].rstrip() + f"\n[... recortado: el mensaje original tenía {len(texto)} caracteres ...]"


class Conversation:
    """
    Gestiona una conversación con BRAIN.

    Mantiene el historial de mensajes y lo guarda en disco
    (datos/conversaciones/historial.json), de modo que BRAIN recuerda
    la conversación aunque se cierre y se vuelva a abrir.
    """

    CATEGORIA = "conversaciones"
    ARCHIVO = "historial"  # el de la conversación principal ("general")

    def __init__(self, brain, max_messages=20, persistente=True, id="general", instrucciones=None):
        self.brain = brain
        self.max_messages = max_messages
        self.persistente = persistente
        self.id = id
        self.instrucciones = instrucciones
        self.historial = []

        if id != "general":
            self.ARCHIVO = f"c_{id}"

        self._cargar()

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def _cargar(self):
        if not self.persistente:
            return

        datos = self.brain.data.leer(self.CATEGORIA, self.ARCHIVO)

        if not isinstance(datos, dict):
            return

        for mensaje in datos.get("mensajes", []):
            if (
                isinstance(mensaje, dict)
                and mensaje.get("role") in {"user", "assistant"}
                and isinstance(mensaje.get("content"), str)
            ):
                self.historial.append(
                    {
                        "role": mensaje["role"],
                        "content": mensaje["content"],
                    }
                )

        self._limitar_historial()

    def _guardar(self):
        if not self.persistente:
            return

        try:
            self.brain.data.guardar(
                self.CATEGORIA,
                self.ARCHIVO,
                {"mensajes": self.historial},
            )
        except OSError:
            # No poder guardar el historial no debe impedir seguir hablando.
            pass

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def limpiar(self):
        """Borra el historial de la conversación actual."""
        self.historial.clear()
        self._guardar()

    def mensajes(self):
        """Devuelve una copia del historial."""
        return list(self.historial)

    def preguntar(self, mensaje):
        """
        Envía un mensaje a BRAIN y guarda la conversación.

        Si la IA falla, el mensaje no se guarda en el historial y el
        error se propaga para que quien llame lo muestre.
        """

        respuesta = self._lista_pegada(mensaje)

        if respuesta is None:
            # El tema de esta conversación (por ejemplo "solo recetas") se añade
            # al prompt de la IA solo mientras se contesta aquí.
            self.brain.ai.contexto_extra = self.instrucciones

            try:
                respuesta = self.brain.ai.preguntar(
                    mensaje,
                    historial=list(self.historial),
                )
            finally:
                self.brain.ai.contexto_extra = None

        self.historial.append({"role": "user", "content": recortar(mensaje)})
        self.historial.append({"role": "assistant", "content": recortar(respuesta)})

        self._limitar_historial()
        self._guardar()

        return respuesta

    def registrar_intercambio(self, mensaje, respuesta):
        """Guarda en el historial algo que ha pasado sin la IA (por ejemplo, una captura leída)."""

        self.historial.append({"role": "user", "content": recortar(mensaje)})
        self.historial.append({"role": "assistant", "content": recortar(respuesta)})

        self._limitar_historial()
        self._guardar()

    def _lista_pegada(self, mensaje):
        """
        Si el mensaje es una lista larga de productos con cantidades, la guarda
        directamente (sin pasar por la IA, que se equivoca con listas largas).
        Por defecto va a la despensa; solo va a la compra si el usuario lo dice.
        Devuelve la respuesta, o None si no era una lista.
        """

        from brain.utils.listas import aplicar_lista, interpretar_lista, parece_lista_pegada

        if not parece_lista_pegada(mensaje):
            return None

        inventario = self.brain.modules.obtener("inventario")
        compras = self.brain.modules.obtener("compras")

        if inventario is None or compras is None:
            return None

        interpretada = interpretar_lista(mensaje)

        resultado = aplicar_lista(interpretada, inventario, compras)

        self.brain.ai.herramientas_usadas = [
            {
                "nombre": "anadir_a_compra" if resultado["destino"] == "compra" else "anadir_varios_inventario",
                "argumentos": {"productos": resultado["total"]},
                "resultado": resultado,
            }
        ]

        texto = resultado["texto"]

        if resultado["destino"] == "compra":
            texto += " Si era para la despensa, dímelo y lo cambio."
        else:
            texto += " Los ves en el panel de la derecha. Si querías la lista de la compra, dímelo y lo cambio."

        return texto

    def _limitar_historial(self):
        """Limita el tamaño del historial."""

        if len(self.historial) > self.max_messages:
            exceso = len(self.historial) - self.max_messages

            del self.historial[:exceso]

        # El historial siempre debe empezar por un mensaje del usuario.
        while self.historial and self.historial[0]["role"] != "user":
            del self.historial[0]


class GestorConversaciones:
    """
    Varias conversaciones en paralelo, cada una con su historial (y, si se
    quiere, un tema: "esta conversación es solo de recetas").

    La conversación "general" es la de siempre (datos/conversaciones/historial.json)
    y no se puede borrar. Las demás se guardan como c_<id>.json y se listan en
    datos/conversaciones/indice.json.
    """

    INDICE = "indice"
    TITULO_NUEVA = "Nueva conversación"
    MAX_CONVERSACIONES = 30

    def __init__(self, brain, persistente=True):
        self.brain = brain
        self.persistente = persistente
        self._abiertas = {}

    # ------------------------------------------------------------------
    # Índice
    # ------------------------------------------------------------------

    def _leer_indice(self):
        datos = self.brain.data.leer(Conversation.CATEGORIA, self.INDICE) if self.persistente else None
        lista = []

        if isinstance(datos, dict):
            for c in datos.get("conversaciones", []):
                if isinstance(c, dict) and isinstance(c.get("id"), str) and c["id"] != "general":
                    lista.append(
                        {
                            "id": c["id"],
                            "titulo": str(c.get("titulo") or self.TITULO_NUEVA)[:60],
                            "instrucciones": c.get("instrucciones") or None,
                            "creada": c.get("creada", ""),
                            "actualizada": c.get("actualizada", ""),
                        }
                    )

        if not self.persistente:
            lista = list(getattr(self, "_indice_memoria", []))

        return lista

    def _guardar_indice(self, lista):
        if not self.persistente:
            self._indice_memoria = lista
            return

        try:
            self.brain.data.guardar(Conversation.CATEGORIA, self.INDICE, {"conversaciones": lista})
        except OSError:
            pass

    @staticmethod
    def _ahora():
        from datetime import datetime

        return datetime.now().isoformat(timespec="seconds")

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------

    def obtener(self, id=None):
        """La conversación pedida (por defecto la principal). Lanza KeyError si no existe."""

        id = id or "general"

        if id in self._abiertas:
            return self._abiertas[id]

        instrucciones = None

        if id != "general":
            datos = next((c for c in self._leer_indice() if c["id"] == id), None)

            if datos is None:
                raise KeyError(f"No existe la conversación '{id}'.")

            instrucciones = datos["instrucciones"]

        conversacion = Conversation(self.brain, persistente=self.persistente, id=id, instrucciones=instrucciones)
        self._abiertas[id] = conversacion

        return conversacion

    def listar(self):
        """Todas las conversaciones, la principal primero y luego la más reciente primero."""

        resultado = [
            {
                "id": "general",
                "titulo": "Conversación principal",
                "instrucciones": None,
                "mensajes": len(self.obtener("general").historial),
                "actualizada": "",
            }
        ]

        otras = sorted(self._leer_indice(), key=lambda c: c["actualizada"] or c["creada"], reverse=True)

        for c in otras:
            resultado.append(
                {
                    "id": c["id"],
                    "titulo": c["titulo"],
                    "instrucciones": c["instrucciones"],
                    "mensajes": len(self.obtener(c["id"]).historial),
                    "actualizada": c["actualizada"],
                }
            )

        return resultado

    def crear(self, titulo=None, instrucciones=None):
        import uuid

        lista = self._leer_indice()

        if len(lista) >= self.MAX_CONVERSACIONES:
            raise ValueError(f"Ya hay {self.MAX_CONVERSACIONES} conversaciones. Borra alguna para crear otra.")

        titulo = (titulo or "").strip() or self.TITULO_NUEVA
        instrucciones = (instrucciones or "").strip() or None

        if instrucciones and len(instrucciones) > 500:
            raise ValueError("El tema de la conversación es demasiado largo (máximo 500 caracteres).")

        ahora = self._ahora()
        nueva = {
            "id": uuid.uuid4().hex[:8],
            "titulo": titulo[:60],
            "instrucciones": instrucciones,
            "creada": ahora,
            "actualizada": ahora,
        }

        lista.append(nueva)
        self._guardar_indice(lista)

        return nueva

    def renombrar(self, id, titulo):
        lista = self._leer_indice()
        titulo = (titulo or "").strip()

        if not titulo:
            raise ValueError("El título no puede estar vacío.")

        for c in lista:
            if c["id"] == id:
                c["titulo"] = titulo[:60]
                self._guardar_indice(lista)

                return c

        raise KeyError(f"No existe la conversación '{id}'.")

    def borrar(self, id):
        if id == "general":
            raise ValueError("La conversación principal no se puede borrar (sí vaciar).")

        lista = self._leer_indice()
        restantes = [c for c in lista if c["id"] != id]

        if len(restantes) == len(lista):
            raise KeyError(f"No existe la conversación '{id}'.")

        self._guardar_indice(restantes)
        self._abiertas.pop(id, None)

        if self.persistente:
            self.brain.data.eliminar(Conversation.CATEGORIA, f"c_{id}")

    def preguntar(self, id, mensaje):
        """Pregunta en una conversación concreta y actualiza su fecha y título."""

        conversacion = self.obtener(id)
        respuesta = conversacion.preguntar(mensaje)

        if id and id != "general":
            lista = self._leer_indice()

            for c in lista:
                if c["id"] == id:
                    c["actualizada"] = self._ahora()

                    if c["titulo"] == self.TITULO_NUEVA:
                        c["titulo"] = " ".join(mensaje.split())[:40]

            self._guardar_indice(lista)

        return respuesta
