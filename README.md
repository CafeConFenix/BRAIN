# BRAIN

**B**ase de **R**azonamiento y **A**utomatización con **I**nteligencia **N**atural (Base of Reasoning and Automation with Natural Intelligence).

BRAIN is a modular personal assistant designed to centralize information, automate tasks, and leverage local artificial intelligence to assist with daily life.

The ultimate goal is to turn it into the digital brain of your home and personal workflow, integrating AI, memory, automation, smart home control, health, energy, inventory, voice control, and other services into a single unified platform.

---

## Quick Installation on Windows

1. Download the project and extract it (for example, to `C:\BRAIN`).
2. Double-click on **`INSTALAR.bat`** and wait. It installs Python and Ollama if missing, downloads the AI model, and creates a **BRAIN** shortcut on your desktop.
3. Double-click the **BRAIN** shortcut (or `INICIAR.bat`). Your browser will open with the chat interface.

Step-by-step guide and troubleshooting: [`INSTRUCCIONES_WINDOWS.md`](INSTRUCCIONES_WINDOWS.md).

| File | Description |
| --- | --- |
| `INSTALAR.bat` | Installs everything required (first time only) |
| `INICIAR.bat` | Opens BRAIN with a local web interface in your browser |
| `INICIAR_CONSOLA.bat` | Opens BRAIN as a console chat in a terminal window |
| `DIAGNOSTICO.bat` | Checks system status, installations, and potential issues |
| `MEJORAR_IA.bat` | Analyzes your PC hardware and downloads the best fitting AI model |
| `CONFIGURAR_ENERGIA.bat` | Selects your inverter sensors for real-time solar production & consumption tracking |
| `CONFIGURAR_DOMOTICA.bat` | Connects BRAIN with Home Assistant to control your home ([guide](GUIA_DOMOTICA.md)) |

For Linux or macOS: `python3 main.py` (web), `python3 main.py --consola`, or `python3 main.py --diagnostico`. Requires Python 3.9 or higher and [Ollama](https://ollama.com/download) with a model (`ollama pull qwen3:4b`). No external Python `pip` packages required.


### Core

- ✅ Main `Brain` class
- ✅ Dynamic module loading system
- ✅ Centralized `DataManager` (atomic writes, resilient to corrupted files and Windows file locks)
- ✅ `GestorConocimiento` (personality and permanent memory)
- ✅ JSON-based data persistence
- ✅ Modular and scalable architecture (`ModuloBase`)
- ✅ Event and error logging in `datos/logs/`

### Modules

- ✅ Health (weight tracking and history)
- ✅ Inventory & Pantry management
- ✅ Energy (historical solar production and real-time inverter consumption/production)
- ✅ Calendar (events and tasks)
- ✅ Shopping lists
- ✅ Memory
- ✅ Sensors
- ✅ Smart Home / Domotics (lights, plugs, blinds, climate, and scenes via Home Assistant)

### Tool Calling System

Tools are functions that the AI can invoke to query and modify data. They use a simple decorator and are auto-discovered: just drop a new file into `brain/tools/builtin/`.

- **Health:** `guardar_peso`, `obtener_peso`, `peso_en_fecha`, `historial_peso`
- **Inventory:** `anadir_inventario`, `anadir_varios_inventario`, `quitar_inventario`, `se_ha_acabado`, `ver_inventario`, `buscar_inventario`, `borrar_del_inventario`, `vaciar_inventario`
- **Shopping:** `anadir_a_compra`, `anadir_varias_a_compra`, `ver_lista_compra`, `marcar_comprado`, `quitar_de_compra`, `vaciar_lista_compra`
- **Calendar:** `anadir_evento`, `anadir_tarea`, `completar_tarea`, `ver_agenda`
- **Energy:** `guardar_produccion_solar`, `ver_produccion_solar`, `ver_energia_ahora`
- **Recipes:** `ingredientes_disponibles` (pantry + house basics), `ver_basicos`, `anadir_basico`, `quitar_basico`
- **Memory:** `recordar`, `consultar_memoria`, `olvidar`
- **Sensors:** `guardar_sensor`, `ver_sensor`
- **Smart Home:** `encender`, `apagar`, `regular_luz`, `mover_persiana`, `poner_temperatura`, `activar_escena`, `ver_dispositivos`, `estado_dispositivo`

### Artificial Intelligence

- ✅ Native Ollama integration (custom client, zero external dependencies)
- ✅ Hardware detection (RAM, NVIDIA GPU, disk) to pick the best model: Qwen 3.8 27B, Gemma 4 (26B / 12B / E4B / E2B), or Qwen 3 4B
- ✅ `BrainAI` as an abstract AI layer
- ✅ Native Ollama tool-calling, with fallback mechanisms for models lacking native tool support
- ✅ Multi-tool chaining within a single turn
- ✅ Context-aware AI (personality, current date/time, and permanent memory)

### Conversation & Interfaces

- ✅ Persistent conversation history (remembers across restarts)
- ✅ Historical queries ("how much did I weigh on August 5th?")
- ✅ Local web interface (light/dark theme, mobile friendly): live energy stats, switchable smart devices, pantry management, shopping lists, bulk list importer, local microphone dictation, and text-to-speech output
- ✅ Console chat mode

### Tests

- ✅ 177 automated tests (run locally without needing Ollama or touching your personal data)
- ✅ `scripts/probar_ia.py` utility for real Ollama connection testing

```text
python -m unittest discover -s tests -t .