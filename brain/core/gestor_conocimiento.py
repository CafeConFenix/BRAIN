from brain.core.config import Config
from brain.core.data_manager import DataManager


class GestorConocimiento:
    """
    Punto único de acceso al conocimiento de BRAIN.

    La IA y otros componentes del sistema utilizarán esta clase
    para consultar información sin acceder directamente al DataManager.
    """

    def __init__(self):
        self.data = DataManager()

    def obtener(self, modulo: str, seccion: str):
        """
        Devuelve el contenido de una sección de un módulo.
        """

        datos = self.data.leer_modulo(modulo)

        if datos is None:
            return None

        return datos.get(seccion, [])

    def personalidad(self):
        """
        Devuelve el texto de personalidad.md (la del usuario o, si no hay, la de fábrica).

        Se lee con utf-8-sig para aceptar archivos guardados con el
        Bloc de notas de Windows.
        """

        for ruta in (Config.PERSONALIDAD, Config.PERSONALIDAD_BASE):
            try:
                with open(ruta, "r", encoding="utf-8-sig") as f:
                    return f.read().strip()

            except OSError:
                continue

        return ""

    def recuerdos(self):
        """Devuelve en texto todo lo que el usuario ha pedido recordar."""

        from brain.modules.memoria import Memoria

        return Memoria().resumen_para_ia()
