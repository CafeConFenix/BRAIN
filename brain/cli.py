import os
import platform
import re
import subprocess
import sys
import time

from brain.ai.ollama import OllamaError, buscar_ejecutable
from brain.core.config import Config
from brain.core.hardware import alternativas, detectar_hardware, guardar_modelo, recomendar_modelo

AYUDA = """
Comandos:
  /ayuda          muestra esta ayuda
  /herramientas   lista lo que BRAIN sabe hacer
  /modelos        lista los modelos de IA instalados
  /limpiar        borra el historial de la conversación
  /salir          cierra BRAIN
"""


def preparar_ia(brain, interactivo=True):
    """
    Comprueba que Ollama y un modelo están listos y los prepara si puede.

    Devuelve (True, "") si todo está listo, o (False, mensaje) con lo que
    hay que hacer para arreglarlo.
    """

    ollama = brain.ai.ollama

    if not ollama.servidor_activo():
        if buscar_ejecutable() is None:
            return False, (
                "No encuentro Ollama en este equipo. Ejecuta INSTALAR.bat "
                "(o instálalo desde https://ollama.com/download) y vuelve a abrir BRAIN."
            )

        if interactivo:
            print("Iniciando Ollama...")

        if not ollama.iniciar_servidor():
            return False, "No he conseguido arrancar Ollama. Ábrelo desde el menú Inicio y vuelve a intentarlo."

    try:
        modelos = [m for m in ollama.modelos() if "embed" not in m.lower()]
    except OllamaError as error:
        return False, str(error)

    if modelos:
        return True, ""

    modelo = Config.MODELO or recomendar_modelo()["etiqueta"]

    mensaje = f"Ollama no tiene ningún modelo de IA instalado. Descárgalo con: ollama pull {modelo}"

    if not interactivo:
        return False, mensaje

    print(f"\nOllama no tiene ningún modelo de IA instalado. BRAIN necesita uno ({modelo}, unos 2,5 GB).")

    try:
        respuesta = input("¿Quieres descargarlo ahora? (s/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False, mensaje

    if respuesta not in {"s", "si", "sí", "y", "yes"}:
        return False, mensaje

    try:
        if ollama.descargar_modelo(modelo):
            return True, ""
    except OllamaError as error:
        return False, str(error)

    return False, mensaje


def _salida_de(comando, espera=15):
    """
    Ejecuta un comando y devuelve su salida como texto.

    Los programas de Windows (netstat, tasklist...) escriben en la página de
    códigos de la consola, no en UTF-8: se decodifica sin fallar nunca.
    """

    try:
        resultado = subprocess.run(comando, capture_output=True, timeout=espera)
    except (OSError, subprocess.SubprocessError):
        return ""

    return (resultado.stdout or b"").decode("utf-8", errors="replace")


def quien_escucha(url):
    """
    Nombres de los programas que escuchan en el puerto de Ollama (solo
    Windows). Sirve para detectar un segundo Ollama (por ejemplo en Docker).
    """

    if os.name != "nt":
        return []

    puerto = url.rsplit(":", 1)[-1].strip("/")

    salida = _salida_de(["netstat", "-ano", "-p", "tcp"])

    pids = set()

    for linea in salida.splitlines():
        partes = linea.split()

        if len(partes) >= 5 and partes[3].upper() == "LISTENING" and partes[1].endswith(f":{puerto}"):
            pids.add(partes[4])

    nombres = []

    for pid in sorted(pids):
        tarea = _salida_de(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"])
        coincide = re.match(r'"([^"]+)"', tarea.strip())
        nombres.append(f"{coincide.group(1) if coincide else 'desconocido'} (PID {pid})")

    return nombres


def diagnostico(brain):
    """Muestra el estado del sistema (útil para ver qué falla)."""

    ollama = brain.ai.ollama

    print("\n=== DIAGNÓSTICO DE BRAIN ===")
    print(f"Versión de BRAIN : {Config.VERSION}")
    print(f"Python           : {platform.python_version()} ({platform.system()} {platform.release()})")
    print(f"Datos            : {Config.DATOS}")
    print(f"Ollama (programa): {buscar_ejecutable() or 'NO ENCONTRADO'}")
    print(f"Ollama (servidor): {'activo' if ollama.servidor_activo() else 'apagado'} en {ollama.url}")

    try:
        modelos = ollama.modelos()
        print(f"Modelos          : {', '.join(modelos) or 'ninguno'}")

        if modelos:
            print(f"Modelo elegido   : {ollama.resolver_modelo()}")
    except OllamaError as error:
        print(f"Modelos          : no disponible ({error})")

    if os.environ.get("OLLAMA_HOST"):
        print(f"OLLAMA_HOST      : {os.environ['OLLAMA_HOST']}")

    if os.environ.get("OLLAMA_MODELS"):
        print(f"OLLAMA_MODELS    : {os.environ['OLLAMA_MODELS']}")

    listado = ollama.lista_por_comando()

    if listado:
        print("Lo que ve el comando 'ollama list':")

        for linea in listado.splitlines():
            print(f"    {linea}")

    try:
        escuchan = quien_escucha(ollama.url)
    except Exception:
        escuchan = []

    if escuchan:
        print(f"Programas escuchando en ese puerto: {', '.join(escuchan)}")

    try:
        recomendado = recomendar_modelo()
        print(f"Tu equipo        : {recomendado['hardware'].resumen()}")
        print(f"Modelo ideal     : {recomendado['etiqueta']} (se instala con MEJORAR_IA.bat)")
    except Exception as error:
        print(f"Tu equipo        : no he podido medirlo ({error})")

    print(f"Módulos          : {', '.join(brain.modules.listar())}")
    print(f"Herramientas     : {len(brain.tools.listar())}")


def configurar_energia(brain):
    """Asistente para elegir los sensores del inversor y del contador."""

    from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError
    from brain.modules.energia import (
        NOMBRES_ROL,
        ROLES,
        EnergiaTiempoReal,
        _a_vatios,
        _es_potencia,
        describir,
        detectar_sensores,
        guardar_sensores_energia,
    )

    print("\n=== VER EL INVERSOR EN TIEMPO REAL ===")

    ha = HomeAssistant()

    if not ha.configurado:
        print("Primero hay que conectar Home Assistant: ejecuta CONFIGURAR_DOMOTICA.bat.")
        return 1

    try:
        estados = ha.estados()
    except HomeAssistantError as error:
        print(f"[Error] {error}")
        return 1

    candidatos = detectar_sensores(estados)

    potencias = [
        {"entidad": e["entity_id"], "nombre": (e.get("attributes") or {}).get("friendly_name", e["entity_id"]), "valor_w": round(_a_vatios(e))}
        for e in estados
        if _es_potencia(e) and _a_vatios(e) is not None
    ]

    if not potencias:
        print("Home Assistant no tiene ningún sensor de potencia (W o kW).")
        print("Primero añade tu inversor en Home Assistant (Ajustes > Dispositivos y servicios) y vuelve a ejecutar esto.")
        return 1

    print("Voy a buscar en Home Assistant los sensores de tu inversor solar y de tu contador.")
    print("En cada pregunta: Enter = elegir el primero (el que mejor encaja), 0 = ninguno, t = ver todos.\n")

    def mostrar(lista):
        for i, c in enumerate(lista, 1):
            valor = "" if c["valor_w"] is None else f"  (ahora: {c['valor_w']} W)"
            print(f"   {i}) {c['nombre']}{valor}")

    elegidos = {}

    for rol in ROLES:
        if rol == "bateria_pct":
            lista = candidatos[rol]

            if not lista:
                continue
        else:
            lista = candidatos[rol] or []

        print(f"\n» {NOMBRES_ROL[rol].capitalize()}:")

        if lista:
            mostrar(lista)
        else:
            print("   (no he encontrado ninguno que encaje)")

        while True:
            try:
                respuesta = input("   Tu elección: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return 1

            if respuesta == "t" and rol != "bateria_pct":
                lista = potencias
                mostrar(lista)
                continue

            if respuesta == "" and lista:
                elegidos[rol] = lista[0]["entidad"]
                break

            if respuesta in ("0", ""):
                break

            if respuesta.isdigit() and 1 <= int(respuesta) <= len(lista):
                elegidos[rol] = lista[int(respuesta) - 1]["entidad"]
                break

            print("   No te he entendido; escribe un número, Enter, 0 o t.")

    if not elegidos:
        print("\nNo has elegido ningún sensor; no cambio nada.")
        return 1

    # El signo de "red" depende del aparato: se averigua preguntando.
    if elegidos.get("red"):
        actual = next((p["valor_w"] for p in potencias if p["entidad"] == elegidos["red"]), None)

        if actual is not None and abs(actual) > 50:
            print(f"\nEl sensor de la red marca ahora {actual} W.")

            try:
                respuesta = input("¿Ahora mismo estás COMPRANDO electricidad a la red (c), VENDIENDO (v) o no lo sabes (?): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return 1

            if respuesta.startswith("c") and actual < 0:
                elegidos["red_invertida"] = True
            elif respuesta.startswith("v") and actual > 0:
                elegidos["red_invertida"] = True

    guardar_sensores_energia(elegidos)

    print("\n[OK] Guardado. Esto es lo que veo ahora mismo:")
    print("   " + describir(EnergiaTiempoReal().leer()))
    print("\nBRAIN lo mostrará en directo en el panel «Energía ahora».")

    return 0


def configurar_domotica(brain):
    """Asistente para conectar BRAIN con Home Assistant."""

    from getpass import getpass

    from brain.integrations.home_assistant import (
        HomeAssistant,
        HomeAssistantError,
        encontrar_home_assistant,
        guardar_configuracion,
        leer_configuracion,
        normalizar_url,
    )

    print("\n=== CONECTAR BRAIN CON LA DOMÓTICA (Home Assistant) ===")
    print("Necesitas tener Home Assistant funcionando en tu red. Si no lo tienes, mira GUIA_DOMOTICA.md.\n")

    url_actual, token_actual = leer_configuracion()

    print("Buscando Home Assistant en tu red...")
    encontrada = encontrar_home_assistant()

    sugerida = url_actual or encontrada

    if encontrada:
        print(f"Lo he encontrado en {encontrada}")
    else:
        print("No lo he encontrado automáticamente.")

    try:
        entrada = input(f"Dirección de Home Assistant [{sugerida or 'por ejemplo 192.168.1.50:8123'}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        return 1

    url = normalizar_url(entrada or sugerida)

    if not url:
        print("[Error] Necesito la dirección de Home Assistant.")
        return 1

    print("\nAhora necesito la llave de acceso (token). Para crearla:")
    print("  1. Abre Home Assistant en el navegador y entra en tu perfil (tu nombre abajo a la izquierda).")
    print("  2. Pestaña 'Seguridad' > al final 'Tokens de acceso de larga duración' > 'Crear token'.")
    print("  3. Ponle el nombre BRAIN, copia el texto largo que aparece y pégalo aquí (clic derecho).")

    try:
        token = getpass("\nToken (no se verá mientras lo pegas, pulsa Enter): ").strip()
    except (EOFError, KeyboardInterrupt):
        return 1

    token = token or token_actual

    if not token:
        print("[Error] Necesito el token.")
        return 1

    cliente = HomeAssistant(url, token)

    print("\nProbando la conexión...")

    try:
        cliente.comprobar()
        estados = cliente.estados()
    except HomeAssistantError as error:
        print(f"[Error] {error}")
        print("No he guardado nada. Revisa los datos y vuelve a ejecutarlo.")
        return 1

    guardar_configuracion(url, token)

    cuentas = {}

    for estado in estados:
        dominio = estado.get("entity_id", "").split(".", 1)[0]
        cuentas[dominio] = cuentas.get(dominio, 0) + 1

    print("\n[OK] Conectado con Home Assistant. Esto es lo que puede controlar BRAIN:")

    for dominio, nombre in (
        ("light", "luces"),
        ("switch", "enchufes e interruptores"),
        ("cover", "persianas y cortinas"),
        ("climate", "termostatos"),
        ("scene", "escenas"),
        ("media_player", "reproductores"),
    ):
        if cuentas.get(dominio):
            print(f"  - {cuentas[dominio]} {nombre}")

    if not cuentas.get("light") and not cuentas.get("switch"):
        print("  (Todavía no hay luces ni enchufes. Añade tus aparatos en Home Assistant y BRAIN los verá solo.)")

    print("\nYa puedes abrir BRAIN y decirle: «Enciende la luz del salón».")

    try:
        from brain.modules.energia import detectar_sensores

        if detectar_sensores(estados)["produccion"]:
            print("\nHe encontrado sensores que parecen de un inversor solar.")

            if input("¿Quieres ver ahora la producción y el consumo en tiempo real? (s/n): ").strip().lower() in {"s", "si", "sí", "y"}:
                return configurar_energia(brain)
    except (EOFError, KeyboardInterrupt):
        pass

    return 0


def _aparece_en_ollama(ollama, etiqueta, intentos=10):
    """Comprueba (con algo de paciencia) que Ollama lista el modelo recién descargado."""

    for _ in range(intentos):
        try:
            if ollama._buscar_modelo(etiqueta, ollama.modelos()):
                return True
        except OllamaError:
            pass

        time.sleep(1)

    return False


def mejorar_ia(brain, auto=False):
    """
    Mide el equipo, elige el mejor modelo de IA que le cabe y lo descarga.

    Con auto=True no hace preguntas (lo usa el instalador). Devuelve 0 si
    al final BRAIN tiene un modelo listo.
    """

    ollama = brain.ai.ollama

    print("\n=== MEJORAR LA IA DE BRAIN ===")
    print("Midiendo tu ordenador...")

    recomendado = recomendar_modelo(detectar_hardware())
    etiqueta = recomendado["etiqueta"]

    print(recomendado["hardware"].resumen())

    for nota in recomendado["hardware"].notas:
        print(f"[!] {nota}")

    print(f"\nModelo recomendado: {etiqueta} (descarga de unos {recomendado['descarga_gb']:g} GB)")
    print(recomendado["explicacion"])

    if not ollama.servidor_activo():
        print("\nArrancando Ollama...")

        if not ollama.iniciar_servidor(espera=90):
            print("[Error] No consigo arrancar Ollama. Ejecuta INSTALAR.bat o ábrelo desde el menú Inicio.")
            return 1

    instalados = ollama.modelos()

    if ollama._buscar_modelo(etiqueta, instalados):
        guardar_modelo(etiqueta)
        print(f"\nYa tienes {etiqueta} instalado. BRAIN lo usará.")
        return 0

    if not auto:
        try:
            respuesta = input("\n¿Descargarlo ahora? (s/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 1

        if respuesta not in {"s", "si", "sí", "y", "yes"}:
            print("Vale, no cambio nada.")
            return 0

    for candidato in [etiqueta] + alternativas(etiqueta):
        print(f"\nDescargando {candidato} (solo la primera vez, puede tardar)...")

        try:
            correcto = ollama.descargar_modelo(candidato)
        except OllamaError as error:
            print(f"[Error] {error}")
            return 1

        if correcto:
            if not _aparece_en_ollama(ollama, candidato):
                print(f"[!] Ollama dice que descargó {candidato} pero no lo veo en su lista.")
                print("    Puede que haya dos Ollama distintos en este PC. Ejecuta DIAGNOSTICO.bat y mándame lo que salga.")
                return 1

            guardar_modelo(candidato)
            print(f"\nListo: BRAIN usará {candidato}.")

            if instalados:
                print("Puedes borrar los modelos antiguos para liberar espacio (ollama rm nombre).")

            return 0

        print(f"[!] No se ha podido descargar {candidato}. Pruebo con uno más pequeño.")

    # Si no se pudo descargar nada nuevo, sirve lo que ya hubiera.
    if instalados:
        print("\nSigo con el modelo que ya tenías instalado.")
        return 0

    print("[Error] No he podido descargar ningún modelo. Comprueba tu conexión a internet.")
    return 1


def chat_consola(brain):
    """Chat de texto en la consola."""

    print("\nEscribe tu mensaje y pulsa Enter. /ayuda para ver los comandos, /salir para cerrar.\n")

    while True:
        try:
            texto = input("Tú > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not texto:
            continue

        if texto.startswith("/"):
            comando = texto.lower()

            if comando in {"/salir", "/exit", "/quit"}:
                break

            if comando == "/ayuda":
                print(AYUDA)

            elif comando == "/herramientas":
                for herramienta in brain.tools.listar():
                    print(f"- {herramienta['nombre']}: {herramienta['descripcion']}")

            elif comando == "/modelos":
                try:
                    for modelo in brain.ai.modelos():
                        print(f"- {modelo}")
                except OllamaError as error:
                    print(error)

            elif comando == "/limpiar":
                brain.conversacion.limpiar()
                print("Conversación borrada.")

            else:
                print("Ese comando no existe. Escribe /ayuda.")

            continue

        try:
            print("BRAIN está pensando...", end="\r", flush=True)

            respuesta = brain.conversacion.preguntar(texto)

            print(" " * 30, end="\r")
            print(f"BRAIN > {respuesta}\n")

        except OllamaError as error:
            print(" " * 30, end="\r")
            print(f"[Error] {error}\n")

        except KeyboardInterrupt:
            print("\nCancelado.\n")

    print("Hasta luego.")


def salir_con_error(mensaje, codigo=1):
    print(f"\n[BRAIN] {mensaje}", file=sys.stderr)

    return codigo
