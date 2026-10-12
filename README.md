# BRAIN

**B**ase de **R**azonamiento y **A**utomatización con **I**nteligencia **N**atural.

BRAIN es un asistente personal modular diseñado para centralizar información, automatizar tareas y utilizar inteligencia artificial local para asistir en el día a día.

El objetivo final es convertirlo en el cerebro digital de la vivienda y de su propietario, integrando IA, memoria, automatización, domótica, salud, energía, inventario, voz y otros servicios en una única plataforma.

---

## Instalación rápida en Windows

1. Descarga el proyecto y descomprímelo (por ejemplo en `C:\BRAIN`).
2. Haz doble clic en **`INSTALAR.bat`** y espera. Instala Python y Ollama si faltan, descarga el modelo de IA y crea un icono **BRAIN** en el escritorio.
3. Haz doble clic en el icono **BRAIN** (o en `INICIAR.bat`). Se abre el navegador con el chat.

Guía paso a paso y solución de problemas: [`INSTRUCCIONES_WINDOWS.md`](INSTRUCCIONES_WINDOWS.md).

| Archivo | Para qué sirve |
| --- | --- |
| `INSTALAR.bat` | Instala todo lo necesario (solo la primera vez) |
| `INICIAR.bat` | Abre BRAIN con interfaz web en el navegador |
| `INICIAR_CONSOLA.bat` | Abre BRAIN como chat en la ventana negra |
| `DIAGNOSTICO.bat` | Muestra qué está instalado y qué falla |
| `MEJORAR_IA.bat` | Mides tu PC y descarga el mejor modelo de IA que le cabe |
| `CONFIGURAR_ENERGIA.bat` | Elige los sensores del inversor para ver la producción y el consumo en tiempo real |
| `CONFIGURAR_DOMOTICA.bat` | Conecta BRAIN con Home Assistant para controlar la casa ([guía](GUIA_DOMOTICA.md)) |

En Linux o macOS: `python3 main.py` (web), `python3 main.py --consola` o `python3 main.py --diagnostico`. Necesita Python 3.9 o superior y [Ollama](https://ollama.com/download) con algún modelo (`ollama pull qwen3:4b`). No hay que instalar ningún paquete de Python.


### Núcleo

- ✅ Clase principal `Brain`
- ✅ Carga dinámica de módulos
- ✅ `DataManager` centralizado (escritura atómica, tolerante a archivos dañados y a bloqueos de Windows)
- ✅ `GestorConocimiento` (personalidad y memoria)
- ✅ Persistencia de datos mediante JSON
- ✅ Arquitectura modular y escalable (`ModuloBase`)
- ✅ Registro de eventos y errores en `datos/logs/`

### Módulos

- ✅ Salud (peso e historial)
- ✅ Inventario
- ✅ Energía (producción solar histórica y consumo/producción en tiempo real desde el inversor)
- ✅ Calendario (eventos y tareas)
- ✅ Compras
- ✅ Memoria
- ✅ Sensores
- ✅ Domótica (luces, enchufes, persianas, clima y escenas mediante Home Assistant)

### Sistema de herramientas

Las herramientas son funciones que la IA puede usar para consultar y modificar datos. Se registran con un decorador y se descubren solas: basta con crear un archivo en `brain/tools/builtin/`.

- **Salud:** `guardar_peso`, `obtener_peso`, `peso_en_fecha`, `historial_peso`
- **Inventario:** `anadir_inventario`, `anadir_varios_inventario`, `quitar_inventario`, `se_ha_acabado`, `ver_inventario`, `buscar_inventario`, `borrar_del_inventario`, `vaciar_inventario`
- **Compras:** `anadir_a_compra`, `anadir_varias_a_compra`, `ver_lista_compra`, `marcar_comprado`, `quitar_de_compra`, `vaciar_lista_compra`
- **Calendario:** `anadir_evento`, `anadir_tarea`, `completar_tarea`, `ver_agenda`
- **Energía:** `guardar_produccion_solar`, `ver_produccion_solar`, `ver_energia_ahora`
- **Recetas:** `ingredientes_disponibles` (despensa + básicos de casa), `ver_basicos`, `anadir_basico`, `quitar_basico`
- **Memoria:** `recordar`, `consultar_memoria`, `olvidar`
- **Sensores:** `guardar_sensor`, `ver_sensor`
- **Domótica:** `encender`, `apagar`, `regular_luz`, `mover_persiana`, `poner_temperatura`, `activar_escena`, `ver_dispositivos`, `estado_dispositivo`

### Inteligencia artificial

- ✅ Integración con Ollama (cliente propio, sin dependencias)
- ✅ Detección del hardware (RAM, tarjeta NVIDIA, disco) y elección del mejor modelo: Qwen 3.8 27B, Gemma 4 (26B / 12B / E4B / E2B) o Qwen 3 4B
- ✅ `BrainAI` como capa de abstracción de IA
- ✅ "Tool calling" nativo de Ollama, con respaldo para modelos que no lo admiten
- ✅ La IA puede encadenar varias herramientas en una misma respuesta
- ✅ La IA conoce la personalidad, la fecha actual y la memoria permanente

### Conversación e interfaces

- ✅ Historial de conversación persistente (se recuerda al cerrar y abrir)
- ✅ Consultas históricas ("¿cuánto pesaba el 5 de agosto?")
- ✅ Interfaz web local (tema claro/oscuro, móvil): energía en directo, dispositivos con interruptores, despensa, compra, importación de listas, micrófono local (funciona en Brave) y lectura en voz alta
- ✅ Chat por consola

### Tests

- ✅ 177 tests automáticos que no necesitan Ollama ni tocan tus datos
- ✅ `scripts/probar_ia.py` para una prueba con tu Ollama real

```text
python -m unittest discover -s tests -t .