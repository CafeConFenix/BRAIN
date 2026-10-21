import re
from datetime import date, timedelta

from brain.base.modulo import ModuloBase
from brain.modules.inventario import normalizar
from brain.utils.fechas import DIAS

COMIDAS = ("comida", "cena")


def _dia(texto):
    clave = normalizar(texto)

    for i, nombre in enumerate(DIAS):
        if clave.startswith(normalizar(nombre)[:3]):
            return i

    raise ValueError(f"No entiendo el día '{texto}'.")


def parsear_menu(texto) -> list:
    """
    Una línea por plato: 'lunes comida: Macarrones con tomate | pasta, tomate, queso'.
    La comida/cena es opcional (por defecto comida) y los ingredientes van tras '|' o ' - '.
    """

    platos = []

    for linea in str(texto or "").splitlines():
        linea = linea.strip(" -*•\t")

        if ":" not in linea:
            continue

        cabecera, resto = linea.split(":", 1)
        palabras = cabecera.split()

        if not palabras:
            continue

        try:
            dia = _dia(palabras[0])
        except ValueError:
            continue

        momento = "cena" if any(normalizar(p).startswith("cen") for p in palabras[1:]) else "comida"
        partes = re.split(r"\s*\|\s*|\s+[-–—]\s+", resto, maxsplit=1)
        nombre = partes[0].strip()

        if not nombre:
            continue

        ingredientes = [i.strip() for i in re.split(r"[,;]", partes[1]) if i.strip()] if len(partes) > 1 else []
        platos.append({"dia": dia, "momento": momento, "plato": nombre[:80], "ingredientes": ingredientes})

    return platos


class Menu(ModuloBase):
    """Menú de la semana: platos por día (comida y cena) y la compra de lo que falta."""

    nombre = "menu"

    def guardar(self, texto) -> dict:
        platos = parsear_menu(texto)

        if not platos:
            raise ValueError("No he encontrado ningún plato. Usa una línea por plato, por ejemplo: 'lunes comida: Lentejas | lentejas, chorizo, zanahoria'.")

        hoy = date.today()
        lunes = hoy - timedelta(days=hoy.weekday())
        self.guardar_seccion("platos", platos)
        datos = self.data.leer_modulo(self.nombre)
        datos["semana"] = lunes.isoformat()
        self.data.guardar_modulo(self.nombre, datos)

        return self.ver()

    def ver(self) -> dict:
        platos = self.obtener_seccion("platos")
        dias = []

        for i, nombre in enumerate(DIAS):
            fila = {"dia": nombre}

            for p in platos:
                if p["dia"] == i:
                    fila[p["momento"]] = p["plato"]

            if len(fila) > 1:
                dias.append(fila)

        return {"dias": dias, "total_platos": len(platos), "semana": self.data.leer_modulo(self.nombre).get("semana")}

    def faltan(self) -> list:
        """Ingredientes del menú que no hay en casa (sin repetir)."""

        from brain.modules.inventario import Inventario

        inventario = Inventario()
        vistos, faltan = set(), []

        for p in self.obtener_seccion("platos"):
            if not p["ingredientes"]:
                continue

            for nombre, cantidad in inventario.comparar_receta("\n".join(p["ingredientes"]))["faltan"]:
                clave = normalizar(nombre)

                if clave not in vistos:
                    vistos.add(clave)
                    faltan.append((nombre, cantidad))

        return faltan

    def añadir_faltantes_a_compra(self) -> dict:
        from brain.modules.compras import Compras

        if not self.obtener_seccion("platos"):
            raise ValueError("Todavía no hay menú semanal. Pídeme que lo prepare.")

        faltan = self.faltan()
        compras = Compras()
        en_lista = {normalizar(i.get("producto", "")) for i in compras.lista()}
        nuevos = [(n, c) for n, c in faltan if normalizar(n) not in en_lista]

        if nuevos:
            compras.añadir_varios(nuevos)

        return {"añadidos": [n for n, _ in nuevos], "ya_en_la_lista": [n for n, _ in faltan if normalizar(n) in en_lista]}

    def vaciar(self) -> int:
        n = len(self.obtener_seccion("platos"))
        self.guardar_seccion("platos", [])

        return n
