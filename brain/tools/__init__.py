import importlib
import pkgutil

from brain.tools import builtin as _builtin

# Importa automáticamente todas las herramientas de brain/tools/builtin/.
# Para añadir una herramienta nueva basta con crear un archivo ahí con
# funciones decoradas con @tool.
for _modulo in pkgutil.iter_modules(_builtin.__path__):
    importlib.import_module(f"{_builtin.__name__}.{_modulo.name}")
