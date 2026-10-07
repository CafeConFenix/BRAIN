# Changelog

## v0.3.0

### Arquitectura

- Creación de la clase principal `Brain`.
- Integración del sistema de conocimiento dentro del núcleo.
- Establecimiento del punto de entrada principal del proyecto (`main.py`).

### Gestión del conocimiento

- Creación de la clase `Conocimiento`.
- Implementación del método `guardar()`.
- Implementación del método `leer()`.
- Implementación del método `existe()`.
- Implementación del método `eliminar()`.
- Implementación del almacenamiento persistente mediante archivos JSON.
- Primera prueba funcional de escritura y lectura de datos.

### Python

- Instalación y configuración del entorno virtual (`.venv`).
- Instalación y configuración de `pip`.
- Instalación de `Black`.
- Formateo automático del código.
- Validación del funcionamiento del entorno Python.

### Proyecto

- Definición de la estructura base del código Python.
- Creación del paquete `brain`.
- Creación de los módulos iniciales (`core.py`, `conocimiento.py`, `salud.py`, `inventario.py` y `herramientas.py`).
- Primer núcleo funcional de BRAIN.

## v0.2.0

### Arquitectura

- Definición de la filosofía del proyecto.
- Definición de BRAIN como un sistema modular.
- Separación conceptual entre IA, automatización y almacenamiento de conocimiento.
- Diseño inicial de la arquitectura basada en eventos.

### Conocimiento

- Creación del documento `datos/conocimiento/personalidad.md`.
- Definición de la identidad de BRAIN.
- Definición de la misión del sistema.
- Definición de la forma de comunicación.
- Definición de prioridades y principios de funcionamiento.

### Organización

- Creación de la estructura de almacenamiento de datos.
- Organización de los módulos por áreas:
  - Salud
  - Energía
  - Domótica
  - Inventario
  - Compras
  - Calendario
  - Sensores
  - Memoria
  - Logs
- Creación de los archivos JSON iniciales para cada módulo.

### Documentación

- Ampliación del README.
- Definición de la arquitectura general del proyecto.
- Actualización del ROADMAP.
- Documentación de la estructura del sistema.

---

## v0.1.0

### Sistema

- Instalación de Ubuntu 26.04 LTS.
- Actualización completa del sistema.
- Instalación de Git.
- Configuración inicial de Git (usuario y correo).

### Proyecto

- Creación del proyecto BRAIN.
- Definición del acrónimo:
  - **B**ase de **R**azonamiento y **A**utomatización con **I**nteligencia **N**atural.
- Creación de la estructura inicial del proyecto.
- Creación del README.
- Creación del ROADMAP.
- Creación del CHANGELOG.
- Inicialización del repositorio Git.
- Primer commit del proyecto.

### Contenedores

- Instalación de Docker Engine.
- Instalación de Docker Compose.
- Verificación del funcionamiento de Docker mediante `hello-world`.

### Inteligencia Artificial

- Despliegue de Ollama mediante Docker.
- Despliegue de Open WebUI mediante Docker.
- Configuración de la comunicación entre ambos servicios.
- Descarga del modelo Qwen3:8B.
- Descarga del modelo Qwen3:4B.

### GPU

- Instalación de NVIDIA Container Toolkit.
- Configuración de Docker para utilizar la GPU.
- Verificación del funcionamiento de CUDA.
- Configuración de Ollama para utilizar CPU y GPU de forma conjunta.
- Validación del uso de la GPU con modelos locales.

### Pruebas

- Primeras pruebas de rendimiento con modelos locales.
- Comparativa de tiempos entre CPU y GPU.
- Análisis del reparto de carga CPU/GPU.
- Validación del entorno de desarrollo para continuar con BRAIN.
