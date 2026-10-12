"""
Búsqueda y lectura de notas y manuales guardados en datos/documentos/.

Lee archivos .txt, .md y .json, los parte en fragmentos y los puntúa con
BM25 (puro Python, sin embeddings ni bibliotecas externas). El índice se
rehace solo cuando cambia algún archivo.
"""

import json
import math
import re
import threading
from pathlib import Path

from brain.base.modulo import ModuloBase
from brain.core.config import Config
from brain.modules.inventario import normalizar

EXTENSIONES = (".txt", ".md", ".json")
MAX_BYTES = 5 * 1024 * 1024
TAM_FRAGMENTO = 800  # caracteres aproximados por fragmento
SOLAPE = 120

K1 = 1.5
B = 0.75

VACIAS = {
    "de", "del", "la", "las", "el", "los", "y", "o", "a", "en", "un", "una", "unos", "unas", "que", "se", "es",
    "por", "con", "para", "al", "lo", "su", "sus", "como", "mas", "pero", "si", "no", "me", "mi", "te", "tu",
    "the", "and", "of", "to", "in", "is", "for", "on",
}


class DocumentoError(ValueError):
    """Error con mensaje entendible para el usuario."""


def tokenizar(texto):
    """Palabras clave en minúsculas, sin acentos, sin artículos y con raíz aproximada."""

    tokens = []

    for palabra in re.findall(r"[a-z0-9ñ]+", normalizar(texto)):
        if palabra in VACIAS or len(palabra) < 2:
            continue

        if len(palabra) > 4 and palabra.endswith("es"):
            palabra = palabra[:-2]
        elif len(palabra) > 3 and palabra.endswith("s"):
            palabra = palabra[:-1]

        tokens.append(palabra)

    return tokens


def _aplanar_json(valor, prefijo=""):
    """Convierte un JSON en líneas 'clave: valor' buscables."""

    lineas = []

    if isinstance(valor, dict):
        for clave, v in valor.items():
            lineas += _aplanar_json(v, f"{prefijo}{clave}.")
    elif isinstance(valor, list):
        for i, v in enumerate(valor):
            if isinstance(v, (dict, list)):
                lineas += _aplanar_json(v, f"{prefijo}{i + 1}.")
            else:
                lineas.append(f"{prefijo.rstrip('.')}: {v}")
    else:
        lineas.append(f"{prefijo.rstrip('.')}: {valor}")

    return lineas


def leer_texto(ruta):
    """Lee un archivo de texto aceptando UTF-8 (con o sin BOM) y Windows-1252."""

    datos = Path(ruta).read_bytes()[:MAX_BYTES]

    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            return datos.decode(codificacion)
        except UnicodeDecodeError:
            continue

    return datos.decode("latin-1")


def texto_de_documento(ruta):
    """Texto legible de un documento (los .json se aplanan)."""

    texto = leer_texto(ruta)

    if Path(ruta).suffix.lower() == ".json":
        try:
            return "\n".join(_aplanar_json(json.loads(texto)))
        except ValueError:
            pass  # JSON mal formado: se trata como texto normal

    return texto


def trocear(texto, tamano=TAM_FRAGMENTO, solape=SOLAPE):
    """Divide en fragmentos de ~`tamano` caracteres respetando párrafos y frases."""

    parrafos = [p.strip() for p in re.split(r"\n\s*\n|\n(?=#)", texto) if p.strip()]

    piezas = []

    for parrafo in parrafos:
        if len(parrafo) <= tamano:
            piezas.append(parrafo)
            continue

        frases = re.split(r"(?<=[.!?])\s+|\n", parrafo)
        actual = ""

        for frase in frases:
            while len(frase) > tamano:  # frase enorme: se corta a la fuerza
                if actual:
                    piezas.append(actual)
                    actual = ""
                piezas.append(frase[:tamano])
                frase = frase[tamano - solape :]

            if actual and len(actual) + len(frase) + 1 > tamano:
                piezas.append(actual)
                actual = actual[-solape:].split(" ", 1)[-1] + " " + frase if solape else frase
            else:
                actual = f"{actual} {frase}".strip()

        if actual:
            piezas.append(actual)

    # Une párrafos cortos consecutivos para no tener cientos de fragmentos diminutos.
    fragmentos = []

    for pieza in piezas:
        if fragmentos and len(fragmentos[-1]) + len(pieza) + 2 <= tamano // 2:
            fragmentos[-1] += "\n\n" + pieza
        else:
            fragmentos.append(pieza)

    return fragmentos


class Documentos(ModuloBase):
    nombre = "documentos"

    def __init__(self):
        super().__init__()
        self._cache = None  # (firma, índice)
        self._bloqueo = threading.Lock()

    @property
    def carpeta(self) -> Path:
        return Path(Config.DATOS) / "documentos"

    # ------------------------------------------------------------------
    # Archivos
    # ------------------------------------------------------------------

    def archivos(self):
        carpeta = self.carpeta

        if not carpeta.exists():
            return []

        return sorted(
            p for p in carpeta.rglob("*") if p.is_file() and p.suffix.lower() in EXTENSIONES and not p.name.startswith(".")
        )

    def listar(self):
        """Documentos disponibles: nombre (ruta relativa) y tamaño."""

        return [{"nombre": p.relative_to(self.carpeta).as_posix(), "tamano_kb": round(p.stat().st_size / 1024, 1)} for p in self.archivos()]

    def resolver(self, nombre):
        """Encuentra un documento por nombre exacto o parcial, sin salir de la carpeta."""

        texto = str(nombre or "").strip().replace("\\", "/")

        if not texto:
            raise DocumentoError("Falta el nombre del documento.")

        archivos = self.archivos()

        if not archivos:
            raise DocumentoError(f"No hay documentos. Guarda archivos .txt, .md o .json en {self.carpeta}.")

        relativos = {p.relative_to(self.carpeta).as_posix(): p for p in archivos}
        clave = normalizar(texto)

        for relativo, ruta in relativos.items():
            if normalizar(relativo) == clave:
                return ruta

        # Sin extensión o parcial
        exactos = [r for r in relativos if normalizar(Path(r).stem) == clave or normalizar(Path(r).name) == clave]

        if not exactos:
            exactos = [r for r in relativos if clave in normalizar(r)]

        if len(exactos) == 1:
            return relativos[exactos[0]]

        if len(exactos) > 1:
            raise DocumentoError(f"'{nombre}' coincide con varios documentos: {', '.join(exactos)}. Indica el nombre completo.")

        raise DocumentoError(f"No encuentro el documento '{nombre}'. Disponibles: {', '.join(relativos)}.")

    # ------------------------------------------------------------------
    # Índice BM25
    # ------------------------------------------------------------------

    def _firma(self):
        return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in self.archivos())

    def _indice(self):
        firma = self._firma()

        with self._bloqueo:
            if self._cache and self._cache[0] == firma:
                return self._cache[1]

            fragmentos = []

            for ruta in self.archivos():
                try:
                    texto = texto_de_documento(ruta)
                except OSError:
                    continue

                nombre = ruta.relative_to(self.carpeta).as_posix()

                for n, trozo in enumerate(trocear(texto), start=1):
                    # El nombre del archivo también cuenta: "manual lavadora" encuentra manual_lavadora.md
                    tokens = tokenizar(trozo) + tokenizar(Path(nombre).stem.replace("_", " "))

                    if tokens:
                        fragmentos.append({"documento": nombre, "fragmento": n, "texto": trozo, "tokens": tokens})

            frecuencia_docs = {}

            for f in fragmentos:
                for termino in set(f["tokens"]):
                    frecuencia_docs[termino] = frecuencia_docs.get(termino, 0) + 1

            medio = sum(len(f["tokens"]) for f in fragmentos) / len(fragmentos) if fragmentos else 0

            indice = {"fragmentos": fragmentos, "df": frecuencia_docs, "medio": medio}

            self._cache = (firma, indice)

            return indice

    def buscar(self, consulta, limite=5):
        """Los `limite` fragmentos más relevantes para la consulta."""

        terminos = tokenizar(consulta)

        if not terminos:
            raise DocumentoError("Escribe palabras para buscar (no solo artículos o signos).")

        indice = self._indice()
        fragmentos = indice["fragmentos"]

        if not fragmentos:
            return []

        n = len(fragmentos)
        resultados = []

        for f in fragmentos:
            longitud = len(f["tokens"])
            conteo = {}

            for t in f["tokens"]:
                conteo[t] = conteo.get(t, 0) + 1

            puntos = 0.0

            for termino in set(terminos):
                tf = conteo.get(termino, 0)

                if not tf:
                    continue

                df = indice["df"][termino]
                idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
                puntos += idf * tf * (K1 + 1) / (tf + K1 * (1 - B + B * longitud / indice["medio"]))

            if puntos > 0:
                resultados.append((puntos, f))

        resultados.sort(key=lambda r: r[0], reverse=True)

        return [
            {
                "documento": f["documento"],
                "fragmento": f["fragmento"],
                "puntuacion": round(p, 3),
                "texto": f["texto"],
            }
            for p, f in resultados[: max(1, int(limite))]
        ]

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------

    def leer(self, nombre, desde=0, maximo=6000):
        """Texto de un documento por páginas de `maximo` caracteres."""

        ruta = self.resolver(nombre)

        texto = texto_de_documento(ruta)

        desde = max(0, int(desde or 0))
        maximo = min(max(500, int(maximo or 6000)), 20000)

        trozo = texto[desde : desde + maximo]

        resultado = {
            "documento": ruta.relative_to(self.carpeta).as_posix(),
            "desde": desde,
            "hasta": desde + len(trozo),
            "total_caracteres": len(texto),
            "texto": trozo,
        }

        if desde + maximo < len(texto):
            resultado["siguiente_desde"] = desde + maximo

        return resultado
