# BRAIN

**B**ase de **R**azonamiento y **A**utomatización con **I**nteligencia **N**atural.

BRAIN es un asistente personal modular diseñado para centralizar información, automatizar tareas y utilizar inteligencia artificial local para asistir en el día a día.

El objetivo final es convertirlo en el cerebro digital de la vivienda y de su propietario, integrando IA, memoria, automatización, domótica, salud, energía, inventario, voz y otros servicios en una única plataforma.

---

## Instalación rápida en Windows

1. Descarga el proyecto y descomprímelo (por ejemplo en `C:\BRAIN`).
2. Haz doble clic en **`INSTALAR.bat`** y espera. Instala Python y Ollama si faltan, descarga el modelo de IA y crea el icono **BRAIN** (con su logo) en el escritorio y el menú Inicio; BRAIN arranca con Windows.
3. Haz doble clic en el icono **BRAIN**. Se abre en su **propia ventana**, con un icono junto al reloj para que los avisos suenen aunque la cierres.

¿Prefieres un instalador con asistente? Haz doble clic en **`CREAR_SETUP.bat`**: crea **`instalbrain (versión).exe`**, que puedes copiar a otro PC (lleva Python incluido, sin ventana negra, conserva tus datos al actualizar y se desinstala desde *Configuración → Aplicaciones*).

Para usar BRAIN desde el móvil o fuera de casa: [`REMOTE_ACCESS.md`](docs/es/REMOTE_ACCESS.md) (o [en inglés](REMOTE_ACCESS.md)).

Guía paso a paso y solución de problemas: [`WINDOWS_GUIDE.md`](docs/es/WINDOWS_GUIDE.md) (o [en inglés](WINDOWS_GUIDE.md)).

| Archivo | Para qué sirve |
| --- | --- |
| `INSTALAR.bat` | Instala todo lo necesario (solo la primera vez) |
| `INICIAR.bat` | Abre BRAIN como programa (ventana propia e icono junto al reloj) |
| `INICIAR_NAVEGADOR.bat` | Abre BRAIN en el navegador |
| `CREAR_SETUP.bat` | Crea `instalbrain (versión).exe`, un instalador con asistente que puedes copiar a otro PC |
| `CONFIGURAR_ACCESO.bat` | Contraseña y acceso desde el móvil con Tailscale |
| `INICIAR_CONSOLA.bat` | Abre BRAIN como chat en la ventana negra |
| `DIAGNOSTICO.bat` | Muestra qué está instalado y qué falla |
| `MEJORAR_IA.bat` | Mide tu PC y descarga el mejor modelo de IA que le cabe |
| `CONFIGURAR_ENERGIA.bat` | Elige los sensores del inversor para ver la producción y el consumo en tiempo real |
| `CONFIGURAR_DOMOTICA.bat` | Conecta BRAIN con Home Assistant para controlar la casa ([guía](docs/es/SMART_HOME_GUIDE.md)) |

---

## 🐧 Instalar en Linux / macOS

El núcleo de BRAIN no tiene dependencias de pip, así que funciona igual en Linux y macOS que en Windows — solo sin la ventana propia, el icono junto al reloj y el instalador de doble clic, que son comodidades exclusivas de Windows.

### Opción A — directamente con Python

```bash
# 1. Instala Ollama y descarga un modelo (sáltate esto si ya tienes uno)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:4b          # va bien con 8 GB de RAM; mira la tabla de arriba para modelos más grandes

# 2. Arranca BRAIN
python3 main.py --web --no-browser
```

Después abre tú mismo `http://127.0.0.1:8765` (no hay icono que te avise de que ya está listo). Otras opciones útiles: `--console` (chatear en la terminal, sin interfaz web), `--diagnose` (ver qué está instalado y qué falla), `--upgrade-model` (medir tu equipo de nuevo y elegir un modelo mejor).

Para que siga funcionando al cerrar la terminal, usa `tmux`/`screen`, o móntalo como servicio de usuario de `systemd`.

### Opción B — Docker / Docker Compose (recomendado si no tienes ya Ollama)

Esto arranca Ollama y BRAIN, cada uno en su propio contenedor, ya conectados entre sí:

```bash
git clone https://github.com/CafeConFenix/BRAIN.git
cd BRAIN
docker compose up -d
```

Luego:

```bash
# Descarga un modelo la primera vez (solo hace falta una vez; se queda en el volumen ollama_data)
docker compose exec ollama ollama pull qwen3:4b
```

Abre `http://localhost:8765` y ya está. `docker compose logs -f brain` te muestra qué está haciendo BRAIN, `docker compose down` lo para (tus datos y modelos se quedan en sus volúmenes), y `docker compose up -d --build` lo reconstruye cuando actualices el código.

Qué hace el archivo de Docker Compose, explicado sin rodeos:
- **`ollama`**: ejecuta Ollama, con sus modelos guardados en el volumen `ollama_data` para que sobrevivan a reconstrucciones del contenedor. Si tienes una GPU NVIDIA, descomenta el bloque `deploy:` de `docker-compose.yml` (necesita el [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) instalado en tu máquina) para que use la GPU en vez de la CPU.
- **`brain`**: construye la imagen de BRAIN con el `Dockerfile` incluido y habla con el contenedor `ollama` por la red interna de Docker (`BRAIN_OLLAMA_URL=http://ollama:11434`) — no tienes que configurar nada para eso. Sus propios datos (despensa, historial de chat, copias de seguridad…) viven en el volumen `brain_data`, y el puerto `8765` queda publicado en tu máquina para que lo abras desde el navegador.

Home Assistant y el acceso remoto con Tailscale funcionan igual que en Windows: se conectan desde el panel de Ajustes de la propia interfaz web, sin necesidad de ningún contenedor extra.

**Lo que no aplica dentro de un contenedor:** la ventana propia, el icono junto al reloj y los avisos nativos de Windows (no hay escritorio donde mostrarlos — usarás la interfaz web en su lugar), y el micrófono (necesitaría pasar los dispositivos de audio del equipo anfitrión, que varía mucho según cómo tengas montado Docker; si necesitas voz, la Opción A de arriba es más sencilla).

---

## Estado del proyecto

**Versión:** 1.0.6 (README en inglés: [README.md](README.md))

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

* **Salud:** `save_weight`, `get_weight`, `weight_on_date`, `weight_history`
* **Inventario:** `add_inventory`, `add_many_to_inventory`, `remove_from_inventory`, `ran_out`, `show_inventory`, `search_inventory`, `delete_from_inventory`, `clear_inventory`
* **Compras:** `add_to_shopping`, `add_many_to_shopping`, `show_shopping_list`, `mark_bought`, `remove_from_shopping`, `clear_shopping_list`
* **Calendario:** `add_event`, `add_task`, `complete_task`, `show_agenda`
* **Energía:** `save_solar_production`, `show_solar_production`, `show_energy_now`
* **Recetas:** `available_ingredients` (despensa + básicos de casa), `list_staples`, `add_staple`, `remove_staple`
* **Memoria:** `remember`, `query_memory`, `forget`
* **Sensores:** `save_sensor`, `show_sensor`
* **Domótica:** `turn_on`, `turn_off`, `adjust_light`, `move_blind`, `set_temperature`, `activate_scene`, `list_devices`, `device_state`

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
* ✅ Interfaz web local (tema claro/oscuro, móvil): energía en directo, dispositivos con interruptores, despensa, compra, importación de listas, micrófono local (funciona en Brave) y lectura en voz alta
* ✅ Chat por consola

### Tests

* ✅ 177 tests automáticos que no necesitan Ollama ni tocan tus datos
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

├── docs/
├── main.py
├── INSTALAR.bat  INICIAR.bat  INICIAR_CONSOLA.bat  DIAGNOSTICO.bat
├── README.md
└── CHANGELOG.md
```

---

## Almacenamiento

Los datos se guardan dentro de `datos/` (puedes cambiar la carpeta con `BRAIN_DATA`). Lo que crece sin parar (peso, sensores, producción solar y energía) está en una base SQLite, `datos/brain.db`; el resto (despensa, compra, agenda, memoria y configuración) son archivos JSON que puedes abrir con el Bloc de notas. BRAIN hace una copia diaria en `datos/backups/` (se guardan las 5 últimas) y puedes pedirle "haz una copia de seguridad" o "restaura la última copia". Para que consulte tus manuales y notas, guarda archivos `.txt`, `.md` o `.json` en `datos/documentos/`. Para cambiar los sonidos de los avisos, copia tus `.wav`, `.mp3` u `.ogg` en `datos/sonidos/` y dile a BRAIN qué sonido quieres para cada tipo de aviso.

El objetivo es mantener la lógica de los módulos separada de la implementación del almacenamiento.

---

## Configuración

Opcional, mediante variables de entorno:

| Variable | Qué hace | Por defecto |
| --- | --- | --- |
| `BRAIN_MODEL` | Modelo de IA a usar (ej. `qwen3:8b`) | el mejor instalado |
| `BRAIN_DATA` | Carpeta de datos | `datos/` |
| `BRAIN_OLLAMA_URL` | Dirección de Ollama (si no existe se usa `OLLAMA_HOST`) | `http://127.0.0.1:11434` |
| `BRAIN_HA_URL` / `BRAIN_HA_TOKEN` | Home Assistant (alternativa a `CONFIGURAR_DOMOTICA.bat`) | los de `datos/domotica/` |
| `BRAIN_THINK` | `1` activa el "modo pensar" de Qwen 3 (más lento, más preciso) | desactivado |
| `BRAIN_CONTEXT` | Memoria de trabajo de la IA, en tokens | `16384` |
| `BRAIN_PORT` | Puerto de la interfaz web | `8765` |
| `BRAIN_VOICE_MODEL` | Modelo Whisper del micrófono (`base`, `small`, `medium`) | según tu RAM |

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
* Mejorar la capacidad de razonamiento y planificación de BRAIN.

---

Proyecto iniciado en agosto de 2026.
