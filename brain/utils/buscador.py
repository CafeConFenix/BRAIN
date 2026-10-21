"""Búsqueda global: un solo cuadro para encontrar cosas en toda la casa."""

from brain.modules.inventario import normalizar


def _coincide(clave, *textos) -> bool:
    return any(clave in normalizar(t) for t in textos if t)


def buscar_todo(modulos, texto, limite=8) -> dict:
    """modulos: el registro de módulos (brain.modules). Devuelve resultados agrupados por tipo."""

    clave = normalizar(texto)

    if len(clave) < 2:
        raise ValueError("Escribe al menos dos letras para buscar.")

    grupos = []

    def añadir(tipo, titulo, items):
        if items:
            grupos.append({"tipo": tipo, "titulo": titulo, "resultados": items[:limite]})

    inventario = modulos.obtener("inventario")

    if inventario:
        añadir("despensa", "En casa", [{"texto": f"{p['nombre']} ({p['cantidad']})", "detalle": p["ubicacion"] + (f", caduca {p['caduca']}" if p.get("caduca") else "")} for p in inventario.todo() if _coincide(clave, p["nombre"], p["ubicacion"])])

    compras = modulos.obtener("compras")

    if compras:
        añadir("compra", "Lista de la compra", [{"texto": i.get("producto", ""), "detalle": f"x{i.get('cantidad', 1)}"} for i in compras.lista() if _coincide(clave, i.get("producto"))])

    calendario = modulos.obtener("calendario")

    if calendario:
        eventos = calendario.obtener_seccion("eventos")
        tareas = calendario.obtener_seccion("tareas")
        añadir("agenda", "Agenda", [{"texto": e.get("titulo", ""), "detalle": f"{e.get('fecha', '')} {e.get('hora') or ''}".strip()} for e in eventos if _coincide(clave, e.get("titulo"), e.get("fecha"))] + [{"texto": t.get("titulo", ""), "detalle": "tarea" + (" hecha" if t.get("hecha") else "")} for t in tareas if _coincide(clave, t.get("titulo"))])

    gastos = modulos.obtener("gastos")

    if gastos:
        añadir("gastos", "Gastos", [{"texto": f"{g['concepto'] or g['categoria']} — {g['importe']:.2f} €", "detalle": g["fecha"]} for g in reversed(gastos.obtener_seccion("gastos")) if _coincide(clave, g.get("concepto"), g.get("categoria"))])

    memoria = modulos.obtener("memoria")

    if memoria:
        recuerdos = [{**r, "tipo": t} for t in ("personas", "preferencias", "contexto", "proyectos") for r in memoria.obtener_seccion(t) if isinstance(r, dict)]
        añadir("memoria", "Cosas que recuerdo", [{"texto": r.get("texto", ""), "detalle": r["tipo"]} for r in recuerdos if _coincide(clave, r.get("texto"))])

    aparatos = modulos.obtener("electrodomesticos")

    if aparatos:
        añadir("aparatos", "Electrodomésticos", [{"texto": str(a.get("nombre", "")), "detalle": " ".join(str(a.get(k) or "") for k in ("marca", "modelo")).strip()} for a in aparatos.aparatos() if isinstance(a, dict) and _coincide(clave, a.get("nombre"), a.get("marca"), a.get("modelo"))])

    hogar = modulos.obtener("hogar")

    if hogar:
        añadir("hogar", "Tareas del hogar", [{"texto": t["nombre"], "detalle": f"le toca a {t['le_toca_a']}" if t["le_toca_a"] else ""} for t in hogar.listar() if _coincide(clave, t["nombre"], t["le_toca_a"])])

    documentos = modulos.obtener("documentos")

    if documentos:
        try:
            encontrados = documentos.buscar(texto, limite=limite)
        except Exception:
            encontrados = []

        añadir("documentos", "En tus manuales y notas", [{"texto": (r.get("texto") or "")[:160].replace("\n", " "), "detalle": r.get("documento") or ""} for r in encontrados])

    return {"consulta": texto, "total": sum(len(g["resultados"]) for g in grupos), "grupos": grupos}
