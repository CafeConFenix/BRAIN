from brain.base.modulo import ModuloBase
from brain.modules.inventario import normalizar
from brain.utils.fechas import hoy

TIPOS = ("personas", "preferencias", "contexto", "proyectos")

SINONIMOS = {
    "persona": "personas",
    "gente": "personas",
    "preferencia": "preferencias",
    "gusto": "preferencias",
    "gustos": "preferencias",
    "proyecto": "proyectos",
    "dato": "contexto",
    "datos": "contexto",
    "nota": "contexto",
    "notas": "contexto",
}


class Memoria(ModuloBase):
    nombre = "memoria"

    def normalizar_tipo(self, tipo, estricto=False):
        """Tipo oficial de memoria. Lo desconocido se guarda como "contexto"."""

        clave = normalizar(tipo or "contexto")

        clave = SINONIMOS.get(clave, clave)

        if clave in TIPOS:
            return clave

        if estricto:
            raise ValueError(f"El tipo de memoria '{tipo}' no existe. Opciones: {', '.join(TIPOS)}.")

        return "contexto"

    def recordar(self, texto, tipo="contexto"):
        """Guarda algo para que BRAIN lo recuerde siempre."""

        tipo = self.normalizar_tipo(tipo)

        texto = str(texto).strip()

        if not texto:
            raise ValueError("No hay nada que recordar.")

        existentes = self.obtener_seccion(tipo)

        for registro in existentes:
            if normalizar(registro.get("texto", "")) == normalizar(texto):
                return {**registro, "tipo": tipo, "ya_existia": True}

        registro = {"texto": texto, "fecha": hoy()}

        self.añadir_registro(tipo, registro)

        return {**registro, "tipo": tipo}

    def consultar(self, tipo=None):
        clave = SINONIMOS.get(normalizar(tipo or ""), normalizar(tipo or ""))

        # "todo", "todos", "recuerdos"... o un tipo que no existe: se muestra todo.
        if clave in TIPOS:
            return {clave: self.obtener_seccion(clave)}

        return {t: self.obtener_seccion(t) for t in TIPOS if self.obtener_seccion(t)}

    def olvidar(self, texto):
        """Borra los recuerdos que contengan el texto indicado."""

        clave = normalizar(texto)

        borrados = []

        for tipo in TIPOS:
            registros = self.obtener_seccion(tipo)

            restantes = [r for r in registros if clave not in normalizar(r.get("texto", ""))]

            if len(restantes) != len(registros):
                borrados.extend(r for r in registros if r not in restantes)
                self.guardar_seccion(tipo, restantes)

        if not borrados:
            raise ValueError(f"No encuentro ningún recuerdo con '{texto}'.")

        return {"olvidados": borrados}

    def resumen_para_ia(self):
        """Texto breve con todo lo recordado, para incluir en el prompt."""

        lineas = []

        for tipo, registros in self.consultar().items():
            for registro in registros:
                lineas.append(f"- ({tipo}) {registro.get('texto', '')}")

        return "\n".join(lineas)
