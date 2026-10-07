from brain.tools.registry import ToolRegistry


class ToolExecutor:
    """
    Ejecuta herramientas registradas.
    """

    def __init__(self):
        self.registry = ToolRegistry()

    def ejecutar(self, nombre, /, argumentos=None, **kwargs):
        """
        Ejecuta una herramienta.

        Los argumentos se pueden pasar como diccionario o como
        parámetros con nombre:

            ejecutar("guardar_peso", {"peso": 80})
            ejecutar("guardar_peso", peso=80)
        """

        if argumentos:
            if not isinstance(argumentos, dict):
                raise TypeError("Los argumentos deben ser un diccionario.")

            kwargs = {**argumentos, **kwargs}

        # `nombre` es solo posicional: así una herramienta puede tener un
        # parámetro llamado "nombre" (anadir_inventario) sin chocar con este.
        return self.registry.ejecutar(nombre, kwargs)

    def listar(self):
        """Devuelve las herramientas disponibles."""

        return self.registry.listar()

    def obtener(self, nombre):
        """Obtiene una herramienta."""

        return self.registry.obtener(nombre)

    def esquemas(self):
        """Devuelve las herramientas en formato JSON Schema para Ollama."""

        return self.registry.esquemas()
