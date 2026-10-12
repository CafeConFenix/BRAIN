import json
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from brain.ai.ollama import OllamaError, buscar_ejecutable
from brain.ai.vision import MAX_BYTES as MAX_IMAGEN
from brain.ai.vision import VisionError, guardar_lectura, leer_bascula
from brain.core import logger
from brain.core.config import Config
from brain.core.hardware import alternativas, guardar_modelo, recomendar_modelo
from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.sistema import CopiaError
from brain.utils.listas import DESTINOS, aplicar_lista, interpretar_lista
from brain.voice.reconocimiento import Reconocedor, VozError

ESTATICOS = Path(__file__).resolve().parent / "static"

MAX_MENSAJE = 4000
MAX_CUERPO = 64 * 1024
MAX_AUDIO = 4 * 1024 * 1024

# Reconocimiento de voz local (el micrófono de la web).
reconocedor = Reconocedor()


def leer_energia():
    """Producción, consumo y red en directo (la lectura nunca rompe la web)."""

    from brain.tools.builtin.energia import tiempo_real

    try:
        return tiempo_real.leer()
    except Exception as error:
        logger.error(f"Energía en directo: {error!r}")

        return {"configurado": True, "error": f"No he podido leer el inversor: {error}"}


def construir_sistema(brain):
    """Copias de seguridad, tareas en segundo plano y alertas de Home Assistant."""

    from brain.core.scheduler import planificador, sondeo

    sistema = brain.modules.obtener("sistema")

    return {
        "copias": sistema.listar_copias() if sistema else [],
        "tareas": planificador.estado(),
        "planificador_activo": planificador.activo,
        "alertas": sondeo.alertas,
    }


def construir_avisos(brain, despues=0):
    """Avisos recientes y cómo entregarlos en la web (sin duplicar el sonido de Windows)."""

    from brain.core import notificador

    avisos = brain.modules.obtener("avisos")

    if avisos is None:
        return {"avisos": [], "no_leidos": 0, "ultimo_id": 0}

    config = avisos.configuracion()
    entrega_nativa = config["nativo"] and notificador.ES_WINDOWS
    molestar = not avisos.en_no_molestar()

    lista = avisos.listar(despues_de=despues, limite=30)

    for aviso in lista:
        aviso["sonar_web"] = (not config["silencio"]) and (not entrega_nativa) and (aviso["nivel"] == "critico" or molestar)

    todos = avisos.listar(solo_no_leidos=True, limite=500)

    return {
        "avisos": lista,
        "no_leidos": len(todos),
        "ultimo_id": lista[-1]["id"] if lista else despues,
        "silencio": config["silencio"],
    }


def construir_resumen(brain):
    """Datos para el panel lateral de la interfaz."""

    salud = brain.modules.obtener("salud")
    compras = brain.modules.obtener("compras")
    calendario = brain.modules.obtener("calendario")
    energia = brain.modules.obtener("energia")
    inventario = brain.modules.obtener("inventario")
    memoria = brain.modules.obtener("memoria")

    productos = sum(len(v) for v in inventario.listar().values()) if inventario else 0
    recuerdos = sum(len(v) for v in memoria.consultar().values()) if memoria else 0

    return {
        "peso": salud.historial_peso(30) if salud else [],
        "compra": compras.lista() if compras else [],
        "agenda": calendario.agenda(14) if calendario else {},
        "solar": energia.produccion(14) if energia else {},
        "despensa": inventario.todo() if inventario else [],
        "basicos": inventario.basicos() if inventario else [],
        "productos_inventario": productos,
        "recuerdos": recuerdos,
    }


_reparador = {"hilo": None, "ultimo": 0.0}
_cerrojo_reparador = threading.Lock()

# Segundos que se espera entre un intento de arrancar Ollama y el siguiente.
ESPERA_ENTRE_INTENTOS = 20


def _arrancar_ollama(ollama):
    """Intenta arrancar Ollama (puede tardar un minuto la primera vez)."""

    try:
        ollama.iniciar_servidor(espera=90)
    except Exception as error:
        logger.error(f"No se pudo arrancar Ollama: {error!r}")


def lanzar_reparacion(brain, forzar=False):
    """
    Arranca Ollama en segundo plano sin bloquear la interfaz.

    Se vuelve a intentar cada pocos segundos mientras siga apagado, porque
    la primera vez que se abre tras instalarlo puede tardar bastante.
    Devuelve True si hay un intento en marcha.
    """

    with _cerrojo_reparador:
        hilo = _reparador["hilo"]

        if hilo is not None and hilo.is_alive():
            return True

        if not forzar and time.time() - _reparador["ultimo"] < ESPERA_ENTRE_INTENTOS:
            return False

        _reparador["ultimo"] = time.time()

        hilo = threading.Thread(target=_arrancar_ollama, args=(brain.ai.ollama,), daemon=True)
        _reparador["hilo"] = hilo
        hilo.start()

        return True


_descarga = {"activa": False, "modelo": "", "porcentaje": 0, "estado": "", "error": ""}
_cache_recomendado = {}


def _recomendado():
    """Modelo ideal para este equipo (se mide una sola vez)."""

    if not _cache_recomendado:
        try:
            r = recomendar_modelo()
            _cache_recomendado.update({"etiqueta": r["etiqueta"], "descarga_gb": r["descarga_gb"]})
        except Exception as error:
            logger.error(f"No se pudo medir el equipo: {error!r}")
            _cache_recomendado.update({"etiqueta": Config.MODELO_POR_DEFECTO, "descarga_gb": 2.5})

    return _cache_recomendado


def _descargar(brain, etiqueta):
    def progreso(estado, completado, total):
        _descarga["estado"] = estado

        if total:
            _descarga["porcentaje"] = int(completado * 100 / total)

    try:
        candidatos = [etiqueta] + alternativas(etiqueta)

        for candidato in candidatos:
            _descarga.update({"modelo": candidato, "porcentaje": 0, "estado": "Empezando...", "error": ""})

            try:
                if brain.ai.ollama.descargar_modelo(candidato, progreso=progreso):
                    guardar_modelo(candidato)
                    logger.sistema(f"Modelo {candidato} descargado desde la interfaz web")

                    return

            except OllamaError as error:
                _descarga["error"] = str(error)
                logger.error(f"Descarga de {candidato}: {error}")

        if not _descarga["error"]:
            _descarga["error"] = "No se pudo descargar el modelo."
    finally:
        _descarga["activa"] = False


def lanzar_descarga(brain):
    """Descarga el modelo recomendado en segundo plano. True si hay descarga en marcha."""

    with _cerrojo_reparador:
        if _descarga["activa"]:
            return True

        _descarga.update({"activa": True, "porcentaje": 0, "estado": "Empezando...", "error": ""})

    threading.Thread(target=_descargar, args=(brain, _recomendado()["etiqueta"]), daemon=True).start()

    return True


def construir_estado(brain):
    """Estado de la IA para mostrarlo arriba en la interfaz."""

    ollama = brain.ai.ollama

    estado = {
        "version": Config.VERSION,
        "ia_lista": False,
        "modelo": None,
        "mensaje": "",
        "arrancando": False,
        "sin_modelos": False,
        "recomendado": None,
        "descarga": dict(_descarga),
    }

    try:
        modelos = [m for m in ollama.modelos() if "embed" not in m.lower()]

        if not modelos:
            recomendado = _recomendado()

            estado["sin_modelos"] = True
            estado["recomendado"] = recomendado
            estado["mensaje"] = (
                f"Ollama funciona (en {ollama.url}) pero no tiene ningún modelo de IA. "
                f"Pulsa el botón para descargar el recomendado para tu PC ({recomendado['etiqueta']}, "
                f"unos {recomendado['descarga_gb']:g} GB)."
            )
        else:
            estado["modelo"] = ollama.resolver_modelo()
            estado["ia_lista"] = True

    except OllamaError as error:
        estado["mensaje"] = str(error)

        if buscar_ejecutable():
            # Ollama está instalado pero apagado o arrancando: se intenta
            # levantarlo en segundo plano y la página volverá a preguntar.
            estado["arrancando"] = lanzar_reparacion(brain)

            if estado["arrancando"]:
                estado["mensaje"] = "Arrancando la IA (Ollama)... puede tardar hasta un minuto la primera vez."
        else:
            estado["mensaje"] = (
                "No encuentro Ollama en este equipo. Ejecuta INSTALAR.bat "
                "(o instálalo desde https://ollama.com/download)."
            )

    return estado


def leer_dispositivos(brain):
    """Dispositivos de domótica para el panel (nunca rompe la web)."""

    domotica = brain.modules.obtener("domotica")

    if domotica is None or not domotica.conectado():
        return {"conectado": False, "grupos": [], "escenas": [], "total": 0}

    try:
        return {"conectado": True, **domotica.panel()}
    except HomeAssistantError as error:
        return {"conectado": True, "error": str(error), "grupos": [], "escenas": [], "total": 0}
    except Exception as error:
        logger.error(f"Panel de domótica: {error!r}")

        return {"conectado": True, "error": f"No he podido leer los dispositivos: {error}", "grupos": [], "escenas": [], "total": 0}


def _importar(brain, datos):
    """Importa (o previsualiza) una lista pegada. Devuelve (código, respuesta)."""

    texto = str(datos.get("texto", ""))
    destino = str(datos.get("destino", "auto")).strip().lower()

    if destino not in DESTINOS:
        destino = None  # "auto": se deduce del texto

    interpretada = interpretar_lista(texto, destino)

    if not interpretada or not interpretada["productos"]:
        return 400, {"error": "No he encontrado ningún producto en el texto. Escribe uno por línea, por ejemplo: Leche, 2 unidades."}

    respuesta = {
        "destino": interpretada["destino"],
        "total": len(interpretada["productos"]),
        "productos": [{"nombre": n, "cantidad": c} for n, c in interpretada["productos"]],
    }

    if datos.get("solo_vista_previa"):
        return 200, respuesta

    inventario = brain.modules.obtener("inventario")
    compras = brain.modules.obtener("compras")

    resultado = aplicar_lista(interpretada, inventario, compras)

    return 200, {**respuesta, "texto": resultado["texto"]}


def _accion_datos(brain, ruta, datos):
    """Acciones de la interfaz sobre compra, inventario y domótica. Devuelve (código, respuesta)."""

    compras = brain.modules.obtener("compras")
    inventario = brain.modules.obtener("inventario")
    domotica = brain.modules.obtener("domotica")

    try:
        if ruta == "/api/importar":
            return _importar(brain, datos)

        if ruta == "/api/compra/quitar":
            return 200, {"quitados": [i["producto"] for i in compras.quitar(str(datos.get("producto", "")))]}

        if ruta == "/api/compra/vaciar":
            return 200, {"borrados": compras.vaciar()}

        if ruta == "/api/inventario/borrar":
            borrados = inventario.borrar(str(datos.get("nombre", "")), datos.get("ubicacion") or None)

            return 200, {"borrados": [p["nombre"] for p in borrados]}

        if ruta == "/api/inventario/vaciar":
            return 200, {"borrados": inventario.vaciar(datos.get("ubicacion") or None)}

        if ruta == "/api/avisos/leer":
            return 200, {"marcados": brain.modules.obtener("avisos").marcar_leidos(datos.get("ids") or None)}

        if ruta == "/api/copia/crear":
            return 200, {"copia": brain.modules.obtener("sistema").crear_copia()}

        if ruta == "/api/copia/restaurar":
            if not datos.get("nombre"):
                return 400, {"error": "Elige qué copia restaurar."}

            return 200, {"restaurado": brain.modules.obtener("sistema").restaurar_copia(str(datos["nombre"]))}

        if ruta == "/api/dispositivo":
            if "encendido" not in datos:
                return 400, {"error": "Falta indicar si hay que encender o apagar."}

            return 200, domotica.conmutar(datos.get("entidad", ""), bool(datos["encendido"]))

        if ruta == "/api/escena":
            return 200, domotica.lanzar_escena(datos.get("entidad", ""))

    except HomeAssistantError as error:
        return 502, {"error": str(error)}

    except CopiaError as error:
        return 400, {"error": str(error)}

    except ValueError as error:
        return 404, {"error": str(error)}

    return 404, {"error": "No encontrado."}


RUTAS_DATOS = (
    "/api/avisos/leer",
    "/api/copia/crear",
    "/api/copia/restaurar",
    "/api/importar",
    "/api/compra/quitar",
    "/api/compra/vaciar",
    "/api/inventario/borrar",
    "/api/inventario/vaciar",
    "/api/dispositivo",
    "/api/escena",
)


def crear_manejador(brain):
    bloqueo_chat = threading.Lock()

    class Manejador(BaseHTTPRequestHandler):
        server_version = "BRAIN"
        protocol_version = "HTTP/1.1"

        # ----------------------------------------------------------
        # Utilidades
        # ----------------------------------------------------------

        def log_message(self, formato, *args):
            # Se silencia el registro de cada petición en la consola.
            pass

        def _hosts_permitidos(self):
            puerto = self.server.server_address[1]

            return {f"127.0.0.1:{puerto}", f"localhost:{puerto}"}

        def _origen_valido(self):
            """
            Protege BRAIN de páginas web externas: solo se aceptan
            peticiones dirigidas a localhost y que vengan de la propia
            interfaz de BRAIN.
            """

            if self.headers.get("Host", "") not in self._hosts_permitidos():
                return False

            origen = self.headers.get("Origin")

            if origen is not None:
                return urlparse(origen).netloc in self._hosts_permitidos()

            return True

        def _enviar(self, codigo, cuerpo, tipo="application/json; charset=utf-8"):
            if not isinstance(cuerpo, bytes):
                cuerpo = json.dumps(cuerpo, ensure_ascii=False, default=str).encode("utf-8")

            self.send_response(codigo)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(cuerpo)))
            self.send_header("Cache-Control", "no-store")
            # Sin conexiones persistentes: así un cuerpo de petición sin leer
            # (por ejemplo, una petición rechazada) nunca se confunde con la
            # siguiente petición.
            self.send_header("Connection", "close")
            self.close_connection = True
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(cuerpo)

        def _leer_json(self):
            try:
                longitud = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                longitud = 0

            if longitud <= 0 or longitud > MAX_CUERPO:
                return None

            try:
                datos = json.loads(self.rfile.read(longitud).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None

            return datos if isinstance(datos, dict) else None

        def _imagen(self):
            """Recibe una captura de la báscula, la lee con un modelo de visión y guarda el peso."""

            try:
                longitud = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                longitud = 0

            if not self.headers.get("Content-Type", "").startswith("image/") or longitud <= 0 or longitud > MAX_IMAGEN:
                return self._enviar(400, {"error": "Imagen no válida (JPG, PNG o WebP, máximo 8 MB)."})

            contenido = self.rfile.read(longitud)
            id_conversacion = parse_qs(urlparse(self.path).query).get("conversacion", ["general"])[0]

            try:
                conversacion = brain.conversaciones.obtener(id_conversacion)
            except KeyError:
                return self._enviar(404, {"error": "Esa conversación no existe."})

            salud = brain.modules.obtener("salud")

            with bloqueo_chat:
                try:
                    lectura = leer_bascula(brain.ai.ollama, contenido)
                    texto = guardar_lectura(salud, lectura)

                except VisionError as error:
                    return self._enviar(422, {"error": str(error)})

                except ValueError as error:
                    return self._enviar(422, {"error": str(error)})

                except Exception as error:
                    logger.error(f"Imagen: {error!r}")

                    return self._enviar(500, {"error": f"No he podido analizar la imagen: {error}"})

                conversacion.registrar_intercambio("📷 Captura de la báscula", texto)

            return self._enviar(200, {"respuesta": texto, "peso": lectura["peso"], "fecha": lectura["fecha"], "medidas": lectura["medidas"]})

        def _voz(self):
            """Recibe un audio WAV del micrófono y devuelve el texto."""

            try:
                longitud = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                longitud = 0

            if "audio" not in self.headers.get("Content-Type", "") or longitud <= 0 or longitud > MAX_AUDIO:
                return self._enviar(400, {"error": "Audio no válido."})

            contenido = self.rfile.read(longitud)

            try:
                return self._enviar(200, {"texto": reconocedor.transcribir(contenido)})

            except VozError as error:
                return self._enviar(503 if not reconocedor.disponible() else 400, {"error": str(error)})

            except Exception as error:
                logger.error(f"Voz: {error!r}")

                return self._enviar(500, {"error": f"No he podido transcribir el audio: {error}"})

        # ----------------------------------------------------------
        # GET
        # ----------------------------------------------------------

        def do_GET(self):
            if not self._origen_valido():
                return self._enviar(403, {"error": "Acceso no permitido."})

            ruta = urlparse(self.path).path

            if ruta in ("/", "/index.html"):
                try:
                    contenido = (ESTATICOS / "index.html").read_bytes()
                except OSError:
                    return self._enviar(404, {"error": "Falta la interfaz web."})

                return self._enviar(200, contenido, "text/html; charset=utf-8")

            if ruta == "/api/estado":
                return self._enviar(200, construir_estado(brain))

            if ruta == "/api/resumen":
                return self._enviar(200, construir_resumen(brain))

            if ruta == "/api/energia":
                return self._enviar(200, leer_energia())

            if ruta == "/api/sistema":
                return self._enviar(200, construir_sistema(brain))

            if ruta == "/api/dispositivos":
                return self._enviar(200, leer_dispositivos(brain))

            if ruta == "/api/voz":
                return self._enviar(200, reconocedor.estado())

            if ruta == "/api/avisos":
                try:
                    despues = int(parse_qs(urlparse(self.path).query).get("despues", ["0"])[0])
                except ValueError:
                    despues = 0

                return self._enviar(200, construir_avisos(brain, despues))

            if ruta.startswith("/api/sonido/"):
                avisos = brain.modules.obtener("avisos")
                archivo = avisos.ruta_sonido(unquote(ruta[len("/api/sonido/") :])) if avisos else None

                if archivo is None:
                    return self._enviar(404, {"error": "Sonido no encontrado."})

                tipos = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}

                return self._enviar(200, archivo.read_bytes(), tipos.get(archivo.suffix.lower(), "application/octet-stream"))

            if ruta == "/api/conversaciones":
                return self._enviar(200, {"conversaciones": brain.conversaciones.listar()})

            if ruta == "/api/historial":
                id_conversacion = parse_qs(urlparse(self.path).query).get("conversacion", ["general"])[0]

                try:
                    return self._enviar(200, {"mensajes": brain.conversaciones.obtener(id_conversacion).mensajes()})
                except KeyError:
                    return self._enviar(404, {"error": "Esa conversación no existe."})

            if ruta == "/api/herramientas":
                return self._enviar(
                    200,
                    {
                        "herramientas": [
                            {
                                "nombre": h["nombre"],
                                "descripcion": h["descripcion"],
                                "categoria": h["categoria"],
                            }
                            for h in brain.tools.listar()
                        ]
                    },
                )

            return self._enviar(404, {"error": "No encontrado."})

        # ----------------------------------------------------------
        # POST
        # ----------------------------------------------------------

        def do_POST(self):
            if not self._origen_valido():
                return self._enviar(403, {"error": "Acceso no permitido."})

            ruta = urlparse(self.path).path

            if ruta == "/api/voz":
                return self._voz()

            if ruta == "/api/imagen":
                return self._imagen()

            if "application/json" not in self.headers.get("Content-Type", ""):
                return self._enviar(415, {"error": "Se esperaba JSON."})

            if ruta == "/api/reparar":
                lanzar_reparacion(brain, forzar=True)

                return self._enviar(200, construir_estado(brain))

            if ruta == "/api/descargar":
                lanzar_descarga(brain)

                return self._enviar(200, construir_estado(brain))

            if ruta == "/api/voz/instalar":
                reconocedor.instalar()

                return self._enviar(200, reconocedor.estado())

            if ruta in RUTAS_DATOS:
                datos = self._leer_json()

                if datos is None:
                    datos = {}

                codigo, respuesta = _accion_datos(brain, ruta, datos)

                return self._enviar(codigo, respuesta)

            if ruta in ("/api/conversaciones/crear", "/api/conversaciones/renombrar", "/api/conversaciones/borrar"):
                datos = self._leer_json() or {}

                try:
                    if ruta.endswith("/crear"):
                        return self._enviar(200, {"conversacion": brain.conversaciones.crear(datos.get("titulo"), datos.get("instrucciones"))})

                    if ruta.endswith("/renombrar"):
                        return self._enviar(200, {"conversacion": brain.conversaciones.renombrar(str(datos.get("id", "")), datos.get("titulo"))})

                    brain.conversaciones.borrar(str(datos.get("id", "")))

                    return self._enviar(200, {"ok": True})

                except KeyError as error:
                    return self._enviar(404, {"error": str(error.args[0])})

                except ValueError as error:
                    return self._enviar(400, {"error": str(error)})

            if ruta == "/api/limpiar":
                datos = self._leer_json() or {}

                try:
                    brain.conversaciones.obtener(datos.get("conversacion")).limpiar()
                except KeyError:
                    return self._enviar(404, {"error": "Esa conversación no existe."})

                return self._enviar(200, {"ok": True})

            if ruta == "/api/chat":
                datos = self._leer_json()

                mensaje = str((datos or {}).get("mensaje", "")).strip()

                if not mensaje:
                    return self._enviar(400, {"error": "El mensaje está vacío."})

                if len(mensaje) > MAX_MENSAJE:
                    return self._enviar(400, {"error": "El mensaje es demasiado largo."})

                id_conversacion = (datos or {}).get("conversacion") or "general"

                try:
                    brain.conversaciones.obtener(id_conversacion)
                except KeyError:
                    return self._enviar(404, {"error": "Esa conversación no existe."})

                with bloqueo_chat:
                    try:
                        respuesta = brain.conversaciones.preguntar(id_conversacion, mensaje)

                    except OllamaError as error:
                        return self._enviar(503, {"error": str(error)})

                    except Exception as error:
                        logger.error(f"Chat web: {error!r}")

                        return self._enviar(500, {"error": f"Error inesperado: {error}"})

                    usadas = [h["nombre"] for h in brain.ai.herramientas_usadas]

                return self._enviar(200, {"respuesta": respuesta, "herramientas": usadas})

            return self._enviar(404, {"error": "No encontrado."})

    return Manejador


def servir(brain, puerto=None, abrir_navegador=True):
    """Arranca la interfaz web de BRAIN en http://127.0.0.1:<puerto>."""

    puerto = puerto or Config.PUERTO_WEB

    manejador = crear_manejador(brain)

    servidor = None

    # Si el puerto está ocupado se prueba con los siguientes.
    for intento in range(puerto, puerto + 10):
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", intento), manejador)
            puerto = intento
            break
        except OSError:
            continue

    if servidor is None:
        raise OSError(f"No he podido abrir ningún puerto entre {puerto} y {puerto + 9}.")

    servidor.daemon_threads = True

    url = f"http://127.0.0.1:{puerto}"

    print(f"\nBRAIN está funcionando en {url}")
    print("Déjalo abierto mientras lo uses. Para cerrarlo pulsa Ctrl+C o cierra esta ventana.\n")

    logger.sistema(f"Interfaz web iniciada en {url}")

    if abrir_navegador:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()

    try:
        servidor.serve_forever()

    except KeyboardInterrupt:
        print("\nCerrando BRAIN...")

    finally:
        servidor.server_close()

        logger.sistema("Interfaz web cerrada")
