"""
Resumen diario proactivo: cada mañana BRAIN junta lo importante del día
(agenda, recordatorios, compra, energía, alertas, garantías y peso) y lo
envía como aviso. También se puede pedir en cualquier momento.
"""

from datetime import date, datetime, timedelta
from typing import List, Optional

from brain.base.modulo import ModuloBase
from brain.modules.avisos import Avisos, _hora_a_minutos
from brain.utils.fechas import DIAS

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)  # fmt: skip

CONFIG_POR_DEFECTO = {"activo": True, "hora": "08:30", "ultimo_envio": None}

# Pasada esta hora ya no se envía el resumen "de la mañana" atrasado.
HORA_LIMITE = "21:00"


def fecha_larga(dia: date) -> str:
    return f"{DIAS[dia.weekday()]} {dia.day} de {MESES[dia.month - 1]}"


def _lista(elementos: List[str], maximo=6) -> str:
    if len(elementos) <= maximo:
        return ", ".join(elementos)

    return ", ".join(elementos[:maximo]) + f" y {len(elementos) - maximo} más"


class Resumen(ModuloBase):
    nombre = "resumen"

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------

    def configuracion(self) -> dict:
        guardada = self.data.leer_modulo(self.nombre)

        return {**CONFIG_POR_DEFECTO, **{k: v for k, v in guardada.items() if k in CONFIG_POR_DEFECTO}}

    def configurar(self, activo=None, hora=None) -> dict:
        config = self.configuracion()

        if activo is not None:
            config["activo"] = bool(activo)

        if hora not in (None, ""):
            try:
                _hora_a_minutos(hora)
            except ValueError:
                raise ValueError("La hora del resumen debe ser HH:MM, por ejemplo 08:30.") from None

            horas, minutos = str(hora).replace(".", ":").split(":")
            config["hora"] = f"{int(horas):02d}:{int(minutos):02d}"

        self.data.guardar_modulo(self.nombre, config)

        return {"activo": config["activo"], "hora": config["hora"]}

    # ------------------------------------------------------------------
    # Composición
    # ------------------------------------------------------------------

    def componer(self, hoy: Optional[date] = None) -> dict:
        """Devuelve {"titulo", "texto", "secciones"} con lo importante del día."""

        from brain.core.scheduler import sondeo
        from brain.modules.calendario import Calendario
        from brain.modules.compras import Compras
        from brain.modules.electrodomesticos import Electrodomesticos
        from brain.modules.salud import Salud

        hoy = hoy or date.today()
        secciones = {}

        # Agenda de hoy y mañana + tareas
        agenda = Calendario().agenda(1)
        manana = (hoy + timedelta(days=1)).isoformat()
        eventos_hoy = [e for e in agenda["eventos"] if e.get("fecha") == hoy.isoformat()]
        eventos_manana = [e for e in agenda["eventos"] if e.get("fecha") == manana]

        def evento(e):
            return f"{e['hora']} {e['titulo']}" if e.get("hora") else e["titulo"]

        lineas = []

        if eventos_hoy:
            lineas.append("Hoy: " + _lista([evento(e) for e in eventos_hoy]) + ".")

        if eventos_manana:
            lineas.append("Mañana: " + _lista([evento(e) for e in eventos_manana]) + ".")

        if agenda["tareas_pendientes"]:
            lineas.append("Tareas pendientes: " + _lista([t["titulo"] for t in agenda["tareas_pendientes"]]) + ".")

        secciones["agenda"] = lineas or ["No tienes nada en la agenda para hoy ni mañana."]

        # Recordatorios de hoy
        recordatorios = [r for r in Avisos().recordatorios() if r["cuando"].startswith(hoy.isoformat())]

        if recordatorios:
            secciones["recordatorios"] = [
                "Recordatorios de hoy: " + _lista([f"{r['cuando'][11:16]} {r['mensaje']}" for r in recordatorios]) + "."
            ]

        # Lista de la compra
        compra = Compras().lista()

        if compra:
            secciones["compra"] = [f"Lista de la compra ({len(compra)}): " + _lista([i["producto"] for i in compra]) + "."]

        # Energía de ayer
        ayer = (hoy - timedelta(days=1)).isoformat()
        produccion = [r for r in self._produccion() if r["fecha"] == ayer]

        if produccion:
            secciones["energia"] = [f"Ayer las placas produjeron {produccion[0]['produccion']:g} kWh."]

        # Alertas activas de Home Assistant
        if sondeo.alertas:
            secciones["alertas"] = [
                "ATENCIÓN, sensores en alerta: " + _lista([a["nombre"] for a in sondeo.alertas]) + "."
            ]

        # Garantías
        garantias = Electrodomesticos().garantias_por_caducar(30, hoy)

        if garantias:
            secciones["garantias"] = [
                "Garantías que caducan pronto: " + _lista([f"{a['nombre']} ({a['garantia_hasta']})" for a in garantias]) + "."
            ]

        # Peso
        historial = Salud().historial_peso()

        if historial:
            ultimo = historial[-1]
            frase = f"Último peso: {ultimo['peso']:g} kg ({ultimo['fecha']})."
            semana = [r for r in historial if r["fecha"] <= (hoy - timedelta(days=7)).isoformat()]

            if semana:
                diferencia = round(ultimo["peso"] - semana[-1]["peso"], 1)

                if diferencia:
                    frase += f" {diferencia:+g} kg respecto a hace una semana."

            secciones["peso"] = [frase]

        titulo = f"Buenos días: {fecha_larga(hoy)}"
        texto = "\n".join(linea for lineas in secciones.values() for linea in lineas)

        return {"titulo": titulo, "texto": texto, "secciones": secciones}

    @staticmethod
    def _produccion():
        from brain.modules.energia import Energia

        return Energia().db.produccion(3)

    # ------------------------------------------------------------------
    # Envío
    # ------------------------------------------------------------------

    def enviar(self) -> dict:
        """Compone el resumen y lo envía como aviso (con el sonido de tipo 'resumen')."""

        resumen = self.componer()
        hay_alerta = "alertas" in resumen["secciones"]

        Avisos().avisar(resumen["titulo"], resumen["texto"], tipo="resumen", nivel="importante" if hay_alerta else "info")

        config = self.configuracion()
        config["ultimo_envio"] = date.today().isoformat()
        self.data.guardar_modulo(self.nombre, config)

        return resumen

    def enviar_si_toca(self, ahora: Optional[datetime] = None) -> Optional[dict]:
        """Lo envía una vez al día, a su hora (o al arrancar si BRAIN estaba apagado a esa hora)."""

        ahora = ahora or datetime.now()
        config = self.configuracion()

        if not config["activo"] or config["ultimo_envio"] == ahora.date().isoformat():
            return None

        minuto = ahora.hour * 60 + ahora.minute

        if not (_hora_a_minutos(config["hora"]) <= minuto < _hora_a_minutos(HORA_LIMITE)):
            return None

        return self.enviar()
