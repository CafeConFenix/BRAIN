import http.client
import io
import json
import threading
import unittest
import wave
from http.server import ThreadingHTTPServer

from brain.integrations.home_assistant import guardar_configuracion
from brain.utils.listas import interpretar_lista, parece_lista_pegada
from brain.web import servidor
from brain.web.servidor import crear_manejador
from brain.voice.reconocimiento import VozError, wav_a_audio
from tests.helpers import CasoBrain, HomeAssistantFalso, llamada, texto

LISTA_DESPENSA = """- Café latte macchiato 250 ml: 2 unidades
- Bebida energética candy zero 500 ml: 2 unidades
- Filetes de contramuslo de pollo 600 g aprox.: 2 unidades
- Cogollos 3 unidades: 3 unids
- Tomate triturado 400 g: 4 unidades
- Leche desnatada pack 6 x 1 L: 1 unidad"""


class CasoWeb(CasoBrain):
    """Servidor web de BRAIN con Ollama falso y Home Assistant falso."""

    def setUp(self):
        super().setUp()

        self.ha = HomeAssistantFalso()
        self.ha.iniciar()

        self.servidor = ThreadingHTTPServer(("127.0.0.1", 0), crear_manejador(self.brain))
        self.servidor.daemon_threads = True
        self.puerto = self.servidor.server_address[1]

        threading.Thread(target=lambda: self.servidor.serve_forever(poll_interval=0.02), daemon=True).start()

        self.inventario = self.brain.modules.obtener("inventario")
        self.compras = self.brain.modules.obtener("compras")

    def tearDown(self):
        self.servidor.shutdown()
        self.servidor.server_close()
        self.ha.parar()

        super().tearDown()

    def conectar_casa(self):
        guardar_configuracion(self.ha.url, HomeAssistantFalso.TOKEN)
        self.brain.modules.obtener("domotica").olvidar_catalogo()

    def api(self, metodo, ruta, cuerpo=None, tipo="application/json", bruto=None):
        conexion = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)

        datos = bruto if bruto is not None else (json.dumps(cuerpo) if cuerpo is not None else None)

        conexion.request(metodo, ruta, body=datos, headers={"Content-Type": tipo} if metodo == "POST" else {})

        respuesta = conexion.getresponse()
        contenido = respuesta.read()
        conexion.close()

        return respuesta.status, json.loads(contenido.decode("utf-8")) if contenido else {}


class TestListasPegadas(CasoBrain):
    def test_reconoce_el_formato_de_la_despensa(self):
        self.assertTrue(parece_lista_pegada(LISTA_DESPENSA))

        r = interpretar_lista(LISTA_DESPENSA)
        nombres = dict(r["productos"])

        self.assertEqual(r["destino"], "despensa")
        self.assertEqual(nombres["Café latte macchiato 250 ml"], 2)
        self.assertEqual(nombres["Filetes de contramuslo de pollo 600 g"], 2)
        self.assertEqual(nombres["Cogollos 3 unidades"], 3)
        self.assertEqual(nombres["Leche desnatada pack 6 x 1 L"], 1)

    def test_no_confunde_ordenes_normales_con_listas(self):
        for frase in ("apunta leche, pan y huevos", "¿qué tengo en la despensa?", "elimina toda la lista de la compra"):
            self.assertFalse(parece_lista_pegada(frase), frase)

    def test_el_titulo_no_es_un_producto(self):
        r = interpretar_lista("Añade esto a mi despensa\n" + LISTA_DESPENSA)

        self.assertEqual(r["titulo"], "Añade esto a mi despensa")
        self.assertEqual(len(r["productos"]), 6)

    def test_va_a_la_compra_solo_si_se_dice(self):
        self.assertEqual(interpretar_lista("Lista de la compra:\n" + LISTA_DESPENSA)["destino"], "compra")
        self.assertEqual(interpretar_lista("Para la nevera\n" + LISTA_DESPENSA)["destino"], "frigorifico")

    def test_el_chat_guarda_la_lista_en_la_despensa_sin_la_ia(self):
        respuesta = self.brain.conversacion.preguntar(LISTA_DESPENSA)

        self.assertIn("6 productos", respuesta)
        self.assertEqual(self.ollama.peticiones, [])  # no se llamó al modelo
        self.assertEqual(len(self.brain.modules.obtener("inventario").listar("despensa")["despensa"]), 6)
        self.assertEqual(self.brain.modules.obtener("compras").lista(), [])

    def test_el_chat_la_manda_a_la_compra_si_el_usuario_lo_pide(self):
        self.brain.conversacion.preguntar("Añade esto a la lista de la compra\n" + LISTA_DESPENSA)

        self.assertEqual(len(self.brain.modules.obtener("compras").lista()), 6)
        self.assertEqual(self.brain.modules.obtener("inventario").listar("despensa")["despensa"], [])

    def test_el_historial_recorta_los_mensajes_largos(self):
        largo = "\n".join(f"- Producto {i} 500 g: 1 unidad" for i in range(200))

        self.brain.conversacion.preguntar(largo)

        guardado = self.brain.conversacion.mensajes()[0]["content"]
        self.assertLess(len(guardado), 1300)
        self.assertIn("recortado", guardado)


class TestBorrado(CasoBrain):
    def ejecutar(self, herramienta, **argumentos):
        return self.brain.tools.ejecutar(herramienta, argumentos)

    def test_vaciar_la_lista_de_la_compra(self):
        self.ejecutar("anadir_varias_a_compra", productos="leche\npan\nhuevos")

        self.assertEqual(self.ejecutar("vaciar_lista_compra")["borrados"], 3)
        self.assertEqual(self.brain.modules.obtener("compras").lista(), [])

    def test_quitar_un_producto_de_la_compra(self):
        self.ejecutar("anadir_varias_a_compra", productos="leche\npan")

        self.ejecutar("quitar_de_compra", producto="leche")

        self.assertEqual([i["producto"] for i in self.brain.modules.obtener("compras").lista()], ["pan"])

    def test_borrar_y_vaciar_inventario(self):
        self.ejecutar("anadir_varios_inventario", productos="Leche entera, 6\nPan, 2\nSal")

        self.assertEqual(len(self.ejecutar("borrar_del_inventario", nombre="leche")["borrados"]), 1)
        self.assertEqual(self.ejecutar("vaciar_inventario")["borrados"], 2)

    def test_la_ia_vacia_la_compra_cuando_se_lo_piden(self):
        self.ejecutar("anadir_varias_a_compra", productos="leche\npan")
        self.ollama.respuestas = [llamada("vaciar_lista_compra"), texto("Listo, la lista de la compra está vacía.")]

        respuesta = self.brain.conversacion.preguntar("elimina toda la lista de la compra")

        self.assertIn("vacía", respuesta)
        self.assertEqual(self.brain.modules.obtener("compras").lista(), [])

    def test_respuesta_vacia_se_reintenta(self):
        self.ollama.respuestas = [texto(""), texto("Aquí estoy.")]

        self.assertEqual(self.brain.conversacion.preguntar("hola"), "Aquí estoy.")
        self.assertEqual(len(self.ollama.peticiones), 2)

    def test_dos_respuestas_vacias_dan_un_mensaje_util(self):
        self.ollama.respuestas = [texto(""), texto("")]

        respuesta = self.brain.conversacion.preguntar("hola")

        self.assertIn("No he sabido qué hacer", respuesta)


class TestRecetas(CasoBrain):
    def ejecutar(self, herramienta, **argumentos):
        return self.brain.tools.ejecutar(herramienta, argumentos)

    def test_ingredientes_incluyen_despensa_y_basicos(self):
        self.ejecutar("anadir_inventario", nombre="Huevos", cantidad=6, ubicacion="frigorifico")
        self.ejecutar("anadir_inventario", nombre="Arroz", cantidad=2)

        r = self.ejecutar("ingredientes_disponibles")

        self.assertTrue(any("Huevos" in i for i in r["inventario"]))
        self.assertTrue(any("Arroz" in i for i in r["inventario"]))
        for basico in ("aceite de oliva", "sal", "azúcar", "harina", "agua", "pimienta"):
            self.assertIn(basico, r["basicos"])

    def test_los_basicos_se_pueden_editar(self):
        self.ejecutar("anadir_basico", nombre="vino blanco")
        self.ejecutar("quitar_basico", nombre="canela")

        basicos = self.ejecutar("ver_basicos")["basicos"]

        self.assertIn("vino blanco", basicos)
        self.assertNotIn("canela", basicos)

    def test_el_inventario_normal_no_se_ve_afectado_por_los_basicos(self):
        self.ejecutar("anadir_basico", nombre="vino blanco")
        self.ejecutar("anadir_inventario", nombre="Leche", cantidad=2)

        self.assertEqual(self.ejecutar("ver_inventario")["despensa"], ["Leche (x2)"])

    def test_la_ia_consulta_los_ingredientes_antes_de_proponer(self):
        self.ejecutar("anadir_inventario", nombre="Arroz", cantidad=2)
        self.ollama.respuestas = [llamada("ingredientes_disponibles"), texto("Puedes hacer arroz blanco con aceite y sal.")]

        respuesta = self.brain.conversacion.preguntar("dame una receta")

        self.assertIn("arroz", respuesta.lower())
        self.assertEqual(self.brain.ai.herramientas_usadas[0]["nombre"], "ingredientes_disponibles")
        # La IA recibió el resultado real, con los básicos incluidos.
        pedido_final = json.dumps(self.ollama.peticiones[-1]["messages"], ensure_ascii=False)
        self.assertIn("aceite de oliva", pedido_final)


class TestWebDatos(CasoWeb):
    def test_importar_con_vista_previa_y_confirmacion(self):
        codigo, r = self.api("POST", "/api/importar", {"texto": LISTA_DESPENSA, "destino": "despensa", "solo_vista_previa": True})

        self.assertEqual((codigo, r["total"]), (200, 6))
        self.assertEqual(self.inventario.listar("despensa")["despensa"], [])  # solo era una vista previa

        codigo, r = self.api("POST", "/api/importar", {"texto": LISTA_DESPENSA, "destino": "despensa"})

        self.assertEqual(codigo, 200)
        self.assertEqual(len(self.inventario.listar("despensa")["despensa"]), 6)

    def test_importar_a_la_compra_y_texto_vacio(self):
        self.api("POST", "/api/importar", {"texto": LISTA_DESPENSA, "destino": "compra"})

        self.assertEqual(len(self.compras.lista()), 6)
        self.assertEqual(self.api("POST", "/api/importar", {"texto": "   \n  "})[0], 400)

    def test_borrar_desde_la_web(self):
        self.api("POST", "/api/importar", {"texto": LISTA_DESPENSA, "destino": "compra"})

        self.api("POST", "/api/compra/quitar", {"producto": "Tomate triturado 400 g"})
        self.assertEqual(len(self.compras.lista()), 5)

        self.assertEqual(self.api("POST", "/api/compra/vaciar", {})[1]["borrados"], 5)
        self.assertEqual(self.compras.lista(), [])

        self.api("POST", "/api/importar", {"texto": LISTA_DESPENSA, "destino": "despensa"})
        self.api("POST", "/api/inventario/borrar", {"nombre": "cogollos"})
        self.assertEqual(len(self.inventario.listar("despensa")["despensa"]), 5)

        self.api("POST", "/api/inventario/vaciar", {})
        self.assertEqual(self.inventario.listar("despensa")["despensa"], [])

    def test_borrar_algo_que_no_existe_da_404(self):
        self.assertEqual(self.api("POST", "/api/compra/quitar", {"producto": "unicornio"})[0], 404)

    def test_el_resumen_trae_los_basicos(self):
        codigo, r = self.api("GET", "/api/resumen")

        self.assertIn("aceite de oliva", r["basicos"])


class TestWebDomotica(CasoWeb):
    def test_sin_conectar_lo_dice(self):
        codigo, r = self.api("GET", "/api/dispositivos")

        self.assertEqual(codigo, 200)
        self.assertFalse(r["conectado"])

    def test_lista_dispositivos_por_habitacion_con_estado(self):
        self.conectar_casa()

        codigo, r = self.api("GET", "/api/dispositivos")

        habitaciones = {g["habitacion"]: g["dispositivos"] for g in r["grupos"]}

        self.assertTrue(r["conectado"])
        self.assertIn("Salón", habitaciones)
        luz = [d for d in habitaciones["Salón"] if d["nombre"] == "Luz salón"][0]
        self.assertTrue(luz["encendido"])
        self.assertEqual(luz["tipo"], "light")
        self.assertEqual([e["nombre"] for e in r["escenas"]], ["Noche"])

    def test_no_muestra_cerraduras_ni_garajes(self):
        self.conectar_casa()

        entidades = {d["entidad"] for g in self.api("GET", "/api/dispositivos")[1]["grupos"] for d in g["dispositivos"]}

        self.assertNotIn("lock.entrada", entidades)
        self.assertNotIn("cover.garaje", entidades)

    def test_interruptor_enciende_y_apaga(self):
        self.conectar_casa()

        codigo, r = self.api("POST", "/api/dispositivo", {"entidad": "light.cocina", "encendido": True})

        self.assertEqual((codigo, r["encendido"]), (200, True))
        self.assertEqual(self.ha.llamadas[-1], ("light", "turn_on", {"entity_id": "light.cocina"}))

        self.api("POST", "/api/dispositivo", {"entidad": "light.salon_techo", "encendido": False})
        self.assertEqual(self.ha.llamadas[-1][:2], ("light", "turn_off"))

    def test_persiana_se_abre_y_se_cierra(self):
        self.conectar_casa()

        self.api("POST", "/api/dispositivo", {"entidad": "cover.persiana_dormitorio", "encendido": False})

        self.assertEqual(self.ha.llamadas[-1][:2], ("cover", "close_cover"))

    def test_no_se_puede_controlar_lo_peligroso_ni_lo_inventado(self):
        self.conectar_casa()

        for entidad in ("lock.entrada", "cover.garaje", "alarm_control_panel.casa", "light.no_existe"):
            codigo, r = self.api("POST", "/api/dispositivo", {"entidad": entidad, "encendido": True})

            self.assertEqual(codigo, 502, entidad)

        self.assertEqual(self.ha.llamadas, [])

    def test_escena(self):
        self.conectar_casa()

        self.api("POST", "/api/escena", {"entidad": "scene.noche"})

        self.assertEqual(self.ha.llamadas[-1][:2], ("scene", "turn_on"))
        self.assertEqual(self.api("POST", "/api/escena", {"entidad": "light.cocina"})[0], 502)

    def test_home_assistant_apagado_no_rompe_la_web(self):
        self.conectar_casa()
        self.ha.parar()

        codigo, r = self.api("GET", "/api/dispositivos")

        self.assertEqual(codigo, 200)
        self.assertIn("error", r)

        self.ha = HomeAssistantFalso()  # para que tearDown pueda parar algo
        self.ha.iniciar()


def crear_wav(segundos=1.0, frecuencia=16000, canales=1, amplitud=8000):
    import math
    import struct

    tramas = int(segundos * frecuencia)
    datos = b"".join(
        struct.pack("<h", int(amplitud * math.sin(2 * math.pi * 440 * i / frecuencia))) * canales for i in range(tramas)
    )

    buffer = io.BytesIO()

    with wave.open(buffer, "wb") as w:
        w.setnchannels(canales)
        w.setsampwidth(2)
        w.setframerate(frecuencia)
        w.writeframes(datos)

    return buffer.getvalue()


class ReconocedorFalso:
    def __init__(self, disponible=True):
        self._disponible = disponible
        self.instalaciones = 0
        self.audios = []

    def disponible(self):
        return self._disponible

    def estado(self):
        return {"disponible": self._disponible, "instalando": False, "paso": "", "error": "", "modelo": "small"}

    def instalar(self):
        self.instalaciones += 1

        return True

    def transcribir(self, contenido):
        if not self._disponible:
            raise VozError("El reconocimiento de voz no está instalado. Pulsa «Instalar voz».")

        self.audios.append(contenido)

        return "enciende la luz del salón"


class TestVoz(CasoWeb):
    def setUp(self):
        super().setUp()

        self.original = servidor.reconocedor
        servidor.reconocedor = ReconocedorFalso()

    def tearDown(self):
        servidor.reconocedor = self.original

        super().tearDown()

    def test_estado_de_la_voz(self):
        codigo, r = self.api("GET", "/api/voz")

        self.assertTrue(r["disponible"])

    def test_transcribe_el_audio_recibido(self):
        wav = crear_wav()

        codigo, r = self.api("POST", "/api/voz", tipo="audio/wav", bruto=wav)

        self.assertEqual((codigo, r["texto"]), (200, "enciende la luz del salón"))
        self.assertEqual(servidor.reconocedor.audios, [wav])

    def test_sin_instalar_pide_instalar(self):
        servidor.reconocedor = ReconocedorFalso(disponible=False)

        codigo, r = self.api("POST", "/api/voz", tipo="audio/wav", bruto=crear_wav())

        self.assertEqual(codigo, 503)
        self.assertIn("Instalar voz", r["error"])

        self.api("POST", "/api/voz/instalar", {})
        self.assertEqual(servidor.reconocedor.instalaciones, 1)

    def test_rechaza_lo_que_no_es_audio(self):
        self.assertEqual(self.api("POST", "/api/voz", {"a": 1})[0], 400)
        self.assertEqual(self.api("POST", "/api/voz", tipo="audio/wav", bruto=b"")[0], 400)

    def test_otra_web_no_puede_usar_el_microfono(self):
        conexion = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        conexion.request("POST", "/api/voz", body=crear_wav(), headers={"Content-Type": "audio/wav", "Origin": "http://malo.example"})

        self.assertEqual(conexion.getresponse().status, 403)


@unittest.skipUnless(__import__("importlib").util.find_spec("numpy"), "necesita numpy")
class TestAudio(unittest.TestCase):
    def test_wav_a_audio(self):
        audio = wav_a_audio(crear_wav(1.0))

        self.assertEqual(len(audio), 16000)
        self.assertEqual(str(audio.dtype), "float32")
        self.assertLessEqual(float(abs(audio).max()), 1.0)

    def test_remuestrea_y_mezcla_a_mono(self):
        audio = wav_a_audio(crear_wav(1.0, frecuencia=48000, canales=2))

        self.assertEqual(len(audio), 16000)

    def test_rechaza_audio_roto_o_demasiado_largo(self):
        with self.assertRaises(VozError):
            wav_a_audio(b"esto no es un wav")

        with self.assertRaises(VozError):
            wav_a_audio(crear_wav(61.0, frecuencia=8000))
