from datetime import date, timedelta

from brain.base.modulo import ModuloBase
from brain.modules.inventario import normalizar
from brain.utils.fechas import validar_fecha


class Hogar(ModuloBase):
    """
    Tareas del hogar que se repiten (sacar la basura, fregar, bajar al perro...)
    con turnos: cada vez que alguien la hace, le toca a la siguiente persona.
    """

    nombre = "hogar"

    def _buscar(self, nombre, tareas):
        clave = normalizar(nombre)

        if not clave:
            raise ValueError("Indica el nombre de la tarea.")

        exacta = [t for t in tareas if normalizar(t["nombre"]) == clave]
        parecidas = exacta or [t for t in tareas if clave in normalizar(t["nombre"]) or normalizar(t["nombre"]) in clave]

        if len(parecidas) == 1:
            return parecidas[0]

        if len(parecidas) > 1:
            raise ValueError("Hay varias tareas que encajan: " + ", ".join(t["nombre"] for t in parecidas) + ". Indica cuál.")

        raise ValueError(f"No tengo la tarea '{nombre}'.")

    def crear(self, nombre, personas="", cada_dias=7, empieza=None) -> dict:
        nombre = str(nombre or "").strip()[:50]

        if not nombre:
            raise ValueError("Indica el nombre de la tarea.")

        if isinstance(personas, str):
            personas = [p.strip() for p in personas.replace(" y ", ",").replace(";", ",").split(",")]

        personas = [str(p).strip()[:30] for p in personas if str(p).strip()]

        try:
            cada_dias = int(float(cada_dias))
        except (TypeError, ValueError):
            raise ValueError("Cada cuántos días se repite debe ser un número.") from None

        if not 1 <= cada_dias <= 365:
            raise ValueError("La repetición debe estar entre 1 y 365 días.")

        tareas = self.obtener_seccion("tareas")
        existente = next((t for t in tareas if normalizar(t["nombre"]) == normalizar(nombre)), None)
        if personas:
            from brain.modules.perfiles import Perfiles

            for persona in personas:
                Perfiles().añadir(persona)

        tarea = existente if existente is not None else {"nombre": nombre, "turno": 0, "historial": []}

        tarea.update({"personas": personas, "cada_dias": cada_dias, "proxima": validar_fecha(empieza)})
        tarea["turno"] = tarea.get("turno", 0) % len(personas) if personas else 0

        if existente is None:
            tareas.append(tarea)

        self.guardar_seccion("tareas", tareas)

        return self._vista(tarea)

    @staticmethod
    def _vista(tarea, hoy=None) -> dict:
        hoy = hoy or date.today()
        personas = tarea.get("personas") or []
        proxima = tarea.get("proxima") or hoy.isoformat()

        return {
            "nombre": tarea["nombre"],
            "le_toca_a": personas[tarea.get("turno", 0) % len(personas)] if personas else "",
            "personas": personas,
            "cada_dias": tarea.get("cada_dias", 7),
            "proxima": proxima,
            "toca_hoy": proxima <= hoy.isoformat(),
            "ultima": (tarea.get("historial") or [{}])[-1] if tarea.get("historial") else None,
        }

    def listar(self) -> list:
        return sorted((self._vista(t) for t in self.obtener_seccion("tareas")), key=lambda t: (t["proxima"], normalizar(t["nombre"])))

    def hecha(self, nombre, quien="", fecha=None) -> dict:
        """Apunta que se ha hecho. Pasa el turno a la siguiente persona y programa la próxima vez."""

        tareas = self.obtener_seccion("tareas")
        tarea = self._buscar(nombre, tareas)
        personas = tarea.get("personas") or []
        dia = date.fromisoformat(validar_fecha(fecha))
        hizo = str(quien or "").strip()

        if not hizo and personas:
            hizo = personas[tarea.get("turno", 0) % len(personas)]

        if personas:
            if hizo and normalizar(hizo) in [normalizar(p) for p in personas]:
                indice = [normalizar(p) for p in personas].index(normalizar(hizo))
            else:
                indice = tarea.get("turno", 0)

            tarea["turno"] = (indice + 1) % len(personas)

        tarea.setdefault("historial", []).append({"fecha": dia.isoformat(), "quien": hizo})
        tarea["historial"] = tarea["historial"][-30:]
        tarea["proxima"] = (dia + timedelta(days=tarea.get("cada_dias", 7))).isoformat()
        self.guardar_seccion("tareas", tareas)

        return self._vista(tarea)

    def saltar_turno(self, nombre) -> dict:
        tareas = self.obtener_seccion("tareas")
        tarea = self._buscar(nombre, tareas)
        personas = tarea.get("personas") or []

        if len(personas) < 2:
            raise ValueError("Esa tarea no tiene más personas para pasar el turno.")

        tarea["turno"] = (tarea.get("turno", 0) + 1) % len(personas)
        self.guardar_seccion("tareas", tareas)

        return self._vista(tarea)

    def borrar(self, nombre) -> dict:
        tareas = self.obtener_seccion("tareas")
        tarea = self._buscar(nombre, tareas)
        tareas.remove(tarea)
        self.guardar_seccion("tareas", tareas)

        return {"nombre": tarea["nombre"]}

    def de_hoy(self, persona="") -> list:
        lista = [t for t in self.listar() if t["toca_hoy"]]

        if persona:
            lista = [t for t in lista if not t["le_toca_a"] or normalizar(t["le_toca_a"]) == normalizar(persona)]

        return lista

    def avisar_de_hoy(self) -> int:
        """Un aviso al día por cada tarea que toca (a quien le corresponde)."""

        hoy = date.today().isoformat()
        avisadas = [a for a in self.obtener_seccion("avisadas") if str(a).startswith(hoy)]
        enviados = 0

        for tarea in self.de_hoy():
            clave = f"{hoy}|{tarea['nombre']}|{tarea['proxima']}"

            if clave in avisadas:
                continue

            avisadas.append(clave)
            enviados += 1

            from brain.modules.avisos import Avisos

            quien = f"Le toca a {tarea['le_toca_a']}." if tarea["le_toca_a"] else "Toca hacerla hoy."
            Avisos().avisar(f"Tarea del hogar: {tarea['nombre']}", quien, tipo="recordatorio")

        self.guardar_seccion("avisadas", avisadas)

        return enviados
