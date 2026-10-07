"""
Cliente de Home Assistant (la "central" de domótica de la casa).

Home Assistant se conecta con casi todas las marcas (Philips Hue, IKEA,
Tuya, Shelly, Xiaomi, Zigbee, Z-Wave, Google, Alexa...). BRAIN solo habla con
Home Assistant, y Home Assistant habla con los aparatos.

Solo usa la biblioteca estándar de Python.
"""

import json
import os
from urllib import error, request

from brain.core.config import Config

# Direcciones habituales donde suele estar Home Assistant en una red doméstica.
DIRECCIONES_HABITUALES = (
    "http://homeassistant.local:8123",
    "http://homeassistant:8123",
    "http://127.0.0.1:8123",
    "http://localhost:8123",
)


class HomeAssistantError(RuntimeError):
    """Error al hablar con Home Assistant (el mensaje está pensado para el usuario)."""


def _archivo_configuracion():
    return Config.DATOS / "domotica" / "home_assistant.json"


def normalizar_url(url):
    """Acepta '192.168.1.5', 'homeassistant.local:8123', 'http://...'."""

    url = (url or "").strip().rstrip("/")

    if not url:
        return ""

    if "://" not in url:
        url = "http://" + url

    esquema, resto = url.split("://", 1)
    resto = resto.split("/", 1)[0]

    if ":" not in resto:
        resto += ":8123"

    return f"{esquema}://{resto}"


def leer_configuracion():
    """Devuelve (url, token). Las variables de entorno tienen prioridad."""

    url = os.environ.get("BRAIN_HA_URL", "").strip()
    token = os.environ.get("BRAIN_HA_TOKEN", "").strip()

    if not (url and token):
        try:
            datos = json.loads(_archivo_configuracion().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            datos = {}

        if isinstance(datos, dict):
            url = url or str(datos.get("url", "")).strip()
            token = token or str(datos.get("token", "")).strip()

    return normalizar_url(url), token


def guardar_configuracion(url, token):
    """Guarda la dirección y la llave de acceso de Home Assistant."""

    archivo = _archivo_configuracion()
    archivo.parent.mkdir(parents=True, exist_ok=True)

    archivo.write_text(
        json.dumps({"url": normalizar_url(url), "token": token.strip()}, indent=4),
        encoding="utf-8",
    )

    try:
        # En sistemas tipo Unix, que solo lo pueda leer el usuario.
        os.chmod(archivo, 0o600)
    except OSError:
        pass


class HomeAssistant:
    """Cliente de la API REST de Home Assistant."""

    def __init__(self, url=None, token=None, timeout=15):
        if url is None and token is None:
            url, token = leer_configuracion()

        self.url = normalizar_url(url)
        self.token = (token or "").strip()
        self.timeout = timeout

        # Home Assistant está en la red de casa: se ignora el proxy del sistema.
        self._opener = request.build_opener(request.ProxyHandler({}))

    @property
    def configurado(self):
        return bool(self.url and self.token)

    # ------------------------------------------------------------------
    # Comunicación
    # ------------------------------------------------------------------

    def _peticion(self, metodo, ruta, datos=None, texto=False):
        if not self.configurado:
            raise HomeAssistantError(
                "La domótica no está conectada todavía. Ejecuta CONFIGURAR_DOMOTICA.bat para conectar BRAIN con Home Assistant."
            )

        cuerpo = None

        if datos is not None:
            cuerpo = json.dumps(datos).encode("utf-8")

        peticion = request.Request(
            f"{self.url}{ruta}",
            data=cuerpo,
            method=metodo,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )

        try:
            with self._opener.open(peticion, timeout=self.timeout) as respuesta:
                contenido = respuesta.read().decode("utf-8")

        except error.HTTPError as e:
            if e.code == 401:
                raise HomeAssistantError(
                    "Home Assistant ha rechazado la llave de acceso (token). Crea una nueva y ejecuta CONFIGURAR_DOMOTICA.bat."
                ) from e

            if e.code == 404:
                raise HomeAssistantError(f"Home Assistant no reconoce la petición {ruta}.") from e

            detalle = e.read().decode("utf-8", errors="replace")[:200]

            raise HomeAssistantError(f"Home Assistant respondió con un error ({e.code}): {detalle}") from e

        except error.URLError as e:
            raise HomeAssistantError(
                f"No puedo conectar con Home Assistant en {self.url} ({e.reason}). "
                "¿Está encendido y en la misma red que este ordenador?"
            ) from e

        except (TimeoutError, OSError) as e:
            raise HomeAssistantError(f"Home Assistant no responde en {self.url}: {e}") from e

        if texto:
            return contenido

        try:
            return json.loads(contenido) if contenido else None
        except ValueError as e:
            raise HomeAssistantError("Home Assistant devolvió una respuesta que no entiendo.") from e

    # ------------------------------------------------------------------
    # Operaciones
    # ------------------------------------------------------------------

    def comprobar(self):
        """Lanza HomeAssistantError si no hay conexión válida."""

        self._peticion("GET", "/api/")

    def estados(self):
        """Lista de todas las entidades con su estado actual."""

        return self._peticion("GET", "/api/states") or []

    def estado(self, entity_id):
        return self._peticion("GET", f"/api/states/{entity_id}")

    def servicio(self, dominio, servicio, datos):
        """Ejecuta un servicio, por ejemplo light.turn_on con {'entity_id': ...}."""

        return self._peticion("POST", f"/api/services/{dominio}/{servicio}", datos or {})

    def areas(self):
        """
        Habitación de cada entidad, como {entity_id: nombre_de_la_habitación}.

        Home Assistant no da las habitaciones en /api/states, así que se
        piden con una plantilla. Si no se pueden obtener, se devuelve {}.
        """

        plantilla = "{% for s in states %}{{ s.entity_id }}|{{ area_name(s.entity_id) or '' }}\n{% endfor %}"

        try:
            texto = self._peticion("POST", "/api/template", {"template": plantilla}, texto=True)
        except HomeAssistantError:
            return {}

        resultado = {}

        for linea in (texto or "").splitlines():
            entidad, _, area = linea.partition("|")

            if entidad.strip() and area.strip() and area.strip().lower() != "none":
                resultado[entidad.strip()] = area.strip()

        return resultado


def encontrar_home_assistant():
    """
    Busca Home Assistant en las direcciones habituales (sin necesitar la
    llave). Devuelve la primera que responda, o '' si no encuentra ninguna.
    """

    for url in DIRECCIONES_HABITUALES:
        peticion = request.Request(f"{url}/api/", method="GET")
        opener = request.build_opener(request.ProxyHandler({}))

        try:
            opener.open(peticion, timeout=3)
            return url
        except error.HTTPError as e:
            # 401 = "necesito la llave": está ahí y funciona.
            if e.code in (401, 403):
                return url
        except (error.URLError, OSError):
            continue

    return ""
