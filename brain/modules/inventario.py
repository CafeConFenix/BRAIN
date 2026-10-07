import re
import unicodedata

from brain.base.modulo import ModuloBase

UBICACIONES = ("frigorifico", "congelador", "despensa", "herramientas", "consumibles")

SINONIMOS = {
    "nevera": "frigorifico",
    "frigorifica": "frigorifico",
    "fridge": "frigorifico",
    "arcon": "congelador",
    "armario": "despensa",
    "armarios": "despensa",
    "almacen": "despensa",
    "bodega": "despensa",
    "garaje": "herramientas",
    "trastero": "herramientas",
    "limpieza": "consumibles",
    "botiquin": "consumibles",
    "bano": "consumibles",
    "frigo": "frigorifico",
    "refrigerador": "frigorifico",
    "freezer": "congelador",
    "alacena": "despensa",
    "cocina": "despensa",
    "herramienta": "herramientas",
    "taller": "herramientas",
    "consumible": "consumibles",
}


def _sin_acentos(texto):
    normal = unicodedata.normalize("NFD", str(texto))

    return "".join(c for c in normal if unicodedata.category(c) != "Mn")


def normalizar(texto):
    """Pasa a minúsculas y sin acentos, para comparar nombres."""

    return _sin_acentos(texto).strip().lower()


UNIDADES = r"(?:unidades|unidad|uds?\.?|unid\.?|u\.?|piezas?|pzs?\.?|paquetes?|botellas?|latas?|briks?|packs?)"

# "- ", "• ", "* ", "1. ", "2) " al principio de una línea de lista.
VIÑETA = re.compile(r"^\s*(?:[-•*·–]|\d+[.)])\s+")

CANTIDAD_FINAL = re.compile(rf"[,;:\s]+(\d+(?:[.,]\d+)?)\s*{UNIDADES}\s*$", re.IGNORECASE)
CANTIDAD_X_FINAL = re.compile(r"\s+[xX×]\s*(\d+(?:[.,]\d+)?)\s*$")
CANTIDAD_INICIAL = re.compile(rf"^\s*(\d+(?:[.,]\d+)?)\s*(?:[xX×]|{UNIDADES}\s+de|{UNIDADES})\s+(.+)$", re.IGNORECASE)
CANTIDAD_SOLO_COMA = re.compile(r",\s*(\d+(?:[.,]\d+)?)\s*$")


def _numero(texto):
    numero = float(texto.replace(",", "."))

    return int(numero) if numero == int(numero) else numero


def parsear_lista(texto):
    """
    Convierte un texto con varios productos en [(nombre, cantidad), ...].

    Entiende una línea por producto (o separados por ";") y cantidades como:
      "Leche entera, 2 unidades" · "2 x leche" · "Leche x2" · "Pan, 3" · "Sal"
    Sin cantidad se entiende 1. Si un producto se repite, se suman.
    """

    if isinstance(texto, (list, tuple)):
        texto = "\n".join(str(t) for t in texto)

    lineas = re.split(r"[\n;]+", str(texto))

    acumulado = {}
    orden = []

    for linea in lineas:
        linea = VIÑETA.sub("", linea).strip().strip(".").strip()

        if not linea:
            continue

        cantidad = 1
        nombre = linea

        for patron in (CANTIDAD_FINAL, CANTIDAD_X_FINAL, CANTIDAD_SOLO_COMA):
            coincidencia = patron.search(nombre)

            if coincidencia:
                cantidad = _numero(coincidencia.group(1))
                nombre = nombre[: coincidencia.start()]
                break
        else:
            inicial = CANTIDAD_INICIAL.match(nombre)

            if inicial:
                cantidad = _numero(inicial.group(1))
                nombre = inicial.group(2)

        nombre = nombre.strip(" ,;:-")

        if not nombre or cantidad <= 0:
            continue

        clave = normalizar(nombre)

        if clave in acumulado:
            acumulado[clave][1] += cantidad
        else:
            acumulado[clave] = [nombre, cantidad]
            orden.append(clave)

    return [(acumulado[c][0], acumulado[c][1]) for c in orden]


class Inventario(ModuloBase):
    nombre = "inventario"

    def normalizar_ubicacion(self, ubicacion, estricta=False):
        """
        Devuelve la ubicación oficial. Si no se reconoce y `estricta` es
        False, se usa la despensa en vez de fallar (los modelos de IA
        inventan nombres como "cocina" o "armario de abajo").
        """

        clave = normalizar(ubicacion or "despensa")

        clave = SINONIMOS.get(clave, clave)

        if clave in UBICACIONES:
            return clave

        for palabra in clave.replace("-", " ").split():
            palabra = SINONIMOS.get(palabra, palabra)

            if palabra in UBICACIONES:
                return palabra

        if estricta:
            raise ValueError(f"La ubicación '{ubicacion}' no existe. Opciones: {', '.join(UBICACIONES)}.")

        return "despensa"

    def añadir_varios(self, productos, ubicacion="despensa"):
        """
        Añade muchos productos de una vez (lista de (nombre, cantidad)).

        Lee y guarda el archivo una sola vez, y devuelve qué se añadió.
        """

        ubicacion = self.normalizar_ubicacion(ubicacion)

        existentes = self.obtener_seccion(ubicacion)

        indice = {normalizar(p.get("nombre", "")): p for p in existentes}

        añadidos = []

        for nombre, cantidad in productos:
            clave = normalizar(nombre)

            if clave in indice:
                indice[clave]["cantidad"] = indice[clave].get("cantidad", 0) + cantidad
            else:
                nuevo = {"nombre": str(nombre).strip(), "cantidad": cantidad}
                existentes.append(nuevo)
                indice[clave] = nuevo

            añadidos.append({"nombre": indice[clave]["nombre"], "cantidad_total": indice[clave]["cantidad"]})

        self.guardar_seccion(ubicacion, existentes)

        return {"ubicacion": ubicacion, "añadidos": añadidos}

    def todo(self):
        """Todos los productos como lista plana [{ubicacion, nombre, cantidad}]."""

        plano = []

        for sitio in UBICACIONES:
            for producto in sorted(self.obtener_seccion(sitio), key=lambda p: normalizar(p.get("nombre", ""))):
                plano.append(
                    {"ubicacion": sitio, "nombre": producto.get("nombre", ""), "cantidad": producto.get("cantidad", 1)}
                )

        return plano

    def añadir_producto(self, seccion, producto):
        """Añade un producto tal cual (compatibilidad con versiones anteriores)."""

        self.añadir_registro(seccion, producto)

    def añadir(self, nombre, cantidad=1, ubicacion="despensa"):
        """
        Añade unidades de un producto. Si ya existe en esa ubicación,
        suma la cantidad.
        """

        ubicacion = self.normalizar_ubicacion(ubicacion)

        cantidad = float(cantidad)

        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor que cero.")

        if cantidad == int(cantidad):
            cantidad = int(cantidad)

        productos = self.obtener_seccion(ubicacion)

        for producto in productos:
            if normalizar(producto.get("nombre", "")) == normalizar(nombre):
                producto["cantidad"] = producto.get("cantidad", 0) + cantidad
                self.guardar_seccion(ubicacion, productos)

                return {**producto, "ubicacion": ubicacion}

        nuevo = {"nombre": str(nombre).strip(), "cantidad": cantidad}

        productos.append(nuevo)

        self.guardar_seccion(ubicacion, productos)

        return {**nuevo, "ubicacion": ubicacion}

    def quitar(self, nombre, cantidad=1, ubicacion=None):
        """
        Resta unidades de un producto (en una ubicación o en todas). Si
        llega a cero, lo elimina.
        """

        cantidad = float(cantidad)

        ubicaciones = [self.normalizar_ubicacion(ubicacion)] if ubicacion else list(UBICACIONES)

        # Si no está en el sitio indicado, se busca también en el resto.
        if ubicacion:
            ubicaciones += [u for u in UBICACIONES if u not in ubicaciones]

        clave = normalizar(nombre)

        for sitio in ubicaciones:
            productos = self.obtener_seccion(sitio)

            for producto in productos:
                existente = normalizar(producto.get("nombre", ""))

                # Coincidencia exacta o, si no, "leche" encuentra "Leche entera Pascual".
                if existente != clave and not (len(clave) >= 3 and clave in existente):
                    continue

                restante = producto.get("cantidad", 0) - cantidad

                if restante <= 0:
                    productos.remove(producto)
                    restante = 0
                else:
                    producto["cantidad"] = int(restante) if restante == int(restante) else restante

                self.guardar_seccion(sitio, productos)

                return {
                    "nombre": producto.get("nombre"),
                    "ubicacion": sitio,
                    "cantidad_restante": restante,
                }

        raise ValueError(f"No encuentro '{nombre}' en el inventario.")

    def listar(self, ubicacion=None):
        """Devuelve el inventario de una ubicación o de todas."""

        if ubicacion:
            sitio = self.normalizar_ubicacion(ubicacion)

            return {sitio: self.obtener_seccion(sitio)}

        return {sitio: self.obtener_seccion(sitio) for sitio in UBICACIONES if self.obtener_seccion(sitio)}

    def buscar(self, texto):
        """Busca productos cuyo nombre contenga el texto."""

        clave = normalizar(texto)

        encontrados = []

        for sitio in UBICACIONES:
            for producto in self.obtener_seccion(sitio):
                if clave in normalizar(producto.get("nombre", "")):
                    encontrados.append({**producto, "ubicacion": sitio})

        return encontrados
