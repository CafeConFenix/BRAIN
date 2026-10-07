class Conversation:
    """
    Gestiona una conversación con BRAIN.

    Mantiene el historial de mensajes y lo guarda en disco
    (datos/conversaciones/historial.json), de modo que BRAIN recuerda
    la conversación aunque se cierre y se vuelva a abrir.
    """

    CATEGORIA = "conversaciones"
    ARCHIVO = "historial"

    def __init__(self, brain, max_messages=20, persistente=True):
        self.brain = brain
        self.max_messages = max_messages
        self.persistente = persistente
        self.historial = []

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

        respuesta = self.brain.ai.preguntar(
            mensaje,
            historial=list(self.historial),
        )

        self.historial.append({"role": "user", "content": mensaje})
        self.historial.append({"role": "assistant", "content": respuesta})

        self._limitar_historial()
        self._guardar()

        return respuesta

    def _limitar_historial(self):
        """Limita el tamaño del historial."""

        if len(self.historial) > self.max_messages:
            exceso = len(self.historial) - self.max_messages

            del self.historial[:exceso]

        # El historial siempre debe empezar por un mensaje del usuario.
        while self.historial and self.historial[0]["role"] != "user":
            del self.historial[0]
