import time
import unicodedata

from brain.base.modulo import ModuloBase
from brain.core import logger
from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, leer_configuracion

# Tipos de aparato que BRAIN puede controlar.
CONTROLABLES = (
    "light",
    "switch",
    "fan",
    "cover",
    "climate",
    "scene",
    "script",
    "input_boolean",
    "media_player",
    "humidifier",
    "vacuum",
)

# Tipos que BRAIN solo puede LEER (nunca controlar): por seguridad, una
# conversación no debe abrir cerraduras ni desactivar alarmas.
SOLO_LECTURA = ("sensor", "binary_sensor", "lock", "alarm_control_panel", "weather", "person", "device_tracker")

# Cubiertas que nunca se abren por voz o chat (garajes, portones, puertas).
COVERS_PROHIBIDAS = ("garage", "gate", "door")

NOMBRES_DOMINIO = {
    "light": "luces",
    "switch": "enchufes e interruptores",
    "fan": "ventiladores",
    "cover": "persianas y cortinas",
    "climate": "climatización",
    "scene": "escenas",
    "script": "scripts",
    "input_boolean": "interruptores virtuales",
    "media_player": "reproductores y televisiones",
    "humidifier": "humidificadores",
    "vacuum": "aspiradoras",
    "sensor": "sensores",
    "binary_sensor": "sensores de presencia, puertas y ventanas",
    "lock": "cerraduras",
    "alarm_control_panel": "alarmas",
}

# Palabras que usa la gente para cada tipo de aparato.
PALABRAS_DOMINIO = {
    "luz": "light",
    "luces": "light",
    "lampara": "light",
    "lamparas": "light",
    "bombilla": "light",
    "bombillas": "light",
    "foco": "light",
    "focos": "light",
    "led": "light",
    "leds": "light",
    "enchufe": "switch",
    "enchufes": "switch",
    "interruptor": "switch",
    "interruptores": "switch",
    "regleta": "switch",
    "ventilador": "fan",
    "ventiladores": "fan",
    "persiana": "cover",
    "persianas": "cover",
    "cortina": "cover",
    "cortinas": "cover",
    "toldo": "cover",
    "toldos": "cover",
    "estor": "cover",
    "estores": "cover",
    "termostato": "climate",
    "calefaccion": "climate",
    "aire": "climate",
    "clima": "climate",
    "radiador": "climate",
    "escena": "scene",
    "television": "media_player",
    "tele": "media_player",
    "tv": "media_player",
    "altavoz": "media_player",
    "altavoces": "media_player",
    "aspiradora": "vacuum",
    "robot": "vacuum",
    "humidificador": "humidifier",
}

PLURALES = {"luces", "lamparas", "bombillas", "focos", "leds", "persianas", "cortinas", "toldos", "estores", "enchufes"}

# Palabras que no ayudan a identificar un aparato.
RELLENO = {
    "el", "la", "los", "las", "un", "una", "de", "del", "al", "en", "mi", "mis", "tu", "y", "a", "por", "para",
    "todo", "toda", "todos", "todas", "que", "se", "lo", "con", "esta", "este", "esa", "ese",
}  # fmt: skip

PALABRAS_SEGURIDAD = ("cerradura", "puerta", "garaje", "alarma", "portal", "candado")

COLORES = {
    "rojo": (255, 0, 0),
    "verde": (0, 200, 0),
    "azul": (0, 0, 255),
    "amarillo": (255, 220, 0),
    "naranja": (255, 120, 0),
    "rosa": (255, 105, 180),
    "morado": (128, 0, 200),
    "violeta": (138, 43, 226),
    "lila": (180, 130, 255),
    "cian": (0, 220, 255),
    "turquesa": (0, 210, 190),
    "blanco": (255, 255, 255),
}

TEMPERATURAS_COLOR = {
    "calida": 2700,
    "calido": 2700,
    "neutra": 4000,
    "neutro": 4000,
    "fria": 6000,
    "frio": 6000,
}

SEGUNDOS_CACHE_CATALOGO = 60


def normalizar(texto):
    """Minúsculas y sin acentos."""

    normal = unicodedata.normalize("NFD", str(texto))

    return "".join(c for c in normal if unicodedata.category(c) != "Mn").lower().strip()


def _raiz(palabra):
    """Quita plurales sencillos (luces -> luc, salones -> salon)."""

    if len(palabra) > 4 and palabra.endswith("es"):
        return palabra[:-2]

    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]

    return palabra


def _palabras(texto):
    limpio = "".join(c if c.isalnum() else " " for c in normalizar(texto))

    return limpio.split()


class Domotica(ModuloBase):
    """
    Control de la casa a través de Home Assistant: luces, enchufes,
    persianas, climatización, escenas y lectura de sensores.

    Los datos de BRAIN (habitaciones, escenas...) siguen en domotica.json;
    los aparatos reales los gestiona Home Assistant.
    """

    nombre = "domotica"

    def __init__(self):
        super().__init__()

        self._ha = None
        self._catalogo = None
        self._catalogo_hasta = 0.0

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    @property
    def ha(self):
        """Cliente de Home Assistant (se vuelve a leer la configuración cada vez)."""

        url, token = leer_configuracion()

        if self._ha is None or (self._ha.url, self._ha.token) != (url, token):
            self._ha = HomeAssistant(url, token)
            self.olvidar_catalogo()

        return self._ha

    def conectado(self):
        return self.ha.configurado

    def olvidar_catalogo(self):
        self._catalogo = None
        self._catalogo_hasta = 0.0

    # ------------------------------------------------------------------
    # Catálogo de aparatos
    # ------------------------------------------------------------------

    def _cargar_catalogo(self):
        """Lista de aparatos con nombre, tipo, habitación y estado."""

        ahora = time.time()

        cliente = self.ha  # si cambió la configuración, vacía el catálogo

        if self._catalogo is not None and ahora < self._catalogo_hasta:
            return self._catalogo

        estados = cliente.estados()
        areas = cliente.areas()

        catalogo = []

        for estado in estados:
            entidad = estado.get("entity_id", "")
            dominio = entidad.split(".", 1)[0]

            if dominio not in CONTROLABLES and dominio not in SOLO_LECTURA:
                continue

            atributos = estado.get("attributes") or {}

            if atributos.get("hidden"):
                continue

            if dominio == "cover" and atributos.get("device_class") in COVERS_PROHIBIDAS:
                continue

            nombre = atributos.get("friendly_name") or entidad

            catalogo.append(
                {
                    "entidad": entidad,
                    "dominio": dominio,
                    "nombre": nombre,
                    "habitacion": areas.get(entidad, ""),
                    "estado": estado.get("state", ""),
                    "atributos": atributos,
                    "_palabras_nombre": {_raiz(p) for p in _palabras(nombre)},
                    "_palabras_clave": {
                        _raiz(p) for p in _palabras(nombre) if p not in PALABRAS_DOMINIO and p not in RELLENO
                    },
                    "_palabras_area": {_raiz(p) for p in _palabras(areas.get(entidad, ""))},
                }
            )

        self._catalogo = catalogo
        self._catalogo_hasta = ahora + SEGUNDOS_CACHE_CATALOGO

        return catalogo

    # ------------------------------------------------------------------
    # Búsqueda
    # ------------------------------------------------------------------

    @staticmethod
    def _analizar(texto):
        """
        Separa lo que dice el usuario en: tipo de aparato pedido, palabras que
        identifican el aparato y si habla en plural / "todas".
        """

        dominios = set()
        claves = []
        plural = False

        for palabra in _palabras(texto):
            if palabra in ("todo", "toda", "todos", "todas"):
                plural = True
                continue

            if palabra in RELLENO:
                continue

            if palabra in PALABRAS_DOMINIO:
                dominios.add(PALABRAS_DOMINIO[palabra])

                if palabra in PLURALES:
                    plural = True

                continue

            claves.append(_raiz(palabra))

        return dominios, claves, plural

    def buscar(self, texto, dominios=None, incluir_lectura=False):
        """
        Busca aparatos que encajen con lo que dijo el usuario ("luz del
        salón", "persiana del dormitorio"...).

        Devuelve (aparatos, plural): `plural` es True si el usuario habló de
        varios a la vez ("todas las luces del salón").
        """

        pedidos, claves, plural = self._analizar(texto)

        if dominios:
            # La herramienta limita los tipos; si el usuario nombró otro tipo
            # que no encaja, manda la herramienta.
            pedidos = (pedidos & set(dominios)) or set(dominios)

        candidatos = []

        for aparato in self._cargar_catalogo():
            if aparato["dominio"] not in CONTROLABLES and not incluir_lectura:
                continue

            if pedidos and aparato["dominio"] not in pedidos:
                continue

            candidatos.append(aparato)

        if not claves:
            return (candidatos if pedidos else []), plural

        claves_set = set(claves)

        # 1) Los que tienen todas las palabras en su propio nombre.
        por_nombre = [a for a in candidatos if claves_set <= a["_palabras_nombre"]]

        if por_nombre:
            # "la luz del salón" -> la que se llama exactamente así, aunque
            # haya otras como "Luz salón techo". Si habla en plural, todas.
            exactos = [a for a in por_nombre if a["_palabras_clave"] == claves_set]

            if len(exactos) > 1:
                # "la luz del salón": entre "Luz salón" y "Lámpara salón",
                # la que lleva la palabra que dijo el usuario.
                dichas = {_raiz(p) for p in _palabras(texto) if p in PALABRAS_DOMINIO}
                con_palabra = [a for a in exactos if dichas and dichas <= a["_palabras_nombre"]]

                if len(con_palabra) == 1:
                    exactos = con_palabra

            if len(exactos) == 1 and not plural:
                return exactos, plural

            return por_nombre, plural

        # 2) Palabras repartidas entre el nombre y la habitación.
        por_conjunto = [a for a in candidatos if claves_set <= (a["_palabras_nombre"] | a["_palabras_area"])]

        if por_conjunto:
            return por_conjunto, plural

        # 3) Solo la habitación ("las luces del salón").
        por_habitacion = [a for a in candidatos if a["_palabras_area"] and claves_set <= a["_palabras_area"]]

        if por_habitacion:
            return por_habitacion, True

        return [], plural

    def _resolver(self, texto, dominios, todos=False):
        """
        Encuentra los aparatos de una orden. Devuelve (aparatos, respuesta_error):
        si hay un problema (nada encontrado o ambigüedad) `respuesta_error`
        es un diccionario listo para devolver a la IA.
        """

        try:
            aparatos, plural = self.buscar(texto, dominios)
        except HomeAssistantError as e:
            return [], {"error": str(e)}

        if not aparatos:
            if any(p in normalizar(texto) for p in PALABRAS_SEGURIDAD):
                return [], {
                    "error": "Por seguridad no controlo cerraduras, puertas, garajes ni alarmas. Tendrás que hacerlo tú."
                }

            ejemplos = ", ".join(sorted({a["nombre"] for a in self._cargar_catalogo() if a["dominio"] in (dominios or CONTROLABLES)})[:12])

            return [], {
                "error": f"No encuentro ningún aparato que encaje con '{texto}'.",
                "aparatos_disponibles": ejemplos or "ninguno",
            }

        if len(aparatos) > 1 and not (todos or plural):
            opciones = [f"{a['nombre']}" + (f" ({a['habitacion']})" if a["habitacion"] else "") for a in aparatos[:10]]

            return [], {
                "ambiguo": True,
                "mensaje": "Hay varios aparatos que encajan. Pregunta al usuario a cuál se refiere, o repite la orden con todos=true si quiere todos.",
                "opciones": opciones,
            }

        return aparatos, None

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _ejecutar(self, aparatos, servicio_por_dominio, datos_extra=None):
        hechos = []
        fallos = []

        for aparato in aparatos:
            servicio = servicio_por_dominio.get(aparato["dominio"])

            if servicio is None:
                fallos.append(f"{aparato['nombre']}: no admite esa acción")
                continue

            datos = {"entity_id": aparato["entidad"]}

            if datos_extra:
                datos.update(datos_extra.get(aparato["dominio"], {}))

            try:
                self.ha.servicio(aparato["dominio"], servicio, datos)
                hechos.append(aparato["nombre"])
                logger.sistema(f"Domótica: {aparato['dominio']}.{servicio} -> {aparato['entidad']}")
            except HomeAssistantError as e:
                fallos.append(f"{aparato['nombre']}: {e}")

        self.olvidar_catalogo()

        resultado = {"hecho_en": hechos}

        if fallos:
            resultado["fallos"] = fallos

        return resultado

    def encender(self, texto, todos=False):
        aparatos, problema = self._resolver(texto, None, todos)

        if problema:
            return problema

        return self._ejecutar(
            aparatos,
            {
                "light": "turn_on",
                "switch": "turn_on",
                "fan": "turn_on",
                "cover": "open_cover",
                "climate": "turn_on",
                "scene": "turn_on",
                "script": "turn_on",
                "input_boolean": "turn_on",
                "media_player": "turn_on",
                "humidifier": "turn_on",
                "vacuum": "start",
            },
        )

    def apagar(self, texto, todos=False):
        aparatos, problema = self._resolver(texto, None, todos)

        if problema:
            return problema

        return self._ejecutar(
            aparatos,
            {
                "light": "turn_off",
                "switch": "turn_off",
                "fan": "turn_off",
                "cover": "close_cover",
                "climate": "turn_off",
                "input_boolean": "turn_off",
                "media_player": "turn_off",
                "humidifier": "turn_off",
                "vacuum": "return_to_base",
            },
        )

    def regular_luz(self, texto, brillo=None, color=None, temperatura=None, todos=False):
        aparatos, problema = self._resolver(texto, ["light"], todos)

        if problema:
            return problema

        datos = {}

        if brillo is not None:
            datos["brightness_pct"] = max(1, min(100, int(round(float(brillo)))))

        if color:
            clave = normalizar(color)

            if clave not in COLORES:
                return {"error": f"No conozco el color '{color}'. Colores: {', '.join(COLORES)}."}

            datos["rgb_color"] = list(COLORES[clave])

        if temperatura:
            clave = normalizar(temperatura)

            if clave not in TEMPERATURAS_COLOR:
                return {"error": "La temperatura de la luz puede ser: cálida, neutra o fría."}

            datos["color_temp_kelvin"] = TEMPERATURAS_COLOR[clave]

        if not datos:
            return {"error": "Indica el brillo (0-100), un color o una temperatura de luz."}

        return self._ejecutar(aparatos, {"light": "turn_on"}, {"light": datos})

    def posicion_persiana(self, texto, posicion, todos=False):
        aparatos, problema = self._resolver(texto, ["cover"], todos)

        if problema:
            return problema

        posicion = max(0, min(100, int(round(float(posicion)))))

        return self._ejecutar(aparatos, {"cover": "set_cover_position"}, {"cover": {"position": posicion}})

    def poner_temperatura(self, texto, grados, todos=False):
        aparatos, problema = self._resolver(texto, ["climate"], todos)

        if problema:
            return problema

        grados = float(grados)

        if not 5 <= grados <= 35:
            return {"error": "La temperatura debe estar entre 5 y 35 grados."}

        return self._ejecutar(aparatos, {"climate": "set_temperature"}, {"climate": {"temperature": grados}})

    def activar_escena(self, texto):
        aparatos, problema = self._resolver(texto, ["scene", "script"], False)

        if problema:
            return problema

        return self._ejecutar(aparatos, {"scene": "turn_on", "script": "turn_on"})

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    @staticmethod
    def _resumir(aparato):
        datos = {"nombre": aparato["nombre"], "estado": aparato["estado"]}

        if aparato["habitacion"]:
            datos["habitacion"] = aparato["habitacion"]

        atributos = aparato["atributos"]

        if aparato["dominio"] == "light" and aparato["estado"] == "on" and atributos.get("brightness") is not None:
            datos["brillo_pct"] = round(atributos["brightness"] * 100 / 255)

        if aparato["dominio"] == "cover" and atributos.get("current_position") is not None:
            datos["posicion_pct"] = atributos["current_position"]

        if aparato["dominio"] == "climate":
            for clave, nombre in (("current_temperature", "temperatura_actual"), ("temperature", "objetivo")):
                if atributos.get(clave) is not None:
                    datos[nombre] = atributos[clave]

        if aparato["dominio"] in ("sensor", "binary_sensor") and atributos.get("unit_of_measurement"):
            datos["unidad"] = atributos["unit_of_measurement"]

        return datos

    def listar(self, tipo="", habitacion="", limite=40):
        """Aparatos de la casa, opcionalmente filtrados por tipo y habitación."""

        dominios = set()

        if tipo:
            dominios, _, _ = self._analizar(tipo)

            if not dominios and normalizar(tipo) in ("sensor", "sensores", "temperatura", "humedad"):
                dominios = {"sensor", "binary_sensor"}

        catalogo = self._cargar_catalogo()

        if dominios:
            catalogo = [a for a in catalogo if a["dominio"] in dominios]
        else:
            catalogo = [a for a in catalogo if a["dominio"] in CONTROLABLES]

        if habitacion:
            claves = {_raiz(p) for p in _palabras(habitacion)} - RELLENO
            catalogo = [a for a in catalogo if claves <= (a["_palabras_area"] | a["_palabras_nombre"])]

        catalogo = sorted(catalogo, key=lambda a: (a["habitacion"], a["nombre"]))

        resultado = {"total": len(catalogo), "aparatos": [self._resumir(a) for a in catalogo[:limite]]}

        if len(catalogo) > limite:
            resultado["aviso"] = "Hay más; filtra por tipo o habitación para ver el resto."

        return resultado

    def estado_de(self, texto):
        try:
            aparatos, _ = self.buscar(texto, None, incluir_lectura=True)
        except HomeAssistantError as e:
            return {"error": str(e)}

        if not aparatos:
            return {"error": f"No encuentro ningún aparato que encaje con '{texto}'."}

        return {"aparatos": [self._resumir(a) for a in aparatos[:10]]}
