"""
Asistente para entrar a BRAIN desde el móvil u otro PC con Tailscale.

Tailscale crea una red privada entre tus dispositivos. BRAIN sigue escuchando
solo en este ordenador; `tailscale serve` publica esa dirección únicamente
dentro de tu red privada, con HTTPS, y BRAIN pide contraseña a quien llegue
por ahí. No se abre ningún puerto del router.
"""

import getpass
import json
import shutil
import subprocess
from typing import Optional

from brain.utils.procesos import ejecutar
from brain.web.acceso import MIN_CLAVE, Acceso


def _ejecutar(argumentos, tiempo=25):
    try:
        r = ejecutar(argumentos, capture_output=True, timeout=tiempo)
    except (OSError, subprocess.SubprocessError):
        return None, ""

    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


def buscar_tailscale() -> Optional[str]:
    encontrado = shutil.which("tailscale")

    if encontrado:
        return encontrado

    import os
    from pathlib import Path

    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(variable)

        if base and (Path(base) / "Tailscale" / "tailscale.exe").exists():
            return str(Path(base) / "Tailscale" / "tailscale.exe")

    return None


def nombre_tailscale(ejecutable: str) -> Optional[str]:
    """Nombre privado de este ordenador en Tailscale (por ejemplo, casa.tail1234.ts.net)."""

    codigo, texto = _ejecutar([ejecutable, "status", "--json"])

    if codigo != 0:
        return None

    try:
        nombre = json.loads(texto).get("Self", {}).get("DNSName", "")
    except ValueError:
        return None

    return nombre.rstrip(".") or None


def publicar(ejecutable: str, puerto: int) -> bool:
    """Publica BRAIN dentro de la red privada con HTTPS (prueba la sintaxis nueva y la antigua)."""

    for argumentos in (
        [ejecutable, "serve", "--bg", f"http://127.0.0.1:{puerto}"],
        [ejecutable, "serve", "--bg", str(puerto)],
        [ejecutable, "serve", "https", "/", f"http://127.0.0.1:{puerto}"],
    ):
        codigo, _ = _ejecutar(argumentos)

        if codigo == 0:
            return True

    return False


def estado_publicacion(ejecutable: str) -> str:
    """Lo que Tailscale tiene publicado ahora mismo (`tailscale serve status`)."""

    _, texto = _ejecutar([ejecutable, "serve", "status"], tiempo=15)

    return texto.strip()


def probar_local(puerto: int, nombre: str) -> str:
    """
    Pide a BRAIN la pagina de entrada con el nombre privado como `Host`, igual que
    hace Tailscale. Devuelve "" si todo va bien o el motivo del fallo.
    """

    import http.client

    from brain.core.config import Config

    try:
        # http.client no pasa por ningun proxy del sistema (urllib si podria).
        conexion = http.client.HTTPConnection("127.0.0.1", puerto, timeout=5)
        conexion.request("GET", "/", headers={"Host": nombre, "X-Forwarded-Proto": "https"})
        respuesta = conexion.getresponse()
        cuerpo = respuesta.read()
        servidor = respuesta.getheader("Server", "desconocido")
        conexion.close()
    except Exception as error:
        return f"BRAIN no responde en el puerto {puerto} ({error}). Abre BRAIN y repite este paso."

    if respuesta.status == 200 and b"BRAIN" in cuerpo:
        return ""

    detalle = f"codigo {respuesta.status}, servidor '{servidor}', puerto {puerto}, respuesta: {cuerpo[:160].decode('utf-8', 'replace')}"

    if not servidor.startswith("BRAIN/") or servidor != f"BRAIN/{Config.VERSION}":
        return (
            f"{detalle}\n    Parece que hay una copia ANTIGUA de BRAIN abierta (o algo distinto en ese puerto).\n"
            "    Ejecuta CERRAR_BRAIN.bat, abre BRAIN de nuevo y repite este paso."
        )

    return detalle


def configurar_acceso(puerto: int) -> int:
    from brain.escritorio import instancia

    # Si BRAIN ya esta abierto en otro puerto (el 8765 estaba ocupado), se usa ese.
    puerto = instancia.puerto_en_marcha() or puerto
    acceso = Acceso()

    print("\n=== Acceso a BRAIN desde el móvil u otro ordenador ===\n")

    if acceso.configurada():
        print("Ya hay una contraseña. Pulsa Intro para conservarla o escribe una nueva.")

    while True:
        clave = getpass.getpass(f"Contraseña (mínimo {MIN_CLAVE} caracteres): ")

        if not clave and acceso.configurada():
            break

        try:
            acceso.establecer_clave(clave)
            break
        except ValueError as error:
            print(f"  {error}")

    ejecutable = buscar_tailscale()

    if ejecutable is None:
        print(
            "\nLa contraseña está guardada, pero falta Tailscale.\n"
            "  1. Instálalo en este ordenador y en el móvil desde https://tailscale.com/download\n"
            "  2. Entra con la misma cuenta en los dos.\n"
            "  3. Vuelve a ejecutar CONFIGURAR_ACCESO.bat.\n"
        )

        return 1

    nombre = nombre_tailscale(ejecutable)

    if not nombre:
        print("\nTailscale está instalado pero no has iniciado sesión. Ábrelo, entra con tu cuenta y repite este paso.\n")

        return 1

    if not publicar(ejecutable, puerto):
        print(
            "\nNo he podido publicar BRAIN con Tailscale. Si es la primera vez, entra en tu panel de Tailscale\n"
            "(https://login.tailscale.com/admin/dns) y activa 'HTTPS Certificates'; después repite este paso.\n"
        )

        return 1

    direccion = f"https://{nombre}"
    acceso.guardar_direccion(direccion)
    acceso.anadir_host(nombre)

    problema = probar_local(puerto, nombre)

    if problema:
        print(f"\n[!] BRAIN no esta listo para recibir conexiones: {problema}")
        print(f"    (nombre privado: {nombre})")
        print("    Abre BRAIN (icono del escritorio), espera unos segundos y vuelve a ejecutar CONFIGURAR_ACCESO.bat.\n")

        return 1

    print("\nTailscale tiene publicado esto:\n")
    print(estado_publicacion(ejecutable) or "  (no he podido leerlo)")

    print(f"\nListo. Desde tu móvil (con Tailscale activado) abre:\n\n    {direccion}\n")
    print("Te pedirá la contraseña. En el móvil puedes usar 'Añadir a pantalla de inicio' para tener BRAIN como una app.\n")

    return 0
