from brain.base.modulo import ModuloBase
from brain.utils.fechas import validar_fecha


class Salud(ModuloBase):
    nombre = "salud"

    def guardar_peso(self, peso, fecha=None):
        """
        Guarda el peso de un día. Si ya había uno ese día, lo actualiza
        en lugar de duplicarlo.
        """

        peso = float(peso)

        if not 20 <= peso <= 500:
            raise ValueError(f"El peso {peso} no parece correcto (debe estar entre 20 y 500).")

        fecha = validar_fecha(fecha)

        registros = [r for r in self.obtener_seccion("peso") if r.get("fecha") != fecha]

        registros.append({"peso": peso, "fecha": fecha})

        registros.sort(key=lambda r: r.get("fecha", ""))

        self.guardar_seccion("peso", registros)

        return {"peso": peso, "fecha": fecha}

    def historial_peso(self, limite=None):
        """Devuelve los pesos ordenados de más antiguo a más reciente."""

        registros = sorted(
            self.obtener_seccion("peso"),
            key=lambda r: r.get("fecha", ""),
        )

        if limite:
            registros = registros[-int(limite) :]

        return registros

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

        registros = self.historial_peso()

        for registro in registros:
            if registro.get("fecha") == fecha:
                return {**registro, "exacto": True}

        anteriores = [r for r in registros if r.get("fecha", "") < fecha]

        if anteriores:
            return {**anteriores[-1], "exacto": False, "buscada": fecha}

        return None
