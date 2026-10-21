import re
from datetime import date

from brain.base.modulo import ModuloBase
from brain.modules.inventario import normalizar
from brain.utils.fechas import MESES, validar_fecha

CATEGORIAS = ("supermercado", "hogar", "facturas", "transporte", "ocio", "salud", "ropa", "restaurantes", "otros")

# Palabras que delatan la categoría de un gasto cuando el usuario no la dice.
PISTAS = {
    "supermercado": ("super", "mercadona", "lidl", "carrefour", "dia ", "aldi", "alcampo", "compra", "fruta", "verdura", "carne", "pescado"),
    "facturas": ("luz", "agua", "gas", "internet", "fibra", "movil", "telefono", "seguro", "alquiler", "hipoteca", "comunidad", "factura", "impuesto"),
    "transporte": ("gasolina", "diesel", "gasoil", "bus", "metro", "tren", "taxi", "uber", "parking", "peaje", "billete", "coche"),
    "ocio": ("cine", "teatro", "concierto", "netflix", "spotify", "juego", "libro", "viaje", "hotel", "gimnasio", "deporte"),
    "salud": ("farmacia", "medico", "dentista", "gafas", "fisio", "medicina", "analitica"),
    "ropa": ("ropa", "zapatos", "camiseta", "pantalon", "zara", "abrigo"),
    "restaurantes": ("restaurante", "cena", "comida fuera", "cafe", "bar", "pizza", "hamburguesa", "menu", "desayuno fuera", "cerveza"),
    "hogar": ("ikea", "muebles", "reparacion", "bricolaje", "leroy", "limpieza", "ferreteria", "decoracion", "electrodomestico"),
}


def _importe(valor) -> float:
    """Acepta 12, 12.5, '12,50', '12,50 €', '1.234,56'."""

    if isinstance(valor, (int, float)):
        numero = float(valor)
    else:
        texto = re.sub(r"[^\d,.\-]", "", str(valor or ""))

        if not texto:
            raise ValueError("Indica el importe del gasto.")

        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        elif texto.count(".") > 1:
            texto = texto.replace(".", "")

        try:
            numero = float(texto)
        except ValueError:
            raise ValueError(f"No entiendo el importe '{valor}'.") from None

    if not 0 < numero <= 1_000_000:
        raise ValueError("El importe debe ser mayor que cero (y razonable).")

    return round(numero, 2)


def adivinar_categoria(concepto) -> str:
    texto = f" {normalizar(concepto)} "

    for categoria, claves in PISTAS.items():
        if any(clave in texto for clave in claves):
            return categoria

    return "otros"


def _categoria(valor, concepto) -> str:
    if not valor:
        return adivinar_categoria(concepto)

    clave = normalizar(valor)

    for categoria in CATEGORIAS:
        if clave == categoria or clave.rstrip("s") == categoria.rstrip("s"):
            return categoria

    adivinada = adivinar_categoria(valor)

    return adivinada if adivinada != "otros" else clave[:30]


def interpretar_mes(valor=None) -> str:
    """'2026-10', 'octubre', 'este mes', 'mes pasado' -> 'AAAA-MM'."""

    hoy = date.today()

    if valor in (None, ""):
        return f"{hoy.year:04d}-{hoy.month:02d}"

    texto = normalizar(valor)

    if re.fullmatch(r"\d{4}-\d{1,2}", texto):
        anio, mes = texto.split("-")

        if 1 <= int(mes) <= 12:
            return f"{int(anio):04d}-{int(mes):02d}"

    if "pasado" in texto or "anterior" in texto:
        anio, mes = (hoy.year, hoy.month - 1) if hoy.month > 1 else (hoy.year - 1, 12)

        return f"{anio:04d}-{mes:02d}"

    for nombre, numero in MESES.items():
        if nombre in texto:
            return f"{hoy.year:04d}-{numero:02d}"

    return f"{hoy.year:04d}-{hoy.month:02d}"


class Gastos(ModuloBase):
    """Control sencillo de gastos del hogar: apuntar, ver el resumen del mes y borrar."""

    nombre = "gastos"

    def anadir(self, importe, concepto="", categoria="", fecha=None) -> dict:
        registros = self.obtener_seccion("gastos")
        concepto = str(concepto or "").strip()[:80]

        gasto = {
            "id": max([g.get("id", 0) for g in registros] + [0]) + 1,
            "fecha": validar_fecha(fecha),
            "importe": _importe(importe),
            "categoria": _categoria(categoria, concepto),
            "concepto": concepto,
        }

        registros.append(gasto)
        self.guardar_seccion("gastos", registros)
        self._avisar_presupuesto(gasto["fecha"][:7])

        return gasto

    # ------------------------------------------------------------------
    # Presupuesto mensual
    # ------------------------------------------------------------------

    def presupuesto(self) -> dict:
        """{'total': 800.0, 'categorias': {'ocio': 50.0}} (vacío si no hay presupuesto)."""

        config = self.obtener_seccion("presupuesto")

        return dict(config[0]) if config and isinstance(config[0], dict) else {}

    def configurar_presupuesto(self, total=None, categoria="", limite=None) -> dict:
        """Fija el presupuesto mensual total y/o el límite de una categoría. Con 0 se quita."""

        config = self.presupuesto()
        categorias = dict(config.get("categorias") or {})

        if total not in (None, ""):
            try:
                valor = float(str(total).replace(",", ".")) if not isinstance(total, (int, float)) else float(total)
            except ValueError:
                raise ValueError(f"No entiendo el presupuesto '{total}'. Escribe una cantidad en euros, por ejemplo 900.") from None

            if valor < 0:
                raise ValueError("El presupuesto no puede ser negativo.")

            if valor == 0:
                config.pop("total", None)
            else:
                config["total"] = round(valor, 2)

        if categoria:
            nombre = _categoria(categoria, categoria)

            if limite in (None, ""):
                raise ValueError("Indica el límite de esa categoría en euros.")

            valor = _importe(limite) if str(limite).strip() not in ("0", "0.0") else 0

            if valor == 0:
                categorias.pop(nombre, None)
            else:
                categorias[nombre] = valor

        config["categorias"] = categorias
        self.guardar_seccion("presupuesto", [config])

        return config

    @staticmethod
    def _nivel(gastado, limite) -> str:
        if not limite:
            return "sin_limite"

        if gastado >= limite:
            return "superado"

        return "aviso" if gastado >= limite * 0.8 else "ok"

    def estado_presupuesto(self, mes=None) -> dict:
        """Cuánto se lleva gastado respecto al presupuesto del mes (total y por categoría)."""

        mes = interpretar_mes(mes)
        config = self.presupuesto()
        resumen = self.resumen(mes)
        total_limite = config.get("total")
        categorias = []

        gastado_por = {c["categoria"]: c["total"] for c in resumen["por_categoria"]}

        for nombre, limite in sorted((config.get("categorias") or {}).items()):
            gastado = gastado_por.get(nombre, 0.0)
            categorias.append({"categoria": nombre, "limite": limite, "gastado": gastado, "porcentaje": round(gastado * 100 / limite), "nivel": self._nivel(gastado, limite)})

        return {
            "mes": mes,
            "configurado": bool(total_limite or categorias),
            "limite": total_limite,
            "gastado": resumen["total"],
            "queda": round(total_limite - resumen["total"], 2) if total_limite else None,
            "porcentaje": round(resumen["total"] * 100 / total_limite) if total_limite else None,
            "nivel": self._nivel(resumen["total"], total_limite),
            "categorias": categorias,
        }

    def _avisar_presupuesto(self, mes) -> None:
        """Avisa (una sola vez por mes y nivel) al llegar al 80 % y al 100 %."""

        try:
            estado = self.estado_presupuesto(mes)

            if not estado["configurado"]:
                return

            hechos = set(self.obtener_seccion("avisados"))
            pendientes = []
            situaciones = [("total", "el presupuesto del mes", estado["limite"], estado["gastado"], estado["nivel"])]
            situaciones += [(c["categoria"], f"el presupuesto de {c['categoria']}", c["limite"], c["gastado"], c["nivel"]) for c in estado["categorias"]]

            for clave, texto, limite, gastado, nivel in situaciones:
                if nivel not in ("aviso", "superado"):
                    continue

                marca = f"{mes}:{clave}:{nivel}"

                if marca in hechos:
                    continue

                hechos.add(marca)
                pendientes.append((nivel, texto, limite, gastado))

            if not pendientes:
                return

            self.guardar_seccion("avisados", sorted(hechos)[-200:])

            from brain.modules.avisos import Avisos

            avisos = Avisos()

            for nivel, texto, limite, gastado in pendientes:
                if nivel == "superado":
                    avisos.avisar("Presupuesto superado", f"Has gastado {gastado:.2f} € y {texto} era de {limite:.2f} €.", tipo="alerta")
                else:
                    avisos.avisar("Presupuesto al 80 %", f"Llevas {gastado:.2f} € de {limite:.2f} € en {texto}.", tipo="info", nivel="importante")
        except Exception:
            pass  # un fallo al avisar nunca debe impedir apuntar el gasto

    def del_mes(self, mes=None) -> list:
        mes = interpretar_mes(mes)

        return sorted((g for g in self.obtener_seccion("gastos") if str(g.get("fecha", "")).startswith(mes)), key=lambda g: (g["fecha"], g["id"]))

    def resumen(self, mes=None) -> dict:
        mes = interpretar_mes(mes)
        gastos = self.del_mes(mes)
        por_categoria = {}

        for g in gastos:
            c = por_categoria.setdefault(g["categoria"], {"categoria": g["categoria"], "total": 0.0, "n": 0})
            c["total"] = round(c["total"] + g["importe"], 2)
            c["n"] += 1

        return {
            "mes": mes,
            "total": round(sum(g["importe"] for g in gastos), 2),
            "n": len(gastos),
            "por_categoria": sorted(por_categoria.values(), key=lambda c: -c["total"]),
            "ultimos": list(reversed(gastos))[:10],
        }

    def borrar(self, id_gasto) -> dict:
        registros = self.obtener_seccion("gastos")

        if not registros:
            raise ValueError("No hay gastos apuntados.")

        if str(id_gasto).strip().lower() in ("ultimo", "último", ""):
            objetivo = max(registros, key=lambda g: g.get("id", 0))
        else:
            try:
                numero = int(id_gasto)
            except (TypeError, ValueError):
                raise ValueError("Indica el número del gasto (o 'ultimo').") from None

            objetivo = next((g for g in registros if g.get("id") == numero), None)

            if objetivo is None:
                raise ValueError(f"No existe el gasto número {numero}.")

        registros.remove(objetivo)
        self.guardar_seccion("gastos", registros)

        return objetivo
