# Changelog

Todos los cambios relevantes de BRAIN se documentan en este archivo.

---

<<<<<<< HEAD
## [0.10.0] - 2026-10-11

### Añadido

* **Resumen diario proactivo**: cada mañana (por defecto a las 8:30, si BRAIN está abierto; si lo abres más tarde llega entonces, hasta las 21:00) te llega un aviso con tu agenda de hoy y mañana, tareas, recordatorios, lista de la compra, producción solar de ayer, alertas de sensores, garantías que caducan y tu peso. Herramientas `ver_resumen_diario` y `configurar_resumen_diario` ("mándame el resumen a las 7:45").
* **Avisos con sonido**: centro de avisos (campana en la web, histórico en SQLite) con notificaciones de Windows y sonido propio. Cada tipo de aviso (`alerta`, `recordatorio`, `resumen`, `automatizacion`, `energia`, `info`) puede tener su sonido: copia archivos `.wav`, `.mp3` u `.ogg` en `datos/sonidos/` y pídele a BRAIN "pon el sonido campana.wav a los recordatorios". Franja de "no molestar" (por defecto 23:00-07:00; las alertas críticas suenan siempre) y modo silencio. Recordatorios ("recuérdame en 20 minutos sacar el pollo") y aviso 30 minutos antes de los eventos de la agenda con hora. Herramientas: `crear_recordatorio`, `ver_recordatorios`, `cancelar_recordatorio`, `ver_avisos`, `marcar_avisos_leidos`, `ver_sonidos`, `asignar_sonido`, `configurar_avisos`, `probar_aviso`.
* **Automatizaciones en lenguaje natural**: "cuando las placas pasen de 3 kW avísame", "todas las noches a las 23:30 apaga las luces". Disparadores por hora (con días), por estado de un dispositivo o por energía; acciones de aviso, encender, apagar y escena (nunca cerraduras, garajes ni alarmas). Herramientas `crear_automatizacion`, `ver_automatizaciones`, `borrar_automatizacion`, `activar_automatizacion`, `ejecutar_automatizacion`.
* **Optimizador de energía**: con el histórico del inversor, `ver_consejo_energia` dice a qué horas sobra producción solar (las mejores para lavadora, lavavajillas o termo), cuándo consume más la casa y cómo va la producción diaria.
* **Báscula por imagen**: el botón de la cámara del chat envía una captura de la app de tu báscula; un modelo de visión de Ollama lee el peso (y grasa, IMC, agua, masa muscular, etc. si salen), BRAIN valida los números y lo guarda. Los datos fuera de rango se rechazan en vez de guardarse mal. Necesita un modelo con visión instalado (BRAIN te lo dice si no lo hay). Herramienta `ver_medidas_corporales`.
* **Electrodomésticos**: guarda marca, modelo, fecha de compra y garantía de cada aparato; si falla uno, `consultar_electrodomestico` junta su ficha con los fragmentos de sus manuales en `datos/documentos/` para diagnosticar. El resumen diario avisa de las garantías que caducan. Herramientas `anadir_electrodomestico`, `ver_electrodomesticos`, `quitar_electrodomestico`, `consultar_electrodomestico`.
* **Conversaciones en paralelo**: pestañas en el chat para tener varias conversaciones independientes (por ejemplo una solo de recetas), cada una con su historial y, si quieres, un tema que BRAIN sigue solo en ella.

### Cambiado

* **La IA recibe solo las herramientas del tema**: con 70 herramientas, sus descripciones ocupaban unos 11.000 tokens de los 16.384 de contexto y habrían vuelto las respuestas vacías. Ahora en cada pregunta se envían solo las de los temas de los que se habla (y de lo último de la conversación); el resto siguen disponibles cuando toca.
* Herramientas totales: 48 -> 70.

---

## [0.9.0] - 2026-10-11

### Añadido

* **Base de datos SQLite** (`brain/core/database.py`, archivo `datos/brain.db`, solo biblioteca estándar): peso, lecturas de sensores, producción solar diaria y un histórico nuevo de energía en tiempo real pasan de JSON a tablas con índices por fecha. Cada operación usa `with sqlite3.connect(...)` (se confirma entera o se deshace) y los datos antiguos se migran solos al primer arranque (queda un `.premigracion` de cada JSON). Las 42 herramientas anteriores conservan su firma. Despensa, compra, agenda, memoria y configuración siguen en JSON.
* **Planificador en segundo plano** (`brain/core/scheduler.py`): un hilo propio que arranca con `main.py` sin bloquear la web ni la consola; un error en una tarea se anota y nunca la detiene. Tareas por defecto: copia de seguridad diaria y sondeo de Home Assistant cada 120 s (`BRAIN_SONDEO_SEGUNDOS`), que guarda la energía en el histórico y vigila sensores de humo, gas, CO, fugas de agua y similares. `BRAIN_PLANIFICADOR=0` lo desactiva.
* **Copias de seguridad** (`brain/modules/sistema.py`): `crear_copia_seguridad`, `ver_copias_seguridad` y `restaurar_copia_seguridad`. ZIP `backup_AAAAMMDD_HHMMSS.zip` en `datos/backups/` con manifiesto de sumas SHA-256 (no incluye los modelos de voz, que se pueden volver a bajar). Solo se conservan las 5 últimas. Restaurar valida el ZIP, guarda antes el estado actual (`prerestauracion_*.zip`) y lo recupera si algo falla. Panel "Copias de seguridad" en la web.
* **`anadir_faltantes_receta_a_compra`**: compara los ingredientes de una receta con frigorífico, congelador, despensa y básicos de casa y apunta de una sola vez en la compra los que faltan o están agotados, sin duplicar lo que ya estaba en la lista. Entiende "2 huevos", "200 g de harina" y plurales.
* **Documentos locales** (`brain/modules/documentos.py`): `buscar_en_documentos` y `leer_documento` sobre los `.txt`, `.md` y `.json` de `datos/documentos/`, con fragmentos y puntuación BM25 en Python puro (sin embeddings). El índice se actualiza solo al cambiar los archivos.

### Cambiado

* Herramientas totales: 42 -> 48 (6 nuevas: `anadir_faltantes_receta_a_compra`, `crear_copia_seguridad`, `ver_copias_seguridad`, `restaurar_copia_seguridad`, `buscar_en_documentos`, `leer_documento`).

---

## [0.8.0] - 2026-10-09

### Corregido

* **Respuestas vacías ("No he podido generar una respuesta")**: las descripciones de las herramientas ocupan unos 5.000 tokens y la memoria de trabajo de la IA era de 8.192, así que el modelo perdía sus instrucciones. Ahora son 16.384, los mensajes largos se guardan recortados en el historial y, si el modelo contesta vacío, se le pide una vez más antes de rendirse (con un mensaje útil si falla).
* **Una lista pegada acababa en la lista de la compra**: ahora una lista larga de productos (como las de un pedido del supermercado) se guarda directamente en la despensa, sin pasar por la IA, y solo va a la compra si lo dices ("...a la lista de la compra").
* El analizador de listas entiende `Nombre: 2 unidades`, `unids`, `uds`, `aprox.`, `Huevos (12)`, títulos que acaban en ":" y una frase de introducción antes de la lista.
* Móvil: el chat ya no se sale de la pantalla.

### Añadido

* **Importar lista** (botón en la despensa y en la compra): pegas el texto tal cual, eliges el sitio (despensa, nevera, congelador o compra), BRAIN te enseña lo que ha entendido y lo añade al confirmar.
* **Borrar**: botón × en cada producto, "Vaciar" (con confirmación) y herramientas `quitar_de_compra`, `vaciar_lista_compra`, `borrar_del_inventario`, `vaciar_inventario` ("borra la lista de la compra" ya funciona).
* **Recetas con tu despensa**: `ingredientes_disponibles` da a la IA lo que hay en casa más los **básicos** (agua, aceite, sal, azúcar, harina, especias...). Los básicos se pueden editar ("ya no tengo comino", `anadir_basico`, `quitar_basico`, `ver_basicos`) y se ven en el panel.
* **Domótica en el panel**: los dispositivos encontrados aparecen por habitación, con un interruptor para encender o apagar (luces, enchufes, ventiladores, persianas, climatización, televisiones) y botones para las escenas. Sigue sin poder tocar cerraduras, puertas, garajes ni alarmas.
* **Micrófono que funciona en Brave** (y en cualquier navegador): la web graba, BRAIN transcribe en tu PC con Whisper (`faster-whisper`) y el audio no sale del ordenador. Se instala una vez con el botón "Instalar voz" (unos 500 MB). En Chrome y Edge se sigue usando el reconocimiento del propio navegador si no lo instalas.
* **Interfaz nueva**: tema claro y oscuro (con botón), energía en tiempo real arriba a la derecha, chat con negritas y listas, versión móvil con pestañas.

### Quitado

* La tarjeta "Producción solar (histórico)": en su lugar está "Energía ahora".

---

=======
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
## [0.7.0] - 2026-10-07

### Corregido

* **Los productos no se guardaban en el inventario** (y la IA decía que sí): cualquier herramienta con un parámetro llamado `nombre` (`anadir_inventario`, `quitar_inventario`) fallaba siempre con "got multiple values for argument 'nombre'". Arreglado de raíz y con test de regresión.
* Cantidades con texto ("1 unidad", "2 uds", "1,5 kg", "dos") ya no dan error.
* Los argumentos inventados por la IA se ignoran en vez de fallar; una ubicación desconocida ("armario de la cocina") va a la despensa; la memoria acepta cualquier tipo desconocido y "todo/recuerdos" para verlo todo.
* La IA puede encadenar hasta 12 pasos (antes 6) y, si no llega a terminar, lo dice con claridad en vez de inventar que lo hizo.
* **Diagnóstico**: ya no se rompe en Windows por la codificación de `netstat`/`tasklist`.
* **Instalador**: ya no da un falso "Ollama sigue sin tener ningún modelo" tras descargarlo bien; BRAIN comprueba por sí mismo que el modelo aparece en Ollama y, si no, lo dice con instrucciones.

### Añadido

* **Carga masiva**: `anadir_varios_inventario` y `anadir_varias_a_compra` entienden listas pegadas tal cual ("Leche entera, 2 unidades", "2 x huevos", "Pan x3"), en una sola operación.
* **"Se ha acabado"**: `se_ha_acabado` quita el producto del inventario y lo apunta en la lista de la compra. Gastar la última unidad con `quitar_inventario` también lo apunta.
* **Panel de la despensa** en la interfaz web: todo el inventario agrupado por ubicación, con cantidades.
* **Energía en tiempo real**: panel "Energía ahora" (producción, consumo, compra/venta a la red, batería) que se actualiza cada 5 segundos, y herramienta `ver_energia_ahora` ("¿cuánto estoy consumiendo?"). Lee el inversor y el contador a través de Home Assistant (Huawei, Fronius, SolarEdge, Growatt, Solax, GoodWe, Victron, Shelly...). Detecta los sensores solo; `CONFIGURAR_ENERGIA.bat` permite elegirlos a mano.

---

## [0.6.0] - 2026-10-07

### Añadido

* **Domótica con Home Assistant**: BRAIN controla luces (encender, apagar, brillo, color, tono blanco), enchufes, persianas, termostatos y escenas, y lee sensores. Funciona con cualquier marca que tenga Home Assistant. Entiende nombres y habitaciones ("la luz del salón", "todas las luces de la cocina") y pregunta si hay dudas.
  * 8 herramientas nuevas: `encender`, `apagar`, `regular_luz`, `mover_persiana`, `poner_temperatura`, `activar_escena`, `ver_dispositivos`, `estado_dispositivo`.
  * `CONFIGURAR_DOMOTICA.bat`: asistente que busca Home Assistant y prueba la conexión.
  * Seguridad: nunca abre cerraduras, puertas, garajes ni portones, ni toca alarmas (solo lectura).
  * Guía: `GUIA_DOMOTICA.md`.
* **Elección automática del mejor modelo de IA según el PC** (`MEJORAR_IA.bat` / `main.py --mejorar-ia`): mide RAM, tarjeta NVIDIA (VRAM) y disco libre y elige entre Qwen 3.8 27B, Gemma 4 (26B, 12B, E4B, E2B) o Qwen 3 4B. Si una descarga falla, prueba el siguiente más pequeño. El instalador usa este mismo sistema.
* El diagnóstico muestra las características del equipo, el modelo ideal, lo que ve `ollama list` y qué programa escucha en el puerto de Ollama.

### Corregido

* **«IA no disponible» tras instalar**: BRAIN solo intentaba arrancar Ollama una vez (8 s). Ahora lo reintenta solo en segundo plano (hasta 90 s por intento), la página consulta más a menudo mientras tanto y hay un botón **Reintentar**.
* **«Ollama funciona pero no tiene ningún modelo»**: BRAIN descarga ahora el modelo a través del mismo Ollama que luego usa (antes, `ollama pull` podía instalarlo en otro sitio). La interfaz web ofrece un botón **Descargar IA** con barra de progreso.
* BRAIN respeta la variable `OLLAMA_HOST`, igual que el comando `ollama`.
* El instalador comprueba al final que el modelo aparece de verdad en Ollama.

---

## [0.5.0] - 2026-10-07

### Añadido

* **Soporte completo para Windows 10 y 11**:
  * `INSTALAR.bat`: instala Python y Ollama si faltan, descarga un modelo de IA, comprueba BRAIN y crea un acceso directo en el escritorio.
  * `INICIAR.bat` (interfaz web), `INICIAR_CONSOLA.bat` (chat en la ventana negra) y `DIAGNOSTICO.bat`.
  * Consola en UTF-8: se acabaron los errores con tildes, eñes y emojis en la consola de Windows.
  * Escritura de datos tolerante a los bloqueos de antivirus / OneDrive.
* **Interfaz web local** (`http://127.0.0.1:8765`): chat, panel con peso, agenda, compra, energía solar, dictado por voz y lectura en voz alta. Solo accesible desde el propio equipo.
* **Chat por consola** (`python main.py --consola`) con comandos `/ayuda`, `/herramientas`, `/modelos`, `/limpiar`, `/salir`.
* `python main.py --diagnostico` para ver qué está instalado y qué falla.
* **Memoria persistente de la conversación**: BRAIN recuerda lo hablado aunque se cierre y se vuelva a abrir.
* **Memoria permanente**: herramientas `recordar`, `consultar_memoria` y `olvidar`; lo recordado se incluye siempre en el contexto de la IA.
* **Consultas históricas**: `peso_en_fecha`, `historial_peso` (con variación entre registros).
* **Varias herramientas en una misma respuesta** (hasta 6 pasos encadenados).
* **22 herramientas** nuevas para Inventario, Compras, Calendario/Agenda, Energía solar, Memoria y Sensores.
* "Tool calling" nativo de Ollama, con respaldo automático a órdenes JSON en texto para modelos que no lo soportan.
* La IA recibe la personalidad (`personalidad.md`), la fecha y hora actuales y la memoria permanente.
* Tests offline con un Ollama simulado (72 pruebas, no necesitan IA real ni tocan tus datos) y `scripts/probar_ia.py` para probar con tu Ollama real.
* Registro de errores y eventos en `datos/logs/`.
* `.gitattributes` (los `.bat` mantienen saltos de línea de Windows) y `pyproject.toml` (Black).

### Modificado

* Todos los datos viven ahora en `datos/` (se fusionó la carpeta duplicada `brain/datos/`).
* `guardar_peso` y la producción solar actualizan el registro del día en vez de duplicarlo; la fecha es opcional (por defecto, hoy).
* Los módulos comparten una clase base (`ModuloBase`) en lugar de repetir código.
* `brain.core` carga `Brain` de forma diferida para evitar importaciones circulares.
* `requirements.txt` ya no lista paquetes (BRAIN solo usa la biblioteca estándar); las herramientas de desarrollo pasan a `requirements-dev.txt`.
* Ollama: se usa `127.0.0.1` en lugar de `localhost` (en Windows `localhost` suele resolverse a IPv6), se ignora el proxy del sistema y se amplía el contexto a 8192 tokens.

### Corregido

* La conversación no recordaba mensajes anteriores (el historial no llegaba a la IA).
* Errores de codificación al imprimir con la consola de Windows.
* Tests que escribían en los datos reales y dependían de que Ollama estuviera encendido.
* Datos duplicados de pruebas en peso, producción solar e inventario.

---

## [0.4.0] - 2026-08-10

### Añadido

* Sistema de inteligencia artificial local mediante Ollama.
* Cliente Python para comunicación con la API de Ollama.
* Capa `BrainAI` para abstraer el proveedor de inteligencia artificial.
* Detección de modelos disponibles.
* Soporte para Qwen 3 4B y Qwen 3 8B.
* Sistema de herramientas registrables mediante decoradores.
* Registro central de herramientas.
* Ejecutor de herramientas.
* Primeras herramientas funcionales para el módulo Salud:

  * `guardar_peso`
  * `obtener_peso`
* Integración entre IA y herramientas.
* Capa básica de conversación.
* Historial de conversación.
* Tests para herramientas, IA y conversación.
* `.gitignore` para excluir cachés, entornos virtuales y archivos temporales.

### Modificado

* Reestructurado el núcleo de BRAIN.
* Centralizado el acceso a datos mediante `DataManager`.
* Mejorado el cargador dinámico de módulos.
* Migrados los módulos a la nueva arquitectura.
* Actualizado `main.py` para utilizar la nueva arquitectura.
* Separada la capa de IA de la lógica principal de BRAIN.
* Separado el sistema de herramientas de los módulos.
* Almacenamiento organizado por módulos mediante archivos JSON.

### Eliminado

* `brain/herramientas.py`, sustituido por el nuevo sistema de herramientas.
* Archivos `.pyc` y directorios `__pycache__` que estaban bajo control de Git.

### Estado

BRAIN dispone por primera vez de un flujo funcional completo:

```text
Usuario
   ↓
BRAIN
   ↓
IA local
   ↓
Decisión
   ↓
Herramienta
   ↓
Módulo
   ↓
DataManager
   ↓
Datos JSON
```

La siguiente etapa se centrará en memoria persistente, consultas históricas y una integración más profunda entre conversación, memoria y herramientas.

---

## [0.3.0] - 2026-08

### Añadido

* Núcleo modular de BRAIN.
* Sistema de módulos.
* `DataManager`.
* Gestor de conocimiento.
* Persistencia independiente por módulo.
* Migración del módulo Inventario a `inventario.json`.
* Estructura modular para Salud, Energía, Inventario y otros módulos.

---

## [0.2.0]

### Añadido

* Arquitectura inicial de BRAIN.
* Sistema inicial de conocimiento.
* Persistencia de datos.
* Primer programa funcional.
* Entorno virtual de Python.
* Formateo mediante Black.
