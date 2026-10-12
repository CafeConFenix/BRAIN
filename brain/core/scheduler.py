"""
Planificador de tareas en segundo plano de BRAIN (solo biblioteca estándar).

Un único hilo demonio ejecuta tareas periódicas. Cualquier excepción de una
tarea se captura y se anota en su estado: nunca detiene el hilo ni la
aplicación. Al ser demonio, no impide que BRAIN se cierre.
"""

import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Callable, Dict, List, Optional

from brain.core.config import Config

DIAS_HISTORIAL_ENERGIA = 365

# Tipos de sensor de Home Assistant que avisan de peligros.
CLASES_CRITICAS = ("smoke", "gas", "carbon_monoxide", "moisture", "safety", "heat", "problem")


class Tarea:
    """Una tarea periódica y su estado."""

    def __init__(self, nombre: str, funcion: Callable, intervalo: float, retraso_inicial: float = 0.0):
        self.nombre = nombre
        self.funcion = funcion
        self.intervalo = max(0.01, float(intervalo))
        self.proxima = time.monotonic() + max(0.0, float(retraso_inicial))
        self.activa = True
        self.ejecuciones = 0
        self.errores = 0
        self.ultima_ejecucion: Optional[str] = None
        self.ultimo_resultado = None
        self.ultimo_error: Optional[str] = None

    def estado(self) -> dict:
        return {
            "nombre": self.nombre,
            "cada_segundos": self.intervalo,
            "activa": self.activa,
            "ejecuciones": self.ejecuciones,
            "errores": self.errores,
            "ultima_ejecucion": self.ultima_ejecucion,
            "ultimo_error": self.ultimo_error,
        }


class Planificador:
    """Ejecuta tareas periódicas en un hilo aparte."""

    def __init__(self, nombre_hilo: str = "brain-planificador"):  # noqa: D107
        self._tareas: Dict[str, Tarea] = {}
        self._bloqueo = threading.RLock()
        self._parar = threading.Event()
        self._despertar = threading.Event()
        self._hilo: Optional[threading.Thread] = None
        self._nombre_hilo = nombre_hilo
        self.alertas: List[dict] = []

    # ------------------------------------------------------------------
    # Registro
    # ------------------------------------------------------------------

    def registrar(
        self,
        nombre: str,
        funcion: Callable,
        segundos: Optional[float] = None,
        horas: Optional[float] = None,
        retraso_inicial: float = 0.0,
    ) -> Tarea:
        """
        Registra (o sustituye) una tarea periódica. El intervalo se da en
        `segundos` y/o `horas` (se suman). `retraso_inicial` son segundos
        hasta la primera ejecución.
        """

        intervalo = float(segundos or 0) + float(horas or 0) * 3600

        if intervalo <= 0:
            raise ValueError("El intervalo debe ser mayor que cero (segundos u horas).")

        tarea = Tarea(nombre, funcion, intervalo, retraso_inicial)

        with self._bloqueo:
            self._tareas[nombre] = tarea

        self._despertar.set()

        return tarea

    def quitar(self, nombre: str) -> bool:
        with self._bloqueo:
            return self._tareas.pop(nombre, None) is not None

    def estado(self) -> List[dict]:
        with self._bloqueo:
            return [t.estado() for t in self._tareas.values()]

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------

    @property
    def activo(self) -> bool:
        return self._hilo is not None and self._hilo.is_alive()

    def iniciar(self) -> None:
        """Arranca el hilo (si ya está en marcha no hace nada). No bloquea."""

        if self.activo:
            return

        self._parar.clear()
        self._hilo = threading.Thread(target=self._bucle, name=self._nombre_hilo, daemon=True)
        self._hilo.start()

    def detener(self, esperar: float = 2.0) -> None:
        self._parar.set()
        self._despertar.set()

        if self._hilo is not None:
            self._hilo.join(timeout=esperar)

    def ejecutar_ahora(self, nombre: str) -> dict:
        """Ejecuta una tarea ya (en el hilo que llama) con la misma protección de errores."""

        with self._bloqueo:
            tarea = self._tareas.get(nombre)

        if tarea is None:
            raise KeyError(f"No existe la tarea '{nombre}'.")

        self._ejecutar(tarea)

        return tarea.estado()

    def _ejecutar(self, tarea: Tarea) -> None:
        try:
            tarea.ultimo_resultado = tarea.funcion()
            tarea.ultimo_error = None
        except Exception as error:  # una tarea nunca debe tumbar el hilo
            tarea.errores += 1
            tarea.ultimo_error = f"{type(error).__name__}: {error}"

            if getattr(Config, "DEPURAR", False):
                traceback.print_exc()
        finally:
            tarea.ejecuciones += 1
            tarea.ultima_ejecucion = datetime.now().isoformat(timespec="seconds")
            tarea.proxima = time.monotonic() + tarea.intervalo

    def _bucle(self) -> None:
        while not self._parar.is_set():
            try:
                with self._bloqueo:
                    tareas = list(self._tareas.values())

                ahora = time.monotonic()
                espera = 30.0

                for tarea in tareas:
                    if self._parar.is_set():
                        return

                    if not tarea.activa:
                        continue

                    if tarea.proxima <= ahora:
                        self._ejecutar(tarea)

                    espera = min(espera, max(0.05, tarea.proxima - time.monotonic()))

                self._despertar.clear()
                self._despertar.wait(timeout=espera)

            except Exception:  # defensa final: el bucle sigue pase lo que pase
                self._parar.wait(1.0)


# ----------------------------------------------------------------------
# Tareas por defecto
# ----------------------------------------------------------------------


def copia_diaria() -> str:
    """Crea la copia de seguridad si la última tiene más de 20 horas."""

    from brain.modules.sistema import Sistema

    copia = Sistema().copia_si_toca(horas=20)

    return f"copia creada: {copia['archivo']}" if copia else "ya había una copia reciente"


class SondeoHomeAssistant:
    """
    Sondeo periódico de Home Assistant (si está configurado):
    guarda en SQLite la lectura de energía y vigila los sensores críticos
    (humo, gas, fuga de agua...). Es un callable para usarlo como tarea.
    """

    def __init__(self):
        self.alertas: List[dict] = []
        self.ultima_comprobacion: Optional[str] = None
        self._avisadas: set = set()  # alertas ya notificadas mientras siguen activas

    def __call__(self) -> str:
        from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError, leer_configuracion

        url, token = leer_configuracion()
        ha = HomeAssistant(url, token, timeout=8)

        if not ha.configurado:
            self.alertas = []
            return "Home Assistant no está configurado"

        try:
            estados = ha.estados()
        except HomeAssistantError as error:
            raise RuntimeError(f"Home Assistant no responde: {error}")

        alertas = []

        for estado in estados:
            entidad = estado.get("entity_id", "")
            atributos = estado.get("attributes") or {}

            if entidad.startswith("binary_sensor.") and atributos.get("device_class") in CLASES_CRITICAS:
                if estado.get("state") == "on":
                    alertas.append(
                        {
                            "entidad": entidad,
                            "nombre": atributos.get("friendly_name", entidad),
                            "tipo": atributos.get("device_class"),
                            "desde": estado.get("last_changed"),
                        }
                    )

        self.alertas = alertas
        self.ultima_comprobacion = datetime.now().isoformat(timespec="seconds")

        self._notificar_alertas_nuevas(alertas)

        from brain.modules.energia import Energia
        from brain.tools.builtin.energia import tiempo_real

        energia = Energia()
        guardada = energia.registrar_lectura(tiempo_real.leer())

        # Mantenimiento: no dejar crecer el histórico sin límite.
        limite = (datetime.now() - timedelta(days=DIAS_HISTORIAL_ENERGIA)).isoformat(timespec="seconds")
        energia.db.depurar_energia(limite)

        return f"{len(alertas)} alertas, energía {'guardada' if guardada else 'sin datos'}"


    def _notificar_alertas_nuevas(self, alertas: List[dict]) -> None:
        """Avisa (con sonido) de cada alerta que aparece; si se apaga y vuelve, avisa otra vez."""

        from brain.modules.avisos import Avisos

        activas = {a["entidad"] for a in alertas}
        self._avisadas &= activas

        for alerta in alertas:
            if alerta["entidad"] in self._avisadas:
                continue

            self._avisadas.add(alerta["entidad"])
            etiqueta = ETIQUETAS_ALERTA.get(alerta.get("tipo"), "Alerta")
            Avisos().avisar(f"{etiqueta}: {alerta['nombre']}", "Revisa la casa cuanto antes.", tipo="alerta", nivel="critico")


ETIQUETAS_ALERTA = {
    "smoke": "Humo detectado",
    "gas": "Gas detectado",
    "carbon_monoxide": "Monóxido de carbono",
    "moisture": "Fuga de agua",
    "safety": "Alerta de seguridad",
    "heat": "Calor excesivo",
    "problem": "Problema",
}


def revisar_recordatorios() -> str:
    """Lanza los recordatorios que ya tocan."""

    from brain.modules.avisos import Avisos

    return f"{Avisos().revisar_recordatorios()} recordatorios"


class AvisoEventos:
    """Avisa de los eventos de la agenda con hora, MINUTOS_ANTES de que empiecen."""

    MINUTOS_ANTES = 30

    def __init__(self):
        self._avisados: set = set()

    def __call__(self) -> str:
        from brain.modules.avisos import Avisos
        from brain.modules.calendario import Calendario

        ahora = datetime.now()
        hoy = ahora.date().isoformat()
        enviados = 0

        for evento in Calendario().obtener_seccion("eventos"):
            if evento.get("fecha") != hoy or not evento.get("hora"):
                continue

            clave = (evento["fecha"], evento["hora"], evento.get("titulo"))

            if clave in self._avisados:
                continue

            try:
                inicio = datetime.strptime(f"{evento['fecha']} {evento['hora']}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue

            faltan = (inicio - ahora).total_seconds() / 60

            if 0 <= faltan <= self.MINUTOS_ANTES:
                self._avisados.add(clave)
                Avisos().avisar(
                    evento.get("titulo", "Evento"),
                    f"Empieza a las {evento['hora']} (en {round(faltan)} min).",
                    tipo="recordatorio",
                    nivel="importante",
                )
                enviados += 1

        return f"{enviados} avisos de agenda"


class MotorAutomatizaciones:
    """Evalúa las automatizaciones (hora, sensores y energía). Conserva el estado entre comprobaciones."""

    def __init__(self):
        self._motor = None

    def __call__(self) -> str:
        if self._motor is None:
            from brain.modules.automatizaciones import Automatizaciones

            self._motor = Automatizaciones()

        hechas = self._motor.evaluar()

        return f"{len(hechas)} ejecutadas" + (": " + "; ".join(hechas) if hechas else "")


def resumen_diario() -> str:
    """Envía el resumen de la mañana (una vez al día, a su hora)."""

    from brain.modules.resumen import Resumen

    return "resumen enviado" if Resumen().enviar_si_toca() else "sin novedades"


def mantenimiento() -> str:
    """Limpieza diaria de avisos antiguos."""

    from brain.modules.avisos import Avisos

    return f"{Avisos().depurar(90)} avisos antiguos borrados"


planificador = Planificador()
sondeo = SondeoHomeAssistant()


def registrar_tareas_por_defecto(plan: Planificador) -> Planificador:
    """Añade la copia diaria y el sondeo de Home Assistant."""

    plan.registrar("copia_diaria", copia_diaria, horas=24, retraso_inicial=60)
    plan.registrar("sondeo_home_assistant", sondeo, segundos=Config.SONDEO_SEGUNDOS, retraso_inicial=15)
    plan.registrar("recordatorios", revisar_recordatorios, segundos=15, retraso_inicial=5)
    plan.registrar("aviso_eventos", AvisoEventos(), segundos=60, retraso_inicial=20)
    plan.registrar("automatizaciones", MotorAutomatizaciones(), segundos=30, retraso_inicial=10)
    plan.registrar("resumen_diario", resumen_diario, segundos=60, retraso_inicial=30)
    plan.registrar("mantenimiento", mantenimiento, horas=24, retraso_inicial=300)

    return plan


def iniciar_planificador() -> Planificador:
    """Arranca el planificador global con las tareas por defecto (si no está desactivado)."""

    if Config.PLANIFICADOR and not planificador.activo:
        registrar_tareas_por_defecto(planificador)
        planificador.iniciar()

    return planificador


Scheduler = Planificador  # nombre alternativo en inglés
