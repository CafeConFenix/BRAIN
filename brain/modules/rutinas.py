from datetime import date

from brain.base.modulo import ModuloBase
from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.calendario import Calendario
from brain.modules.domotica import Domotica

TIPOS = ("salgo", "noches")


class Rutinas(ModuloBase):
    """
    Los botones "Salgo de casa" y "Buenas noches": primero se REVISA lo que hay
    encendido y lo pendiente; solo se apaga lo que la persona confirma.
    """

    nombre = "rutinas"

    def __init__(self):
        super().__init__()
        self.domotica = Domotica()

    def revisar(self, tipo="salgo") -> dict:
        if tipo not in TIPOS:
            raise ValueError("La rutina debe ser 'salgo' o 'noches'.")

        resultado = {"tipo": tipo, "conectado": bool(self.domotica.conectado()), "encendidos": [], "recordatorios": []}

        if resultado["conectado"]:
            try:
                resultado["encendidos"] = self.domotica.encendidos()["encendidos"]
            except HomeAssistantError as error:
                resultado["error"] = str(error)

        calendario = Calendario()
        hoy = date.today().isoformat()

        if tipo == "salgo":
            tareas = [t["titulo"] for t in calendario.tareas_pendientes() if t.get("fecha") in (None, "", hoy) or t.get("fecha", "") < hoy]
            resultado["recordatorios"] = tareas[:5]
        else:
            manana = calendario.agenda(2)["eventos"]
            resultado["recordatorios"] = [f"{e['fecha']} {e.get('hora') or ''} {e['titulo']}".replace("  ", " ").strip() for e in manana if e["fecha"] > hoy][:5]

        return resultado

    def apagar(self, entidades) -> dict:
        """Apaga las entidades indicadas (solo las que BRAIN puede controlar). Devuelve qué se apagó y qué falló."""

        apagadas, fallos = [], []

        for entidad in list(entidades or [])[:100]:
            try:
                self.domotica.conmutar(str(entidad), False)
                apagadas.append(entidad)
            except HomeAssistantError as error:
                fallos.append({"entidad": entidad, "error": str(error)})

        return {"apagadas": apagadas, "fallos": fallos}
