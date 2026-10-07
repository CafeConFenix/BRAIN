from datetime import date, timedelta

from brain.base.modulo import ModuloBase
from brain.modules.inventario import normalizar
from brain.utils.fechas import hoy, validar_fecha


def _hora_valida(hora):
    if hora in (None, ""):
        return None

    texto = str(hora).strip().replace(".", ":")

    try:
        horas, minutos = texto.split(":")
        horas, minutos = int(horas), int(minutos)
    except ValueError:
        raise ValueError(f"La hora '{hora}' no es válida. Usa el formato HH:MM, por ejemplo 18:30.") from None

    if not (0 <= horas <= 23 and 0 <= minutos <= 59):
        raise ValueError(f"La hora '{hora}' no es válida.")

    return f"{horas:02d}:{minutos:02d}"


class Calendario(ModuloBase):
    nombre = "calendario"

    def añadir_evento(self, titulo, fecha=None, hora=None):
        evento = {
            "titulo": str(titulo).strip(),
            "fecha": validar_fecha(fecha),
            "hora": _hora_valida(hora),
        }

        self.añadir_registro("eventos", evento)

        return evento

    def añadir_tarea(self, titulo, fecha=None):
        tarea = {
            "titulo": str(titulo).strip(),
            "fecha": validar_fecha(fecha, defecto_hoy=False),
            "hecha": False,
        }

        self.añadir_registro("tareas", tarea)

        return tarea

    def completar_tarea(self, titulo):
        tareas = self.obtener_seccion("tareas")

        for tarea in tareas:
            if not tarea.get("hecha") and normalizar(titulo) in normalizar(tarea.get("titulo", "")):
                tarea["hecha"] = True
                tarea["completada"] = hoy()

                self.guardar_seccion("tareas", tareas)

                return tarea

        raise ValueError(f"No encuentro ninguna tarea pendiente que se llame '{titulo}'.")

    def tareas_pendientes(self):
        return [t for t in self.obtener_seccion("tareas") if not t.get("hecha")]

    def agenda(self, dias=7):
        """Eventos de los próximos N días y tareas pendientes."""

        dias = int(dias)

        inicio = date.today()
        fin = inicio + timedelta(days=dias)

        eventos = [e for e in self.obtener_seccion("eventos") if inicio.isoformat() <= e.get("fecha", "") <= fin.isoformat()]

        eventos.sort(key=lambda e: (e.get("fecha", ""), e.get("hora") or ""))

        return {
            "desde": inicio.isoformat(),
            "hasta": fin.isoformat(),
            "eventos": eventos,
            "tareas_pendientes": self.tareas_pendientes(),
        }
