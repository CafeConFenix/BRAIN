import importlib
import pkgutil

from brain.tools import builtin as _builtin

# Automatically imports every tool from brain/tools/builtin/.
# To add a new tool, just create a file there with
# functions decorated with @tool.
for _module in pkgutil.iter_modules(_builtin.__path__):
    importlib.import_module(f"{_builtin.__name__}.{_module.name}")
