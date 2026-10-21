from datetime import datetime

from brain.base.modulo import ModuloBase
<<<<<<< HEAD
from brain.core.database import Database
=======
<<<<<<< HEAD
from brain.core.database import Database
=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
from brain.modules.inventario import normalizar

TIPOS = ("temperatura", "humedad", "presencia", "agua", "luminosidad")

SINONIMOS = {
    "temp": "temperatura",
    "luz": "luminosidad",
    "movimiento": "presencia",
}


class Sensores(ModuloBase):
    nombre = "sensores"

<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
    def __init__(self):
        super().__init__()
        self.db = Database()

<<<<<<< HEAD
=======
=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
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

<<<<<<< HEAD
        self.db.guardar_lectura_sensor(tipo, valor, ubicacion, lectura["fecha"])
=======
<<<<<<< HEAD
        self.db.guardar_lectura_sensor(tipo, valor, ubicacion, lectura["fecha"])
=======
        self.añadir_registro(tipo, lectura)
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80

        return {"sensor": tipo, **lectura}

    def ultima(self, tipo):
        tipo = self.normalizar_tipo(tipo)

<<<<<<< HEAD
        lecturas = self.db.lecturas_sensor(tipo, limite=1)
=======
<<<<<<< HEAD
        lecturas = self.db.lecturas_sensor(tipo, limite=1)
=======
        lecturas = self.obtener_seccion(tipo)
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80

        if not lecturas:
            return None

        return {"sensor": tipo, **lecturas[-1]}
