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


UNIDADES = (
    r"(?:unidades|unidad|unids?\.?|unds?\.?|uds?\.?|u\.?|piezas?|pzs?\.?|paquetes?|botellas?|latas?|briks?|packs?)"
)

# "- ", "• ", "* ", "1. ", "2) " al principio de una línea de lista.
VIÑETA = re.compile(r"^\s*(?:[-•*·–]|\d+[.)])\s+")

SEPARADOR = r"[,;:\s\-–]+"

CANTIDAD_FINAL = re.compile(rf"{SEPARADOR}(\d+(?:[.,]\d+)?)\s*{UNIDADES}\s*$", re.IGNORECASE)
CANTIDAD_X_FINAL = re.compile(r"\s+[xX×]\s*(\d+(?:[.,]\d+)?)\s*$")
CANTIDAD_ENTRE_PARENTESIS = re.compile(r"\s*\(\s*(\d+(?:[.,]\d+)?)\s*\)\s*$")
CANTIDAD_SOLO_COMA = re.compile(r"[,:]\s*(\d+(?:[.,]\d+)?)\s*$")
CANTIDAD_INICIAL = re.compile(rf"^\s*(\d+(?:[.,]\d+)?)\s*(?:[xX×]|{UNIDADES}\s+de|{UNIDADES})\s+(.+)$", re.IGNORECASE)

APROX = re.compile(r"[\s,;:(]*\baprox(?:imad[ao]s?)?\.?\)?\s*$", re.IGNORECASE)


def _positivo(valor):
    try:
        return float(valor) > 0
    except (TypeError, ValueError):
        return True


def _numero(texto):
    numero = float(texto.replace(",", "."))

    return int(numero) if numero == int(numero) else numero


def parsear_lineas(texto):
    """
    Convierte un texto con varios productos en [(nombre, cantidad, explicita)].

    `explicita` es True si la línea decía cuántas unidades eran (y no se
    ha supuesto 1). Entiende una línea por producto (o separados por ";"):

      "Leche entera, 2 unidades" · "Leche: 2 unidades" · "Pollo 600 g aprox.: 2 unids"
      "2 x leche" · "Leche x2" · "Pan, 3" · "Huevos (12)" · "Sal"

    Las líneas que acaban en ":" son títulos y se ignoran. Si un producto
    se repite, se suman las cantidades.
    """

    if isinstance(texto, (list, tuple)):
        texto = "\n".join(str(t) for t in texto)

    lineas = re.split(r"[\n;]+", str(texto))

    acumulado = {}
    orden = []

    for linea in lineas:
        linea = VIÑETA.sub("", linea).strip()

        if not linea or linea.endswith(":"):
            continue

        linea = linea.rstrip(".").strip()

        cantidad = 1
        explicita = False
        nombre = linea

        for patron in (CANTIDAD_FINAL, CANTIDAD_X_FINAL, CANTIDAD_ENTRE_PARENTESIS, CANTIDAD_SOLO_COMA):
            coincidencia = patron.search(nombre)

            if coincidencia:
                cantidad = _numero(coincidencia.group(1))
                explicita = True
                nombre = nombre[: coincidencia.start()]
                break
        else:
            inicial = CANTIDAD_INICIAL.match(nombre)

            if inicial:
                cantidad = _numero(inicial.group(1))
                explicita = True
                nombre = inicial.group(2)

        nombre = APROX.sub("", nombre).strip(" ,;:-–")

        if not nombre or cantidad <= 0:
            continue

        clave = normalizar(nombre)

        if clave in acumulado:
            acumulado[clave][1] += cantidad
            acumulado[clave][2] = acumulado[clave][2] or explicita
        else:
            acumulado[clave] = [nombre, cantidad, explicita]
            orden.append(clave)

    return [tuple(acumulado[c]) for c in orden]


def parsear_lista(texto):
    """Igual que parsear_lineas pero devuelve solo [(nombre, cantidad), ...]."""

    return [(nombre, cantidad) for nombre, cantidad, _ in parsear_lineas(texto)]


# Lo que se da por supuesto que hay en cualquier cocina. El usuario puede
# cambiar la lista ("ya no tengo comino", "siempre tengo vino blanco").
BASICOS_POR_DEFECTO = (
    "agua",
    "aceite de oliva",
    "sal",
    "azúcar",
    "harina",
    "pimienta",
    "pimentón",
    "orégano",
    "comino",
    "ajo en polvo",
    "canela",
    "vinagre",
    "laurel",
)


PALABRAS_VACIAS = {"de", "del", "la", "el", "los", "las", "y", "en", "al", "con", "para", "un", "una", "unos", "unas"}

# "200 g de harina", "2 cucharadas de aceite", "1 diente de ajo"...
MEDIDA_INICIAL = re.compile(
    r"^\s*\d+(?:[.,]\d+)?\s*(?:kg|kilos?|gr?|gramos?|ml|cl|dl|l|litros?|cucharad(?:a|ita)s?|cdas?\.?|cdtas?\.?|"
    r"tazas?|vasos?|dientes?|pizcas?|ramitas?|hojas?|lonchas?|rodajas?|filetes?)\b\s*(?:de\s+)?",
    re.IGNORECASE,
)


def _palabras(texto):
    """Palabras clave de un nombre de producto (sin acentos, plurales ni artículos)."""

    palabras = set()

    for palabra in re.findall(r"[a-z0-9ñ]+", normalizar(texto)):
        if palabra in PALABRAS_VACIAS:
            continue

        # Raíz aproximada: tomates/tomate -> tomat, limones/limon -> limon.
        if len(palabra) > 3 and palabra.endswith("s"):
            palabra = palabra[:-1]

        if len(palabra) > 4 and palabra.endswith("e"):
            palabra = palabra[:-1]

        palabras.add(palabra)

    return palabras


def mismo_producto(a, b):
    """
    True si dos nombres se refieren al mismo producto: las palabras del más
    corto están todas en el más largo ("aceite" y "aceite de oliva" sí;
    "sal" y "salmón" no).
    """

    pa, pb = _palabras(a), _palabras(b)

    if not pa or not pb:
        return False

    corto, largo = (pa, pb) if len(pa) <= len(pb) else (pb, pa)

    return corto <= largo


CANTIDAD_SUELTA = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s+(?![xX×]\s)(\D.*)$")


def limpiar_ingrediente(nombre, cantidad=1):
    """
    Quita medidas y números iniciales: '200 g de harina' -> 'harina',
    '2 huevos' -> 'huevos'. Devuelve (nombre, cantidad).
    """

    texto = str(nombre).strip()

    if MEDIDA_INICIAL.match(texto):
        texto = MEDIDA_INICIAL.sub("", texto).strip(" ,;:-")
    else:
        suelta = CANTIDAD_SUELTA.match(texto)

        if suelta:
            cantidad = _numero(suelta.group(1))
            texto = suelta.group(2).strip()

    return (texto or str(nombre).strip()), cantidad


class Inventario(ModuloBase):
    nombre = "inventario"

    # ------------------------------------------------------------------
    # Recetas: qué falta
    # ------------------------------------------------------------------

    def comparar_receta(self, ingredientes):
        """
        Compara los ingredientes de una receta (texto o lista) con el
        frigorífico, el congelador, la despensa y los básicos de casa.

        Devuelve:
          disponibles: [{ingrediente, en}]  (en = ubicación o "básicos de casa")
          agotados:    [{ingrediente, en}]  (está apuntado en el inventario pero con cantidad 0)
          faltan:      [(nombre, cantidad)] (no hay nada de eso; lo que hay que comprar)
        """

        pedidos = [limpiar_ingrediente(n, c) for n, c in parsear_lista(ingredientes)]

        comida = []

        for sitio in ("frigorifico", "congelador", "despensa"):
            for producto in self.obtener_seccion(sitio):
                comida.append((sitio, str(producto.get("nombre", "")), producto.get("cantidad", 1)))

        basicos = self.basicos()

        disponibles, agotados, faltan = [], [], []

        for nombre, cantidad in pedidos:
            coincidencias = [(sitio, n, q) for sitio, n, q in comida if mismo_producto(nombre, n)]

            con_stock = [c for c in coincidencias if _positivo(c[2])]

            if con_stock:
                disponibles.append({"ingrediente": nombre, "en": con_stock[0][0]})
            elif any(mismo_producto(nombre, b) for b in basicos):
                disponibles.append({"ingrediente": nombre, "en": "básicos de casa"})
            else:
                if coincidencias:
                    agotados.append({"ingrediente": nombre, "en": coincidencias[0][0]})

                faltan.append((nombre, cantidad))

        return {"disponibles": disponibles, "agotados": agotados, "faltan": faltan}

    # ------------------------------------------------------------------
    # Básicos de casa (para las recetas)
    # ------------------------------------------------------------------

    def basicos(self):
        """Lista de básicos de casa (los del usuario o, si no los ha tocado, los de fábrica)."""

        guardados = self.data.leer_modulo(self.nombre).get("basicos")

        if isinstance(guardados, list):
            return [str(b) for b in guardados]

        return list(BASICOS_POR_DEFECTO)

    def anadir_basico(self, nombre):
        nombre = str(nombre).strip()

        if not nombre:
            raise ValueError("Falta el nombre del básico.")

        actuales = self.basicos()

        if normalizar(nombre) not in {normalizar(b) for b in actuales}:
            actuales.append(nombre)
            self.guardar_seccion("basicos", actuales)

        return actuales

    def quitar_basico(self, nombre):
        clave = normalizar(nombre)

        actuales = self.basicos()

        restantes = [b for b in actuales if normalizar(b) != clave]

        if len(restantes) == len(actuales):
            raise ValueError(f"'{nombre}' no está entre los básicos de casa.")

        self.guardar_seccion("basicos", restantes)

        return restantes

    def ingredientes_para_cocinar(self):
        """Todo lo que hay para cocinar: inventario (comida) + básicos de casa."""

        comida = []

        for sitio in ("frigorifico", "congelador", "despensa"):
            for producto in sorted(self.obtener_seccion(sitio), key=lambda p: normalizar(p.get("nombre", ""))):
                comida.append(f"{producto.get('nombre', '')} (x{producto.get('cantidad', 1)}, {sitio})")

        return {"inventario": comida, "basicos": self.basicos()}

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

    def borrar(self, nombre, ubicacion=None):
        """
        Elimina por completo un producto (sin importar cuántas unidades haya).
        Devuelve los productos borrados.
        """

        clave = normalizar(nombre)

        sitios = [self.normalizar_ubicacion(ubicacion)] if ubicacion else list(UBICACIONES)

        borrados = []

        for sitio in sitios:
            productos = self.obtener_seccion(sitio)

            restantes = []

            for producto in productos:
                existente = normalizar(producto.get("nombre", ""))

                if existente == clave or (len(clave) >= 3 and clave in existente):
                    borrados.append({**producto, "ubicacion": sitio})
                else:
                    restantes.append(producto)

            if len(restantes) != len(productos):
                self.guardar_seccion(sitio, restantes)

        if not borrados:
            raise ValueError(f"No encuentro '{nombre}' en el inventario.")

        return borrados

    def vaciar(self, ubicacion=None):
        """Borra todos los productos de una ubicación (o de todas). Devuelve cuántos."""

        sitios = [self.normalizar_ubicacion(ubicacion)] if ubicacion else list(UBICACIONES)

        total = 0

        for sitio in sitios:
            total += len(self.obtener_seccion(sitio))
            self.guardar_seccion(sitio, [])

        return total

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
