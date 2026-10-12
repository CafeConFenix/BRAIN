from datetime import datetime

from brain.base.modulo import ModuloBase
from brain.core.database import Database
from brain.modules.inventario import normalizar

TIPOS = ("temperatura", "humedad", "presencia", "agua", "luminosidad")

SINONIMOS = {
    "temp": "temperatura",
    "luz": "luminosidad",
    "movimiento": "presencia",
}


class Sensores(ModuloBase):
    nombre = "sensores"

    def __init__(self):
        super().__init__()
        self.db = Database()

    def normalizar_tipo(self, tipo):
        clave = normalizar(tipo)

        clave = SINONIMOS.get(clave, clave)

        if clave not in TIPOS:
            raise ValueError(f"El sensor '{tipo}' no existe. Opciones: {', '.join(TIPOS)}.")

        return clave

    def registrar(self, tipo, valor, ubicacion=None):
        tipo = self.normalizar_tipo(tipo)

        lectura = {
            "valor": valor,
            "ubicacion": ubicacion,
            "fecha": datetime.now().isoformat(timespec="seconds"),
        }

        self.db.guardar_lectura_sensor(tipo, valor, ubicacion, lectura["fecha"])

        return {"sensor": tipo, **lectura}

    def ultima(self, tipo):
        tipo = self.normalizar_tipo(tipo)

        lecturas = self.db.lecturas_sensor(tipo, limite=1)

        if not lecturas:
            return None

        return {"sensor": tipo, **lecturas[-1]}
