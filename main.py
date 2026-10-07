import argparse
import sys

from brain.utils.consola import preparar_consola


def leer_argumentos(argumentos=None):
    parser = argparse.ArgumentParser(
        prog="BRAIN",
        description="BRAIN: tu asistente personal con inteligencia artificial local.",
    )

    modo = parser.add_mutually_exclusive_group()

    modo.add_argument(
        "--web",
        action="store_true",
        help="abre la interfaz web en el navegador (opción por defecto)",
    )

    modo.add_argument(
        "--consola",
        action="store_true",
        help="chatea con BRAIN en esta ventana, sin navegador",
    )

    modo.add_argument(
        "--diagnostico",
        action="store_true",
        help="muestra el estado del sistema y sale",
    )

    modo.add_argument(
        "--mejorar-ia",
        action="store_true",
        help="mide tu ordenador, elige el mejor modelo de IA y lo descarga",
    )

    modo.add_argument(
        "--configurar-domotica",
        action="store_true",
        help="conecta BRAIN con Home Assistant para controlar luces y dispositivos",
    )

    modo.add_argument(
        "--configurar-energia",
        action="store_true",
        help="elige los sensores del inversor para ver la energía en tiempo real",
    )

    parser.add_argument(
        "--auto",
        action="store_true",
        help="con --mejorar-ia: no hacer preguntas",
    )

    parser.add_argument(
        "--no-navegador",
        action="store_true",
        help="con --web: no abrir el navegador automáticamente",
    )

    parser.add_argument(
        "--puerto",
        type=int,
        default=None,
        help="puerto de la interfaz web (por defecto 8765)",
    )

    return parser.parse_args(argumentos)


def main(argumentos=None):
    preparar_consola()

    opciones = leer_argumentos(argumentos)

    from brain.cli import chat_consola, configurar_domotica, configurar_energia, diagnostico, mejorar_ia, preparar_ia
    from brain.core import Brain
    from brain.core.config import Config

    silencioso = (
        opciones.diagnostico or opciones.mejorar_ia or opciones.configurar_domotica or opciones.configurar_energia
    )

    brain = Brain(silencioso=silencioso)

    if opciones.mejorar_ia:
        return mejorar_ia(brain, auto=opciones.auto)

    if opciones.configurar_domotica:
        return configurar_domotica(brain)

    if opciones.configurar_energia:
        return configurar_energia(brain)

    if opciones.diagnostico:
        diagnostico(brain)
        return 0

    if opciones.consola:
        listo, mensaje = preparar_ia(brain, interactivo=True)

        if not listo:
            print(f"\n[BRAIN] {mensaje}")
            print("Puedes seguir, pero BRAIN no podrá responder hasta que se arregle.\n")

        chat_consola(brain)

        return 0

    from brain.web.servidor import servir

    listo, mensaje = preparar_ia(brain, interactivo=False)

    if not listo:
        print(f"\n[BRAIN] {mensaje}")
        print("La interfaz web se abrirá igualmente y te lo recordará.\n")

    servir(
        brain,
        puerto=opciones.puerto or Config.PUERTO_WEB,
        abrir_navegador=not opciones.no_navegador,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
