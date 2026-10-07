import json
import os
import re
import shutil
import socket
import subprocess
import time
from urllib import error, request

from brain.core.config import Config
from brain.core.hardware import leer_modelo_guardado

# Orden de preferencia cuando no se indica un modelo concreto.
MODELOS_PREFERIDOS = (
    "qwen3.8:27b",
    "gemma4:26b",
    "gemma4:12b",
    "qwen3:8b",
    "gemma4:e4b",
    "gemma4:e2b",
    "qwen3:4b",
    "qwen3:latest",
    "llama3.1:8b",
    "llama3.2:3b",
    "gemma3:4b",
    "mistral:7b",
)


def _mostrar_progreso(estado, completado, total):
    """Muestra el avance de una descarga en la consola."""

    if total:
        porcentaje = completado * 100 // total
        print(f"\r  {estado[:30]:<30} {porcentaje:3d}% ({completado / 1024**3:.1f}/{total / 1024**3:.1f} GB)", end="", flush=True)
    elif estado:
        print(f"\r  {estado[:60]:<60}", end="", flush=True)

    if estado == "success":
        print()


class OllamaError(RuntimeError):
    """Error al comunicarse con Ollama."""


class SinHerramientasError(OllamaError):
    """El modelo elegido no admite herramientas (tool calling) nativas."""


def limpiar_pensamiento(texto):
    """
    Quita el razonamiento interno (<think>...</think>) que algunos
    modelos, como Qwen 3, incluyen en la respuesta.
    """

    if not texto:
        return ""

    texto = re.sub(r"<think>.*?</think>", "", texto, flags=re.DOTALL)

    if "</think>" in texto:
        texto = texto.split("</think>")[-1]

    if "<think>" in texto:
        texto = texto.split("<think>")[0]

    return texto.strip()


def buscar_ejecutable():
    """
    Localiza el programa de Ollama.

    Tras instalarlo con winget, Windows no actualiza el PATH de la
    ventana ya abierta, por eso también se buscan las rutas habituales.
    """

    ruta = shutil.which("ollama")

    if ruta:
        return ruta

    candidatos = []

    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        archivos = os.environ.get("PROGRAMFILES")

        if local:
            candidatos.append(os.path.join(local, "Programs", "Ollama", "ollama.exe"))

        if archivos:
            candidatos.append(os.path.join(archivos, "Ollama", "ollama.exe"))
    else:
        candidatos = ["/usr/local/bin/ollama", "/usr/bin/ollama"]

    for candidato in candidatos:
        if os.path.isfile(candidato):
            return candidato

    return None


class Ollama:
    """
    Cliente para comunicarse con Ollama.

    Soporta:
    - consultas normales y conversaciones con historial
    - selección automática del modelo instalado
    - tool calling nativo de Ollama (opcional)
    - arranque del servidor y descarga de modelos
    """

    def __init__(
        self,
        url=None,
        modelo=None,
        pensar=None,
    ):
        self.url = (url or Config.OLLAMA_URL).rstrip("/")

        # None = elegir automáticamente entre los modelos instalados.
        self.modelo = modelo if modelo is not None else (Config.MODELO or None)

        self.pensar = Config.PENSAR if pensar is None else pensar

        # Se ignora el proxy del sistema: Ollama es local y un proxy
        # corporativo o de antivirus puede romper la conexión.
        self._opener = request.build_opener(request.ProxyHandler({}))

        self._cache_modelos = {}
        self._sin_think = set()

    # ------------------------------------------------------------------
    # Estado del servidor y modelos
    # ------------------------------------------------------------------

    def servidor_activo(self):
        """Indica si Ollama responde."""

        try:
            self.modelos()
            return True
        except OllamaError:
            return False

    def iniciar_servidor(self, espera=25):
        """
        Arranca Ollama en segundo plano si no está funcionando.

        Devuelve True si el servidor queda disponible.
        """

        if self.servidor_activo():
            return True

        ejecutable = buscar_ejecutable()

        if not ejecutable:
            return False

        opciones = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        if os.name == "nt":
            opciones["creationflags"] = (
                subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            opciones["start_new_session"] = True

        try:
            subprocess.Popen([ejecutable, "serve"], **opciones)
        except OSError:
            return False

        limite = time.time() + espera

        while time.time() < limite:
            if self.servidor_activo():
                return True

            time.sleep(0.5)

        return False

    def descargar_modelo(self, nombre, progreso=None):
        """
        Descarga un modelo a través del propio servidor de Ollama que usa
        BRAIN (así se instala exactamente donde BRAIN lo va a buscar).

        `progreso(estado, completado, total)` se llama mientras descarga;
        por defecto se muestra el porcentaje en la consola.
        Devuelve True si la descarga termina bien.
        """

        if progreso is None:
            progreso = _mostrar_progreso

        peticion = request.Request(
            f"{self.url}/api/pull",
            data=json.dumps({"model": nombre, "stream": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        correcto = False

        try:
            with self._opener.open(peticion, timeout=600) as respuesta:
                for linea in respuesta:
                    try:
                        dato = json.loads(linea.decode("utf-8"))
                    except ValueError:
                        continue

                    if dato.get("error"):
                        raise OllamaError(f"Ollama no pudo descargar '{nombre}': {dato['error']}")

                    estado = dato.get("status", "")

                    progreso(estado, dato.get("completed", 0), dato.get("total", 0))

                    if estado == "success":
                        correcto = True

        except error.HTTPError as e:
            detalle = e.read().decode("utf-8", errors="replace")

            raise OllamaError(f"Ollama no pudo descargar '{nombre}' ({e.code}): {detalle}") from e

        except (error.URLError, TimeoutError, socket.timeout, ConnectionError) as e:
            raise OllamaError(f"Se cortó la descarga de '{nombre}': {e}") from e

        finally:
            self._cache_modelos.clear()

        return correcto

    def lista_por_comando(self):
        """Salida de `ollama list` (para el diagnóstico), o '' si no se puede."""

        ejecutable = buscar_ejecutable()

        if not ejecutable:
            return ""

        try:
            salida = subprocess.run([ejecutable, "list"], capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return ""

        return (salida.stdout or b"").decode("utf-8", errors="replace").strip()

    def modelos(self):
        """
        Devuelve los modelos disponibles en Ollama.
        """

        datos = self._abrir(
            request.Request(f"{self.url}/api/tags"),
            timeout=10,
        )

        return [modelo["name"] for modelo in datos.get("models", [])]

    @staticmethod
    def _buscar_modelo(nombre, instalados):
        nombre = nombre.lower()

        for instalado in instalados:
            if instalado.lower() == nombre:
                return instalado

        if ":" not in nombre:
            for instalado in instalados:
                if instalado.lower().startswith(nombre + ":"):
                    return instalado

        return None

    def resolver_modelo(self, modelo=None):
        """
        Decide qué modelo usar.

        Si se pide uno concreto debe estar instalado. Si no, se elige
        el mejor de la lista de preferidos que esté instalado, y en su
        defecto cualquier modelo de texto instalado.
        """

        solicitado = modelo or self.modelo

        if solicitado in self._cache_modelos:
            return self._cache_modelos[solicitado]

        instalados = self.modelos()

        elegido = None

        if solicitado:
            elegido = self._buscar_modelo(solicitado, instalados)

            if elegido is None:
                lista = ", ".join(instalados) or "ninguno"

                raise OllamaError(
                    f"El modelo '{solicitado}' no está instalado en Ollama "
                    f"(instalados: {lista}). "
                    f"Instálalo con: ollama pull {solicitado}"
                )
        else:
            # Primero el modelo que eligió "MEJORAR_IA.bat" (si sigue instalado).
            guardado = leer_modelo_guardado()

            if guardado:
                elegido = self._buscar_modelo(guardado, instalados)

            for preferido in MODELOS_PREFERIDOS:
                if elegido:
                    break

                elegido = self._buscar_modelo(preferido, instalados)

            if elegido is None:
                for instalado in instalados:
                    if "embed" not in instalado.lower():
                        elegido = instalado
                        break

            if elegido is None:
                raise OllamaError(
                    "Ollama no tiene ningún modelo instalado. "
                    "Ejecuta INSTALAR.bat o escribe: ollama pull qwen3:4b"
                )

        self._cache_modelos[solicitado] = elegido

        return elegido

    # ------------------------------------------------------------------
    # Conversación
    # ------------------------------------------------------------------

    def _enviar(self, mensajes, modelo=None, tools=None):
        """Envía mensajes a /api/chat y devuelve el mensaje de respuesta."""

        nombre_modelo = self.resolver_modelo(modelo)

        datos = {
            "model": nombre_modelo,
            "messages": mensajes,
            "stream": False,
        }

        if tools:
            datos["tools"] = tools

        if Config.CONTEXTO:
            datos["options"] = {"num_ctx": Config.CONTEXTO}

        if self.pensar is not None and nombre_modelo not in self._sin_think:
            datos["think"] = bool(self.pensar)

        try:
            resultado = self._post("/api/chat", datos)

        except OllamaError as e:
            if "does not support tools" in str(e).lower():
                raise SinHerramientasError(str(e)) from e

            # Algunos modelos o versiones de Ollama no admiten "think".
            if "think" in datos and "think" in str(e).lower():
                self._sin_think.add(nombre_modelo)
                datos.pop("think")
                resultado = self._post("/api/chat", datos)
            else:
                raise

        mensaje = dict(resultado.get("message") or {})
        mensaje["content"] = limpiar_pensamiento(mensaje.get("content", ""))

        return mensaje

    def chat(self, mensajes, modelo=None):
        """
        Envía una lista de mensajes ({"role": ..., "content": ...}) y
        devuelve el texto de la respuesta.
        """

        return self._enviar(mensajes, modelo=modelo)["content"]

    def chat_completo(self, mensajes, modelo=None, tools=None):
        """
        Envía mensajes y devuelve el mensaje completo de respuesta
        (con "content" y, si el modelo lo pide, "tool_calls").
        """

        return self._enviar(mensajes, modelo=modelo, tools=tools)

    def preguntar(
        self,
        mensaje,
        system=None,
        modelo=None,
        historial=None,
    ):
        """
        Hace una pregunta y devuelve el texto de la respuesta.

        `historial` es la lista de mensajes anteriores de la conversación.
        """

        mensajes = []

        if system:
            mensajes.append({"role": "system", "content": system})

        if historial:
            mensajes.extend(historial)

        mensajes.append({"role": "user", "content": mensaje})

        return self.chat(mensajes, modelo=modelo)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _abrir(self, peticion, timeout):
        """Abre una petición y traduce los errores a OllamaError."""

        try:
            with self._opener.open(peticion, timeout=timeout) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))

        except error.HTTPError as e:
            cuerpo = e.read().decode("utf-8", errors="replace")

            detalle = cuerpo

            try:
                contenido = json.loads(cuerpo)

                if isinstance(contenido, dict):
                    detalle = contenido.get("error", cuerpo)
            except ValueError:
                pass

            raise OllamaError(f"Error de Ollama ({e.code}): {detalle}") from e

        except error.URLError as e:
            raise OllamaError(
                f"No se puede conectar con Ollama en {self.url}: {e.reason}. "
                "¿Está abierto Ollama?"
            ) from e

        except (TimeoutError, socket.timeout) as e:
            raise OllamaError(
                "Ollama tardó demasiado en responder. Puede que el modelo "
                "sea demasiado grande para este equipo; prueba con qwen3:4b."
            ) from e

        except ConnectionError as e:
            raise OllamaError(f"Se perdió la conexión con Ollama: {e}") from e

    def _post(self, endpoint, datos):
        """
        Realiza una petición POST contra Ollama.
        """

        peticion = request.Request(
            f"{self.url}{endpoint}",
            data=json.dumps(datos).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        return self._abrir(peticion, timeout=300)
