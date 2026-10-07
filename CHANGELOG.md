# Changelog

Todos los cambios relevantes de BRAIN se documentan en este archivo.

---

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
