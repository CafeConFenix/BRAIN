"""
Finds Spanish text where only English is allowed (code, comments, docs, scripts).

Spanish belongs to the translations: ``brain/locales/``, ``docs/es/``, ``README.es.md`` and the
test files whose name starts with ``test_es_``. Run it on its own to see what is left:

    python3 tests/language_scan.py [path ...]
"""

import io
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ALLOWED = (
    "brain/locales/",
    "brain/core/legacy/",
    "brain/i18n.py",
    "brain/core/personality_base.es.md",
    "docs/es/",
    "README.es.md",
    "installer/languages/",
    "tests/test_es_",
    "tests/language_scan.py",
    # By decision, the web UI only translates visible text (via the T() dictionary and
    # data-i18n attributes); its internal JS/CSS identifiers stay Spanish on purpose.
    "brain/web/static/index.html",
    # GHOST_PHRASES must keep its Spanish entries: they are real Whisper hallucinations
    # heard in Spanish audio, needed to filter them out. "sinc" (sinc filter) is a false
    # positive from the identifier list, not a Spanish word here.
    "brain/voice/recognition.py",
    # Regex character classes matching accented letters to tokenize user input that may
    # still be typed in Spanish (ñ, áéíóú) — not Spanish text in the code itself.
    "brain/modules/inventory.py",
    "brain/modules/documents.py",
    "brain/tools/registry.py",
    # Inno Setup [Messages] overrides for the installer's "es" language entry are meant
    # to be Spanish; that is the whole point of the block.
    "instalador/brain.iss",
    # The top nav link to the Spanish README is labeled "Español" on purpose.
    "README.md",
)

SKIP_FOLDERS = {".git", "__pycache__", "node_modules", ".github", "python", "dist", "build", "data", "venv"}
SCANNED = {".py", ".md", ".bat", ".ps1", ".iss", ".html", ".js", ".txt", ".toml", ".yml", ".webmanifest"}

ACCENTS = re.compile("[áéíóúñ¿¡ÁÉÍÓÚÑ]")
STOPWORDS = set(
    "el la los las del que una unos unas para por con sin hay tus mis pero como esta este esto muy cuando donde "
    "desde hasta porque tambien mas solo tiene tienes puede puedes quiero tengo nada todo todos tu su sus al".split()
)

IDENTIFIER_WORDS = set(
    """
abajo abierta abiertas abierto abrir acabado acceso accion acciones acento acentos activa activada activado
activar activas activo actualizar acumulado adivinada adivinar agotados ahora ahorro ajustar ajuste ajustes
alerta alertas algo alguna alternar alternativas ambiguo anadir analisis analizador analizar ancho anio
anotacion anotar antiguos anuncio anuncios apaga apagada apagadas apagado apagar aparato aparatos aparece
aplanar aplicacion aplicar aprox aproximado apuntado apuntados archivo archivos argumento argumentos arrancar
arranque arriba articulos asegurar asignados asignar asistente atras atributos autoarranque autoconsumo
autoenviar automatico automatizacion automatizaciones autoprueba autorizado avances avisadas avisados avisar
aviso avisos ayuda añadidos añadir baja bajo bajos bandeja baratas barra bascula basica basicas basico basicos
basura bateria bien bloque bloqueado bloqueo borrado borrados borrar boton botones bruto bucle buenas busca
buscador buscar busqueda cabecera cabeceras cada cadena caduca caducado caducan caducar caducidad caducidades
caja calculado calendario cambiado cambiados cambiar cambios camino campana cancelar candidata candidatas
candidato candidatos cantidad capa capacidades caracteres carga cargada cargar carpeta caso catalogo categoria
categorias cena centro cerebro cerrada cerrado cerrados cerrar cerrojo chispa cierra cierre cifra cifras clase
clases cliente cocina cocinar codificacion codificado codigo coincidencia coincidencias comando comandos
comida comidas comparacion comparar completado completar completo componer compra comprado comprados comprar
compras comprobacion comprobar concepto condicion condiciones conectada conectado conectar conexion conexiones
configurables configuracion configurada configurado configurar confirmar congelador conjunto conmutar
conocimiento consejo conservar consola construir consulta consultar consultas consumibles consumo consumos
contador contadores contenedor contenido conteo contexto controlable controlables conv conversacion
conversaciones convertidos convertir copia copiar copias correcta correcto corriente corta corte corto creada
crear criticas critico crudo cuando cuarto cubierto cuenta cuentas cuerpo cumple cumplido cumplidos danado
dañado debe decir defecto degradado depurar derecho derivar desactivada desactivar descarga descargado
descargados descargar descartar descifrar desconocida desconocido describir descripcion descripciones desde
desp despensa despertar despues destino destinos detalle deteccion detectar detener diagnostico dialogo diaria
diario dibujar dichas diferencia direccion direcciones disp disparador disparadores disponible disponibles
dispositivo dispositivos distinto documento documentos dominio dominios domotica duracion edad editar
ejecucion ejecuciones ejecutable ejecutadas ejecutar ejecutarse ejemplos electrodomestico electrodomesticos
elegido elegidos elegir elementos eliminadas eliminar empezar empieza encabezados encender encendida encendido
encendidos enciende encontrada encontrado encontrados encontrar energia entender entidad entidades entiende
entorno entrada entradas entrar entre entrega enviadas enviados enviar equipo escala escaneado escena escenas
escribir escritorio escucha escuchan espejo espera esperada esperadas esperado esperados esperar esquema
esquemas establecer estado estados estan estandar estaticos estricta estricto etiqueta etiquetas evaluar
evento eventos exacta exacto exactos excedentes exceso excluidas exige exigencia existe existen existente
explicacion explicita fallida fallido fallo fallos falsa falso falta faltan faltantes fantasma fecha fechas
ficha fijar filtrar filtro firma fisica flujo flujos fondo forma formato formulario forzar fragmento
fragmentos franja frase frases frecuencia frente frigorifico fuente fuera funcion garantia garantias gastado
gasto gastos gestor grabacion grabando grados grande grupo grupos guardada guardado guardados guardar
habitacion habitaciones habito habitos hablar hace hasta hecha hechas hecho hechos hemisferio herramienta
herramientas hexa hijo hilo historial historiales historico hizo hogar icono iconos identificador imagen
importar importe incluir incorrecto independientes indice inexistente ingrediente ingreso ingresos inicial
inicializadas iniciar inicio instalacion instalaciones instalado instalados instalando instalar instancia
instancias instrucciones intento intentos interactivo intercambio interpretada interpretar interruptor
interruptores intervalo invalida invalido inventario inversor invertida iteraciones izquierdo lado lanzador
lanzadores lanzar larga lectura lecturas leida leidas leido leidos lenta letra libre lienzo limitar limite
limpia limpiar limpio limpios linea lineas lista listado listar listas listo llamada llamadas lobulos longitud
magnitud malo manda manejador manejar manifiesto manipulado mantenimiento marca marcados marcar marcas marcha
margen masiva matar maximo medida medidas medio mejor mejorar mejores memoria mensaje mensajes meses metodo
mezcla mezclar microfono migra migracion migrar minimo minuto minutos misma mismo mitad modelo modelos modo
molestar momento mostrado mostrar motivo mucho muestras nada nativa nativo navegador neto ninguno nivel
niveles noches nodo nodos nombre nombres normalizar nota notas notificacion notificaciones notificador
notificar novedades nucleo nueva nuevamente nuevas nuevo nuevos numero numeros objetivo obligatorio obtener
ocultos ocupado ocupados ofrecer olvidar omitir opcion opciones operador orden ordenador oscuro otra otras
otro otros pagina palabra palabras paquete parametro parametros parar parche parcial parciales parece
parecidas parecidos parentesis parrafo parrafos parsear parte pasado pasar paso pasos pausa pedido pedidos
pedir pegada peligro pendientes pensamiento pensando pensar pequena pequeno perfil perfiles permitido persiana
persistente personalidad pestanas peticion peticiones pico pide pieza piezas pintar pista pistas pitido placas
planificador plantilla poner porcentaje posicion posiciones positivo potencia potencias precargar precio
predeterminadas preferencias preferido preferidos prefijo pregunta preguntar preguntas preparacion preparar
presu presupuesto previa previo primario primera probar problema problemas proceso procesos produccion
producto productos profundidad programa programar progreso prohibidas propiedad propiedades proxima proyecto
prueba publicacion publicar publicos puerta punto puntos puntuar queda quien quitado quitados quitar racha
raiz rango rapida rapido razon recargar receta recetas rechazado rechazar recibida recibido recibir
recomendacion recomendado recomendar reconfigurar reconocedor reconocimiento recordar recordatorio
recordatorios recortar recuerdos redactar redondeada reducir refrescar refuerzo registradas registrado
registro registros regla reglas reintentar relanzar relativa relativo relativos relleno reloj remoto
remuestrear remuestreo renderizar renombrar reparacion reparador repetida repetido reproducir republicar
requerido resolver respeta resplandor respuesta respuestas restante restantes restaurar resto restos resultado
resultados resumen resumir retraso revisar rotacion rotar roto ruta rutas rutina rutinas sacar sala salen
salgo salida salido salir saltar salud saludo seccion secciones secreto secundario segmentos seguir seguridad
seguro seleccion semana semanal senal separador servicio servicios servidor servir sesion sesiones señal
siempre siguiente silenciar silencio silencioso sinc sinonimos sistema sitio sitios situaciones sobran
sobrante sobrantes sobre solape solicitado sombra sondeo sonido sonidos subir suelta suelto sugerencias
sugerida sugeridos suma sumar superado sustituir tamano tamanos tamaño tarea tareas tarifa tema temas
temperatura temperaturas temporizador terminar termino terminos termostato texto textos tiempo tiempos tiene
tipo tipos titulo toca tocado tocar todo todos tokenizar tomar tono traer tramas tramo transcribir tras trazo
trocear trozo trozos turno ubicacion ubicaciones unidad unidades usadas usan usar usuario vacia vaciar vacias
vacio vacios valida validaciones validar valido valle varios vatios veces vencidos vendido vendidos venta
ventana verificar vieja vineta visto vistos vivo viñeta ybuscador
""".split()
)

# Words that are Spanish identifiers but also fine in English code (for example library names).
IDENTIFIER_OK = {"aviso"} - {"aviso"}

LITERAL = re.compile(r"[A-Za-z]+")


def looks_spanish(text: str) -> bool:
    """True if a piece of text (a message, a comment) is written in Spanish."""

    if ACCENTS.search(text):
        return True

    words = [w.lower() for w in LITERAL.findall(text)]

    return sum(1 for w in words if w in STOPWORDS) >= 2


def spanish_identifier(name: str) -> bool:
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower().split("_")

    return any(p in IDENTIFIER_WORDS for p in parts)


def scan_python(text: str):
    found = []

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return found

    for token in tokens:
        kind, value, (line, _), _, _ = token

        if kind == tokenize.COMMENT and looks_spanish(value):
            found.append((line, "comment", value.strip()))
        elif kind in (tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", -1)) and looks_spanish(value):
            found.append((line, "text", value.strip()[:100]))
        elif kind == tokenize.NAME and spanish_identifier(value):
            found.append((line, "name", value))

    return found


def scan_lines(text: str):
    found = []

    for number, line in enumerate(text.splitlines(), 1):
        if looks_spanish(line):
            found.append((number, "text", line.strip()[:100]))

    return found


def allowed(relative: str) -> bool:
    return any(relative.startswith(prefix) for prefix in ALLOWED)


def files(paths=None):
    for base in paths or [ROOT]:
        base = Path(base)

        for path in ([base] if base.is_file() else sorted(base.rglob("*"))):
            relative = path.relative_to(ROOT).as_posix() if path.is_absolute() or ROOT in path.parents else path.as_posix()

            if not path.is_file() or path.suffix not in SCANNED or SKIP_FOLDERS & set(path.relative_to(ROOT).parts):
                continue

            if allowed(relative):
                continue

            yield relative, path


def scan(paths=None):
    """[(relative path, line, kind, text)] of everything that is not English."""

    result = []

    for relative, path in files(paths):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for line, kind, value in scan_python(text) if path.suffix == ".py" else scan_lines(text):
            result.append((relative, line, kind, value))

    return result


if __name__ == "__main__":
    targets = [Path(a).resolve() for a in sys.argv[1:]] or None
    problems = scan(targets)

    for relative, line, kind, value in problems:
        print(f"{relative}:{line}: [{kind}] {value}")

    print(f"{len(problems)} problems")
    sys.exit(1 if problems else 0)
