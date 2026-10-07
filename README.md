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
| `MEJORAR_IA.bat` | Mide tu PC y descarga el mejor modelo de IA que le cabe |
| `CONFIGURAR_ENERGIA.bat` | Elige los sensores del inversor para ver la producción y el consumo en tiempo real |
| `CONFIGURAR_DOMOTICA.bat` | Conecta BRAIN con Home Assistant para controlar la casa ([guía](GUIA_DOMOTICA.md)) |

En Linux o macOS: `python3 main.py` (web), `python3 main.py --consola` o `python3 main.py --diagnostico`. Necesita Python 3.9 o superior y [Ollama](https://ollama.com/download) con algún modelo (`ollama pull qwen3:4b`). No hay que instalar ningún paquete de Python.

---

## Estado del proyecto

**Versión:** 0.7.0

### Núcleo

* ✅ Clase principal `Brain`
* ✅ Carga dinámica de módulos
* ✅ `DataManager` centralizado (escritura atómica, tolerante a archivos dañados y a bloqueos de Windows)
* ✅ `GestorConocimiento` (personalidad y memoria)
* ✅ Persistencia de datos mediante JSON
* ✅ Arquitectura modular y escalable (`ModuloBase`)
* ✅ Registro de eventos y errores en `datos/logs/`

### Módulos

* ✅ Salud (peso e historial)
* ✅ Inventario
* ✅ Energía (producción solar histórica y consumo/producción en tiempo real desde el inversor)
* ✅ Calendario (eventos y tareas)
* ✅ Compras
* ✅ Memoria
* ✅ Sensores
* ✅ Domótica (luces, enchufes, persianas, clima y escenas mediante Home Assistant)

### Sistema de herramientas

Las herramientas son funciones que la IA puede usar para consultar y modificar datos. Se registran con un decorador y se descubren solas: basta con crear un archivo en `brain/tools/builtin/`.

* **Salud:** `guardar_peso`, `obtener_peso`, `peso_en_fecha`, `historial_peso`
* **Inventario:** `anadir_inventario`, `anadir_varios_inventario`, `quitar_inventario`, `se_ha_acabado`, `ver_inventario`, `buscar_inventario`
* **Compras:** `anadir_a_compra`, `anadir_varias_a_compra`, `ver_lista_compra`, `marcar_comprado`
* **Calendario:** `anadir_evento`, `anadir_tarea`, `completar_tarea`, `ver_agenda`
* **Energía:** `guardar_produccion_solar`, `ver_produccion_solar`, `ver_energia_ahora`
* **Memoria:** `recordar`, `consultar_memoria`, `olvidar`
* **Sensores:** `guardar_sensor`, `ver_sensor`
* **Domótica:** `encender`, `apagar`, `regular_luz`, `mover_persiana`, `poner_temperatura`, `activar_escena`, `ver_dispositivos`, `estado_dispositivo`

### Inteligencia artificial

* ✅ Integración con Ollama (cliente propio, sin dependencias)
* ✅ Detección del hardware (RAM, tarjeta NVIDIA, disco) y elección del mejor modelo: Qwen 3.8 27B, Gemma 4 (26B / 12B / E4B / E2B) o Qwen 3 4B
* ✅ `BrainAI` como capa de abstracción de IA
* ✅ "Tool calling" nativo de Ollama, con respaldo para modelos que no lo admiten
* ✅ La IA puede encadenar varias herramientas en una misma respuesta
* ✅ La IA conoce la personalidad, la fecha actual y la memoria permanente

### Conversación e interfaces

* ✅ Historial de conversación persistente (se recuerda al cerrar y abrir)
* ✅ Consultas históricas ("¿cuánto pesaba el 5 de agosto?")
* ✅ Interfaz web local con panel de datos, dictado por voz y lectura en voz alta
* ✅ Chat por consola

### Tests

* ✅ 139 tests automáticos que no necesitan Ollama ni tocan tus datos
* ✅ `scripts/probar_ia.py` para una prueba con tu Ollama real

```text
python -m unittest discover -s tests -t .
```

---

## Arquitectura

```text
BRAIN/
├── brain/
│   ├── ai/
│   │   ├── brain_ai.py        # capa de IA: herramientas, historial, memoria
│   │   └── ollama.py          # cliente de Ollama
│   │
│   ├── base/
│   │   └── modulo.py          # clase base de los módulos
│   ├── core/
│   │   ├── brain.py
│   │   ├── config.py
│   │   ├── data_manager.py
│   │   ├── gestor_conocimiento.py
│   │   ├── logger.py
│   │   └── module_loader.py
│   │
│   ├── modules/               # calendario, compras, domotica, energia,
│   │                          # inventario, memoria, salud, sensores
│   ├── tools/
│   │   ├── builtin/           # herramientas que usa la IA
│   │   ├── decorators.py
│   │   ├── executor.py
│   │   └── registry.py
│   │
│   ├── voice/
│   │   └── conversation.py    # conversación con historial persistente
│   ├── web/
│   │   ├── servidor.py        # interfaz web local
│   │   └── static/index.html
│   ├── utils/
│   ├── cli.py                 # chat por consola y diagnóstico
│   ├── automation/            # (pendiente)
│   └── integrations/          # (pendiente)
│
├── datos/                     # todos los datos de BRAIN (JSON)
│   ├── conocimiento/personalidad.md
│   ├── salud/  inventario/  energia/  compras/  calendario/
│   ├── memoria/  sensores/  domotica/
│   ├── conversaciones/        # historial del chat
│   └── logs/
│
├── scripts/                   # instalador de Windows y prueba con IA real
├── tests/
├── docker/                    # Ollama + Open WebUI en Docker (Linux)
├── docs/
├── main.py
├── INSTALAR.bat  INICIAR.bat  INICIAR_CONSOLA.bat  DIAGNOSTICO.bat
├── README.md
└── CHANGELOG.md
```

---

## Almacenamiento

Los datos de los módulos se guardan en archivos JSON independientes dentro de `datos/` (puedes cambiar la carpeta con la variable de entorno `BRAIN_DATOS`). Son archivos de texto: puedes abrirlos con el Bloc de notas y hacer copia de seguridad copiando la carpeta.

El objetivo es mantener la lógica de los módulos separada de la implementación del almacenamiento.

---

## Configuración

Opcional, mediante variables de entorno:

| Variable | Qué hace | Por defecto |
| --- | --- | --- |
| `BRAIN_MODELO` | Modelo de IA a usar (ej. `qwen3:8b`) | el mejor instalado |
| `BRAIN_DATOS` | Carpeta de datos | `datos/` |
| `BRAIN_OLLAMA_URL` | Dirección de Ollama (si no existe se usa `OLLAMA_HOST`) | `http://127.0.0.1:11434` |
| `BRAIN_HA_URL` / `BRAIN_HA_TOKEN` | Home Assistant (alternativa a `CONFIGURAR_DOMOTICA.bat`) | los de `datos/domotica/` |
| `BRAIN_PENSAR` | `1` activa el "modo pensar" de Qwen 3 (más lento, más preciso) | desactivado |
| `BRAIN_CONTEXTO` | Memoria de trabajo de la IA, en tokens | `8192` |
| `BRAIN_PUERTO` | Puerto de la interfaz web | `8765` |

---

## Infraestructura

Entorno original de desarrollo (Linux):

* Ubuntu 26.04 LTS
* Python 3.14
* Docker
* Ollama
* Open WebUI
* NVIDIA Container Toolkit
* CUDA
* Git

En Windows basta con Python 3.9+ y Ollama, que instala `INSTALAR.bat`.

---

## Filosofía

BRAIN no es un único programa monolítico.

Es un conjunto de componentes independientes que trabajan juntos para formar un único cerebro digital.

Cada componente debe poder evolucionar, sustituirse o ampliarse sin obligar a modificar el resto del sistema.

La prioridad del proyecto es mantener una arquitectura limpia, modular y escalable antes de añadir funcionalidades complejas.

---

## Próximos objetivos

* Leer los sensores de Home Assistant para el panel y las automatizaciones.
* Incorporar automatizaciones inteligentes.
* Control por voz sin pantalla.
* Arranque automático con Windows.
* Notificaciones y recordatorios activos.
* Mejorar la capacidad de razonamiento y planificación de BRAIN.

---

Proyecto iniciado en agosto de 2026.
