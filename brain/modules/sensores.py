from datetime import datetime

from brain.base.modulo import ModuloBase
from brain.modules.inventario import normalizar

TIPOS = ("temperatura", "humedad", "presencia", "agua", "luminosidad")

SINONIMOS = {
    "temp": "temperatura",
    "luz": "luminosidad",
    "movimiento": "presencia",
}


class Sensores(ModuloBase):
    nombre = "sensores"

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

        self.añadir_registro(tipo, lectura)

        return {"sensor": tipo, **lectura}

    def ultima(self, tipo):
        tipo = self.normalizar_tipo(tipo)

        lecturas = self.obtener_seccion(tipo)

        if not lecturas:
            return None

        return {"sensor": tipo, **lecturas[-1]}
