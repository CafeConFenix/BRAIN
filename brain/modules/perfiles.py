from brain.base.modulo import ModuloBase
from brain.modules.inventario import normalizar


class Perfiles(ModuloBase):
    """Las personas de la casa. Hábitos y tareas del hogar pueden ser de una persona o de todos."""

    nombre = "perfiles"

    def listar(self) -> list:
        return [p for p in self.obtener_seccion("personas") if isinstance(p, dict) and p.get("nombre")]

    def nombres(self) -> list:
        return [p["nombre"] for p in self.listar()]

    def añadir(self, nombre) -> dict:
        nombre = str(nombre or "").strip()[:30]

        if not nombre:
            raise ValueError("Indica el nombre de la persona.")

        personas = self.listar()

        for p in personas:
            if normalizar(p["nombre"]) == normalizar(nombre):
                return p

        if len(personas) >= 12:
            raise ValueError("Ya hay 12 personas; borra alguna primero.")

        nueva = {"nombre": nombre}
        personas.append(nueva)
        self.guardar_seccion("personas", personas)

        return nueva

    def buscar(self, nombre) -> dict:
        clave = normalizar(nombre)

        for p in self.listar():
            if normalizar(p["nombre"]) == clave:
                return p

        raise ValueError(f"No conozco a '{nombre}' entre las personas de la casa.")

    def borrar(self, nombre) -> dict:
        persona = self.buscar(nombre)
        self.guardar_seccion("personas", [p for p in self.listar() if p["nombre"] != persona["nombre"]])

        return persona
