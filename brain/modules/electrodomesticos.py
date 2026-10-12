"""
Registro de electrodomésticos: qué aparatos hay en casa, su marca y modelo,
cuándo se compraron y hasta cuándo dura la garantía. Si el usuario guarda los
manuales en datos/documentos/, BRAIN los consulta para diagnosticar fallos.
"""

import calendar
from datetime import date, datetime, timedelta
from typing import List, Optional

from brain.base.modulo import ModuloBase
from brain.modules.documentos import DocumentoError, Documentos
from brain.modules.inventario import mismo_producto, normalizar
from brain.utils.fechas import validar_fecha


def sumar_meses(fecha: date, meses: int) -> date:
    mes = fecha.month - 1 + int(meses)
    anio = fecha.year + mes // 12
    mes = mes % 12 + 1

    return date(anio, mes, min(fecha.day, calendar.monthrange(anio, mes)[1]))


class Electrodomesticos(ModuloBase):
    nombre = "electrodomesticos"

    def aparatos(self) -> List[dict]:
        return self.obtener_seccion("aparatos")

    def _buscar(self, aparatos, nombre) -> dict:
        clave = normalizar(nombre)

        for a in aparatos:
            if normalizar(a["nombre"]) == clave:
                return a

        parciales = [a for a in aparatos if mismo_producto(nombre, a["nombre"]) or (clave and clave in normalizar(f"{a['nombre']} {a.get('marca') or ''} {a.get('modelo') or ''}"))]

        if len(parciales) == 1:
            return parciales[0]

        if len(parciales) > 1:
            raise ValueError(f"'{nombre}' encaja con varios: {', '.join(a['nombre'] for a in parciales)}. Dime cuál.")

        existentes = ", ".join(a["nombre"] for a in aparatos) or "ninguno"
        raise ValueError(f"No tengo registrado ningún electrodoméstico '{nombre}'. Registrados: {existentes}.")

    def guardar(self, nombre, marca=None, modelo=None, ubicacion=None, fecha_compra=None, garantia_meses=None, notas=None) -> dict:
        """Registra un aparato o, si ya existía, completa sus datos (sin borrar lo que no se mencione)."""

        nombre = str(nombre or "").strip()

        if not nombre:
            raise ValueError("Falta el nombre del electrodoméstico (lavadora, nevera, horno...).")

        aparatos = self.aparatos()
        existente = next((a for a in aparatos if normalizar(a["nombre"]) == normalizar(nombre)), None)

        aparato = existente or {"nombre": nombre, "añadido": date.today().isoformat()}

        for campo, valor in (("marca", marca), ("modelo", modelo), ("ubicacion", ubicacion), ("notas", notas)):
            if valor not in (None, ""):
                aparato[campo] = str(valor).strip()

        if fecha_compra not in (None, ""):
            aparato["fecha_compra"] = validar_fecha(fecha_compra)

        if garantia_meses not in (None, ""):
            meses = int(float(garantia_meses))

            if not 0 < meses <= 600:
                raise ValueError("Los meses de garantía no parecen correctos.")

            if not aparato.get("fecha_compra"):
                aparato["fecha_compra"] = date.today().isoformat()

            aparato["garantia_hasta"] = sumar_meses(date.fromisoformat(aparato["fecha_compra"]), meses).isoformat()

        if existente is None:
            aparatos.append(aparato)

        self.guardar_seccion("aparatos", aparatos)

        return {**aparato, "actualizado": existente is not None}

    def quitar(self, nombre) -> dict:
        aparatos = self.aparatos()
        aparato = self._buscar(aparatos, nombre)

        self.guardar_seccion("aparatos", [a for a in aparatos if a is not aparato])

        return aparato

    @staticmethod
    def estado_garantia(aparato, hoy: Optional[date] = None) -> Optional[str]:
        hasta = aparato.get("garantia_hasta")

        if not hasta:
            return None

        dias = (date.fromisoformat(hasta) - (hoy or date.today())).days

        if dias < 0:
            return f"caducó el {hasta}"

        if dias <= 60:
            return f"caduca en {dias} días ({hasta})"

        return f"en garantía hasta el {hasta}"

    def listar(self) -> List[dict]:
        return [{**a, "garantia": self.estado_garantia(a)} for a in sorted(self.aparatos(), key=lambda a: normalizar(a["nombre"]))]

    def garantias_por_caducar(self, dias=30, hoy: Optional[date] = None) -> List[dict]:
        hoy = hoy or date.today()
        limite = hoy + timedelta(days=dias)

        return [
            a
            for a in self.aparatos()
            if a.get("garantia_hasta") and hoy <= date.fromisoformat(a["garantia_hasta"]) <= limite
        ]

    def consultar(self, nombre, problema=None) -> dict:
        """Ficha del aparato y fragmentos de sus manuales (si hay) relacionados con el problema."""

        aparato = self._buscar(self.aparatos(), nombre)
        ficha = {**aparato, "garantia": self.estado_garantia(aparato)}

        consulta = " ".join(str(x) for x in (aparato["nombre"], aparato.get("marca"), aparato.get("modelo"), problema) if x)

        try:
            fragmentos = Documentos().buscar(consulta, 4)
        except DocumentoError:
            fragmentos = []

        return {
            "aparato": ficha,
            "problema": problema,
            "fragmentos_de_manuales": fragmentos,
        }
