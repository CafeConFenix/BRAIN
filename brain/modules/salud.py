from brain.base.modulo import ModuloBase
from brain.core.database import Database
from brain.utils.fechas import validar_fecha


class Salud(ModuloBase):
    nombre = "salud"

    def __init__(self):
        super().__init__()
        self.db = Database()

    def guardar_peso(self, peso, fecha=None):
        """
        Guarda el peso de un día. Si ya había uno ese día, lo actualiza
        en lugar de duplicarlo.
        """

        peso = float(peso)

        if not 20 <= peso <= 500:
            raise ValueError(f"El peso {peso} no parece correcto (debe estar entre 20 y 500).")

        fecha = validar_fecha(fecha)

        self.db.guardar_peso(fecha, peso)

        return {"peso": peso, "fecha": fecha}

    def historial_peso(self, limite=None):
        """Devuelve los pesos ordenados de más antiguo a más reciente."""

        return self.db.historial_peso(limite)

    def peso_actual(self):
        """Devuelve el registro de peso más reciente (o None)."""

        registros = self.historial_peso()

        if not registros:
            return None

        return registros[-1]

    def peso_en(self, fecha):
        """
        Devuelve el peso de una fecha. Si ese día no hay registro,
        devuelve el último anterior e indica que es aproximado.
        """

        fecha = validar_fecha(fecha)

        exacto = self.db.peso_exacto(fecha)

        if exacto:
            return {**exacto, "exacto": True}

        anterior = self.db.peso_anterior(fecha)

        if anterior:
            return {**anterior, "exacto": False, "buscada": fecha}

        return None

    # ------------------------------------------------------------------
    # Otras medidas de la báscula (grasa, IMC, agua...)
    # ------------------------------------------------------------------

    def guardar_medida(self, nombre, valor, unidad=None, fecha=None):
        """Guarda una medida corporal de un día (si ya había de ese nombre ese día, la sustituye)."""

        fecha = validar_fecha(fecha)

        self.db.guardar_medida(fecha, str(nombre), float(valor), unidad)

        return {"nombre": nombre, "valor": float(valor), "unidad": unidad, "fecha": fecha}

    def medidas(self, nombre=None, limite=30):
        return self.db.medidas(nombre, limite)
