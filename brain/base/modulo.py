from brain.core.data_manager import DataManager


class ModuloBase:
    """
    Base común de los módulos de BRAIN.

    Cada módulo guarda sus datos en datos/<nombre>/<nombre>.json, dividido
    en secciones (listas de registros). Los módulos nunca tocan archivos
    directamente: todo pasa por el DataManager.
    """

    nombre = ""

    def __init__(self):
        self.data = DataManager()

    def añadir_registro(self, seccion, registro):
        self.data.añadir_registro(
            modulo=self.nombre,
            seccion=seccion,
            registro=registro,
        )

    def obtener_seccion(self, seccion):
        datos = self.data.leer_modulo(self.nombre)

        valor = datos.get(seccion, [])

        if not isinstance(valor, list):
            return []

        return valor

    def guardar_seccion(self, seccion, registros):
        datos = self.data.leer_modulo(self.nombre)

        datos[seccion] = registros

        self.data.guardar_modulo(self.nombre, datos)

    def secciones(self):
        """Devuelve los nombres de las secciones del módulo."""

        return list(self.data.leer_modulo(self.nombre).keys())
