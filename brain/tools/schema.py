from dataclasses import dataclass
from typing import Any


@dataclass
class ToolParameter:
    nombre: str
    tipo: str
    descripcion: str
    requerido: bool = True


@dataclass
class ToolSchema:
    nombre: str
    descripcion: str
    funcion: Any
    parametros: list[ToolParameter]
