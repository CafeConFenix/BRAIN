from datetime import date, datetime, timedelta

from brain.base.modulo import ModuloBase
from brain.modules.inventario import normalizar
from brain.utils.fechas import validar_fecha


def _hora(valor) -> str:
    try:
        h, m = str(valor).strip().replace(".", ":").split(":")
        h, m = int(h), int(m)
    except ValueError:
        raise ValueError(f"La hora '{valor}' no es válida. Usa HH:MM, por ejemplo 21:30.") from None

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"La hora '{valor}' no es válida.")

    return f"{h:02d}:{m:02d}"


def _hora(valor) -> str:
    try:
        h, m = str(valor).strip().replace(".", ":").split(":")
        h, m = int(h), int(m)
    except ValueError:
        raise ValueError(f"La hora '{valor}' no es válida. Usa HH:MM, por ejemplo 21:30.") from None

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"La hora '{valor}' no es válida.")

    return f"{h:02d}:{m:02d}"


class Habitos(ModuloBase):
    """
    Hábitos diarios con objetivo y racha: beber agua, tomar una medicina,
    pasear, leer... Cada hábito tiene un objetivo por día (por ejemplo 8
    vasos) y la racha cuenta los días seguidos en los que se ha cumplido.
    """

    nombre = "habitos"

    # ------------------------------------------------------------------

    def _buscar(self, nombre):
        clave = normalizar(nombre)

        if not clave:
            raise ValueError("Indica el nombre del hábito.")

        habitos = self.obtener_seccion("habitos")

        for h in habitos:
            if normalizar(h["nombre"]) == clave:
                return h

        # Aproximado: "agua" encuentra "beber agua".
        parecidos = [h for h in habitos if clave in normalizar(h["nombre"]) or normalizar(h["nombre"]) in clave]

        if len(parecidos) == 1:
            return parecidos[0]

        if len(parecidos) > 1:
            raise ValueError("Hay varios hábitos que encajan: " + ", ".join(h["nombre"] for h in parecidos) + ". Indica cuál.")

        raise ValueError(f"No tengo el hábito '{nombre}'. Créalo primero.")

    def crear(self, nombre, objetivo=1, unidad="", hora="", persona="") -> dict:
        nombre = str(nombre or "").strip()[:40]

        if not nombre:
            raise ValueError("Indica el nombre del hábito.")

        try:
            objetivo = int(float(objetivo))
        except (TypeError, ValueError):
            raise ValueError("El objetivo diario debe ser un número.") from None

        if not 1 <= objetivo <= 1000:
            raise ValueError("El objetivo diario debe estar entre 1 y 1000.")

        habitos = self.obtener_seccion("habitos")
        existente = next((h for h in habitos if normalizar(h["nombre"]) == normalizar(nombre)), None)

        if existente:
            existente["objetivo"] = objetivo
            existente["unidad"] = str(unidad or existente.get("unidad", ""))[:20]

            if hora not in (None, ""):
                existente["hora"] = _hora(hora)

            if persona:
                existente["persona"] = str(persona).strip()[:30]

            self.guardar_seccion("habitos", habitos)

            return existente

        habito = {"nombre": nombre, "objetivo": objetivo, "unidad": str(unidad or "")[:20], "creado": date.today().isoformat()}

        if hora:
            habito["hora"] = _hora(hora)

        if persona:
            habito["persona"] = str(persona).strip()[:30]


        if hora not in (None, ""):
            habito["hora"] = _hora(hora)

        if persona:
            habito["persona"] = str(persona).strip()[:30]

        habitos.append(habito)
        self.guardar_seccion("habitos", habitos)

        return habito

    def anotar(self, nombre, cantidad=1, fecha=None) -> dict:
        habito = self._buscar(nombre)

        try:
            cantidad = int(float(cantidad))
        except (TypeError, ValueError):
            raise ValueError("La cantidad debe ser un número.") from None

        if not -1000 <= cantidad <= 1000 or cantidad == 0:
            raise ValueError("La cantidad debe ser distinta de cero y razonable.")

        dia = validar_fecha(fecha)
        registros = self.obtener_seccion("registros")
        registros.append({"fecha": dia, "habito": habito["nombre"], "cantidad": cantidad})
        self.guardar_seccion("registros", registros)

        return self._estado_de(habito, registros, date.fromisoformat(dia))

    def _totales(self, habito, registros) -> dict:
        totales = {}

        for r in registros:
            if r.get("habito") == habito["nombre"]:
                totales[r["fecha"]] = totales.get(r["fecha"], 0) + int(r.get("cantidad", 0))

        return totales

    def _estado_de(self, habito, registros, dia) -> dict:
        totales = self._totales(habito, registros)
        hoy_total = max(0, totales.get(dia.isoformat(), 0))
        objetivo = habito["objetivo"]

        # Racha: días seguidos cumpliendo el objetivo. Si hoy aún no se ha cumplido, no rompe la racha de ayer.
        cursor = dia if hoy_total >= objetivo else dia - timedelta(days=1)
        racha = 0

        while totales.get(cursor.isoformat(), 0) >= objetivo:
            racha += 1
            cursor -= timedelta(days=1)

        return {
            "habito": habito["nombre"],
            "hoy": hoy_total,
            "objetivo": objetivo,
            "unidad": habito.get("unidad", ""),
            "hora": habito.get("hora", ""),
            "persona": habito.get("persona", ""),
            "cumplido": hoy_total >= objetivo,
            "racha_dias": racha,
            "hora": habito.get("hora", ""),
            "persona": habito.get("persona", ""),
        }

    def estado(self, fecha=None, persona=None) -> dict:
        dia = date.fromisoformat(validar_fecha(fecha))
        registros = self.obtener_seccion("registros")
        habitos = self.obtener_seccion("habitos")

        if persona:
            clave = normalizar(persona)
            habitos = [h for h in habitos if not h.get("persona") or normalizar(h["persona"]) == clave]

        lista = [self._estado_de(h, registros, dia) for h in habitos]

        return {
            "fecha": dia.isoformat(),
            "habitos": lista,
            "cumplidos": sum(1 for h in lista if h["cumplido"]),
            "total": len(lista),
        }

    def borrar(self, nombre) -> dict:
        habito = self._buscar(nombre)
        self.guardar_seccion("habitos", [h for h in self.obtener_seccion("habitos") if h["nombre"] != habito["nombre"]])
        self.guardar_seccion("registros", [r for r in self.obtener_seccion("registros") if r.get("habito") != habito["nombre"]])

        return habito

    def avisar_pendientes(self, ahora=None) -> int:
        """Recuerda (una vez al día por hábito) los hábitos con hora cuya hora ya ha pasado y siguen sin cumplirse."""

        ahora = ahora or datetime.now()
        hoy = ahora.date().isoformat()
        datos = self.data.leer_modulo(self.nombre)
        avisados = {k: v for k, v in (datos.get("_avisados") or {}).items() if v == hoy}
        pendientes = [h for h in self.estado(hoy)["habitos"] if h["hora"] and h["hora"] <= ahora.strftime("%H:%M") and not h["cumplido"] and h["habito"] not in avisados]

        if not pendientes:
            return 0

        from brain.modules.avisos import Avisos

        avisos = Avisos()

        for h in pendientes:
            avisados[h["habito"]] = hoy
            quien = f" ({h['persona']})" if h["persona"] else ""
            avisos.avisar(f"Hábito: {h['habito']}{quien}", f"Hoy llevas {h['hoy']} de {h['objetivo']} {h['unidad']}".strip() + ".", tipo="recordatorio")

        datos["_avisados"] = avisados
        self.data.guardar_modulo(self.nombre, datos)

        return len(pendientes)

    def avisar_pendientes(self, ahora=None) -> int:
        """Avisa (una vez al día por hábito) de los hábitos con hora que ya tocaban y no están cumplidos."""

        from datetime import datetime

        ahora = ahora or datetime.now()
        hoy = ahora.date()
        minutos = ahora.hour * 60 + ahora.minute
        avisados = [a for a in self.obtener_seccion("avisados") if str(a).startswith(hoy.isoformat())]
        registros = self.obtener_seccion("registros")
        enviados = 0

        for habito in self.obtener_seccion("habitos"):
            hora = habito.get("hora")

            if not hora:
                continue

            h, m = hora.split(":")
            clave = f"{hoy.isoformat()}|{habito['nombre']}"

            if minutos < int(h) * 60 + int(m) or clave in avisados:
                continue

            if self._estado_de(habito, registros, hoy)["cumplido"]:
                continue

            avisados.append(clave)
            enviados += 1

            from brain.modules.avisos import Avisos

            quien = f" ({habito['persona']})" if habito.get("persona") else ""
            Avisos().avisar(f"Hábito: {habito['nombre']}{quien}", "Aún no lo has apuntado hoy.", tipo="recordatorio")

        self.guardar_seccion("avisados", avisados)

        return enviados
