from brain.base.modulo import ModuloBase
from brain.modules.inventario import normalizar
from brain.utils.fechas import hoy


class Compras(ModuloBase):
    nombre = "compras"

    def añadir(self, producto, cantidad=1):
        """Añade un producto a la lista de la compra (suma si ya estaba)."""

        cantidad = float(cantidad)

        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor que cero.")

        if cantidad == int(cantidad):
            cantidad = int(cantidad)

        lista = self.obtener_seccion("lista_compra")

        for item in lista:
            if normalizar(item.get("producto", "")) == normalizar(producto):
                item["cantidad"] = item.get("cantidad", 0) + cantidad
                self.guardar_seccion("lista_compra", lista)

                return item

        item = {"producto": str(producto).strip(), "cantidad": cantidad}

        lista.append(item)

        self.guardar_seccion("lista_compra", lista)

        return item

    def añadir_varios(self, productos):
        """Añade varios productos de una vez (lista de (nombre, cantidad))."""

        lista = self.obtener_seccion("lista_compra")

        indice = {normalizar(i.get("producto", "")): i for i in lista}

        añadidos = []

        for nombre, cantidad in productos:
            clave = normalizar(nombre)

            if clave in indice:
                indice[clave]["cantidad"] = indice[clave].get("cantidad", 0) + cantidad
            else:
                item = {"producto": str(nombre).strip(), "cantidad": cantidad}
                lista.append(item)
                indice[clave] = item

            añadidos.append({"producto": indice[clave]["producto"], "cantidad_total": indice[clave]["cantidad"]})

        self.guardar_seccion("lista_compra", lista)

        return añadidos

    def lista(self):
        return self.obtener_seccion("lista_compra")

    def comprado(self, producto):
        """Quita un producto de la lista y lo apunta en el historial."""

        lista = self.obtener_seccion("lista_compra")

        for item in lista:
            if normalizar(item.get("producto", "")) == normalizar(producto):
                lista.remove(item)

                self.guardar_seccion("lista_compra", lista)

                self.añadir_registro("historial", {**item, "fecha": hoy()})

                return item

        raise ValueError(f"'{producto}' no está en la lista de la compra.")

    def historial(self, limite=20):
        return self.obtener_seccion("historial")[-int(limite) :]
