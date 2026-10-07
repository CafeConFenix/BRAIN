import importlib
import inspect
from pathlib import Path


class ModuleLoader:
    """
    Descubre, carga y expone automáticamente los módulos de BRAIN.

    Cada archivo de brain/modules/ debe contener una clase cuyo nombre
    corresponda al módulo en formato PascalCase.

    Ejemplo:

        salud.py -> class Salud
        inventario.py -> class Inventario
        energia.py -> class Energia
    """

    def __init__(self):
        self.ruta = Path(__file__).resolve().parent.parent / "modules"

        self.modulos = {}
        self.instancias = {}

        self._cargar()

    def _nombre_clase(self, nombre):
        """
        Convierte un nombre de módulo a nombre de clase.

        salud -> Salud
        inventario -> Inventario
        memoria -> Memoria
        """

        return "".join(parte.capitalize() for parte in nombre.split("_"))

    def _cargar(self):
        """
        Descubre e importa todos los módulos disponibles.
        """

        if not self.ruta.exists():
            return

        for archivo in sorted(self.ruta.glob("*.py")):

            if archivo.name.startswith("_"):
                continue

            nombre = archivo.stem
            nombre_clase = self._nombre_clase(nombre)

            try:
                modulo = importlib.import_module(f"brain.modules.{nombre}")

                clase = getattr(
                    modulo,
                    nombre_clase,
                    None,
                )

                if clase is None:
                    print(
                        f"[BRAIN] El módulo "
                        f"{nombre} no tiene la clase "
                        f"{nombre_clase}"
                    )
                    continue

                if not inspect.isclass(clase):
                    continue

                instancia = clase()

                self.modulos[nombre] = modulo
                self.instancias[nombre] = instancia

            except Exception as error:
                print(f"[BRAIN] Error cargando módulo " f"{nombre}: {error}")

    def listar(self):
        """
        Devuelve los nombres de los módulos cargados.
        """

        return sorted(self.instancias.keys())

    def obtener(self, nombre):
        """
        Devuelve la instancia de un módulo.
        """

        return self.instancias.get(nombre)

    def recargar(self, nombre):
        """
        Recarga un módulo y crea una nueva instancia.
        """

        if nombre not in self.modulos:
            return False

        modulo = importlib.reload(self.modulos[nombre])

        nombre_clase = self._nombre_clase(nombre)

        clase = getattr(
            modulo,
            nombre_clase,
            None,
        )

        if clase is None:
            return False

        instancia = clase()

        self.modulos[nombre] = modulo
        self.instancias[nombre] = instancia

        return True
