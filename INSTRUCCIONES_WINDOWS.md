# BRAIN en Windows: guía paso a paso

No hace falta saber programar. Necesitas Windows 10 u 11, conexión a internet (solo para instalar) y unos 6 GB libres en el disco.

## 1. Instalar (solo una vez)

1. Descomprime la carpeta de BRAIN donde quieras (por ejemplo `C:\BRAIN`). **No la uses desde dentro del ZIP**: primero hay que extraerla.
2. Haz doble clic en **`INSTALAR.bat`**.
   * Si Windows muestra *"Windows protegió su PC"*: pulsa **Más información** y después **Ejecutar de todas formas**. Es normal con archivos descargados.
   * Si pide permiso para instalar programas, acepta.
3. Espera. La primera vez tarda **entre 5 y 20 minutos** porque descarga Python, Ollama y el modelo de IA (unos 2,5 GB). No cierres la ventana.
4. Al terminar verás un mensaje verde y se habrá creado un icono **BRAIN** en el escritorio.

El instalador mide tu PC (memoria, tarjeta gráfica NVIDIA y espacio en disco) y descarga el mejor modelo de IA que le cabe, de 2,5 a 18 GB según el equipo. Si algún día cambias de PC o de tarjeta gráfica, haz doble clic en **`MEJORAR_IA.bat`** y BRAIN elegirá de nuevo.

## 2. Usar BRAIN

<<<<<<< HEAD
Haz doble clic en el icono **BRAIN** del escritorio (o del menú Inicio).

* BRAIN se abre en **su propia ventana**, sin pestañas y sin depender de Brave u otro navegador (usa Microsoft Edge, que ya viene con Windows, o Chrome si lo prefieres).
* Junto al reloj de Windows aparece el **icono de BRAIN** (si no lo ves, pulsa la flechita ^ de la barra de tareas). Si cierras la ventana, BRAIN **sigue funcionando** y los avisos siguen sonando. Haz clic en el icono para volver a abrirla.
* Clic derecho en el icono: *Abrir BRAIN*, *Silenciar / activar avisos*, *Arrancar con Windows (sí / no)* y *Salir de BRAIN* (esta opción sí lo cierra del todo).
* Para cerrarlo del todo hay tres formas: clic derecho en el icono → *Salir de BRAIN*; el engranaje de Ajustes → *Cerrar BRAIN del todo*; o doble clic en `CERRAR_BRAIN.bat`.
* Si abres BRAIN dos veces no pasa nada: solo se enseña la ventana que ya estaba abierta.
* Si prefieres el navegador de siempre, usa `INICIAR_NAVEGADOR.bat` (en <http://127.0.0.1:8765>).

### Sonidos de los avisos

Pulsa el engranaje de arriba a la derecha → **Sonidos de los avisos** → *Añadir un sonido* y elige un archivo `.wav`, `.mp3` u `.ogg` (máximo 3 MB). Después elige qué sonido suena para cada tipo de aviso (alertas, recordatorios, resumen del día…). Al elegirlo lo oirás una vez de prueba.
=======
Haz doble clic en el icono **BRAIN** del escritorio (o en `INICIAR.bat`).

* Se abre una ventana negra: **déjala abierta** mientras uses BRAIN. Es el motor.
* Se abre el navegador con el chat. Si no se abre solo, entra en <http://127.0.0.1:8765>.
* Para cerrar BRAIN, cierra la ventana negra.
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80

La primera respuesta tarda más (el modelo se carga en memoria). Las siguientes son más rápidas. Sin tarjeta gráfica, cada respuesta puede tardar de 10 a 60 segundos: es normal.

### Qué puedes decirle

Escribe como hablarías con una persona:

* «Hoy peso 88,4»
* «¿Cuánto pesaba el 5 de agosto?» · «¿Cómo ha evolucionado mi peso?»
* «Apunta leche y pan en la lista de la compra» · «¿Qué hay en la compra?» · «Ya he comprado la leche»
* «Tengo dentista el viernes a las 18:30» · «Apúntame que tengo que pagar la luz» · «¿Qué tengo esta semana?»
* «Las placas han producido 32,5 kWh hoy» · «¿Cuánto han producido esta semana?» · «¿Cuánto estoy consumiendo ahora?»
* «He metido 6 huevos en la nevera» · «¿Cuántos huevos quedan?» · «Se ha acabado el aceite» (lo apunta en la compra solo)
<<<<<<< HEAD
=======
<<<<<<< HEAD
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
* Pega una lista entera de productos («Leche: 6 unidades», «Arroz, 2», «2 x huevos»...) y BRAIN la guarda **en la despensa** de una vez. También puedes usar el botón **Importar lista** del panel, que te enseña lo que ha entendido antes de guardar. Para la compra, empieza el mensaje con «lista de la compra».
* «¿Qué puedo cocinar hoy?» · «Dame una receta con lo que tengo» (usa la despensa y los básicos de casa: aceite, sal, agua, harina, azúcar y especias)
* «Borra la lista de la compra» · «Quita el pan de la compra» · «Ya no tengo comino» (lo quita de los básicos)
* «Enciende la luz del salón» · «Baja la persiana del dormitorio» · «Pon el termostato a 22» (necesita [`GUIA_DOMOTICA.md`](GUIA_DOMOTICA.md))
* «Recuerda que mi hermana se llama Ana» · «¿Qué sabes de mí?» · «Olvida lo de mi hermana»

### El micrófono

Pulsa 🎤 y habla; BRAIN envía lo que dices cuando haces una pausa.

* **Chrome y Edge**: funciona sin instalar nada.
* **Brave** (y otros navegadores): la primera vez te ofrece **Instalar voz** (una sola vez, unos 500 MB). Después reconoce tu voz en tu propio PC, sin enviar nada a internet. Tarda unos segundos en transcribir.
* Si el navegador pregunta por el permiso del micrófono, acéptalo. Si lo bloqueaste antes, pulsa el candado de la barra de direcciones y permítelo.

La casilla «Leer las respuestas en voz alta» hace que BRAIN hable.
<<<<<<< HEAD
=======
=======
* Pega una lista entera de productos («Leche, 6 unidades», «Arroz, 2»...) y BRAIN la guarda de una vez.
* «Enciende la luz del salón» · «Baja la persiana del dormitorio» · «Pon el termostato a 22» (necesita [`GUIA_DOMOTICA.md`](GUIA_DOMOTICA.md))
* «Recuerda que mi hermana se llama Ana» · «¿Qué sabes de mí?» · «Olvida lo de mi hermana»

El micrófono 🎤 (solo en Chrome y Edge) sirve para dictar, y la casilla «Leer las respuestas en voz alta» hace que BRAIN hable.
>>>>>>> 2a7957f389dbe664434828a988e1d6677bc447b6
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80

Si prefieres la ventana negra sin navegador, usa **`INICIAR_CONSOLA.bat`**.

## 3. Dónde se guardan tus datos

En la carpeta `datos` dentro de BRAIN, como archivos de texto. Para hacer una **copia de seguridad**, copia esa carpeta. Para pasar BRAIN a otro PC, copia toda la carpeta de BRAIN.

## 4. Si algo falla

Haz doble clic en **`DIAGNOSTICO.bat`**: te dice qué está instalado y qué no.

| Síntoma | Solución |
| --- | --- |
| «No encuentro Python» | Ejecuta `INSTALAR.bat`. Si lo acabas de instalar, cierra todo y vuelve a intentarlo. |
| «No encuentro Ollama» / «Ollama apagado» | Ejecuta `INSTALAR.bat`, o abre **Ollama** desde el menú Inicio y espera unos segundos. |
| «IA no disponible» al abrir | Espera: la primera vez Ollama tarda hasta un minuto en arrancar. BRAIN lo reintenta solo; también puedes pulsar **Reintentar**. |
| «Ollama funciona pero no tiene ningún modelo» | Pulsa el botón **Descargar IA** que aparece en el aviso (o ejecuta `MEJORAR_IA.bat`). Si vuelve a pasar, ejecuta `DIAGNOSTICO.bat`: dice qué ve `ollama list` y qué programa usa el puerto de Ollama. |
| Las respuestas tardan muchísimo | Tu PC es justo para ese modelo. Abre una consola (`cmd`) y escribe `ollama pull qwen3:4b`; BRAIN usará el que tenga instalado. |
| El navegador muestra «Sin conexión con BRAIN» | La ventana negra se ha cerrado. Vuelve a abrir BRAIN. |
| El antivirus bloquea algo | Los `.bat` son texto plano y puedes abrirlos con el Bloc de notas para comprobarlos. Añade la carpeta de BRAIN a las excepciones si hace falta. |
| El puerto 8765 está ocupado | BRAIN prueba solo con los siguientes puertos; mira la dirección que muestra la ventana negra. |

Si nada de esto funciona, copia el texto de la ventana negra (o el de `DIAGNOSTICO.bat`) y pide ayuda con él.

## 5. Controlar las luces y la casa

Mira la guía [`GUIA_DOMOTICA.md`](GUIA_DOMOTICA.md): necesitas Home Assistant y ejecutar `CONFIGURAR_DOMOTICA.bat` una vez.

## 6. Cambiar de modelo (opcional)

Lo normal es usar `MEJORAR_IA.bat`. Si prefieres otro, abre `cmd` y escribe `ollama pull nombre-del-modelo`. BRAIN usa automáticamente el mejor que encuentre instalado. Para forzar uno: `setx BRAIN_MODELO qwen3:8b` y vuelve a abrir BRAIN.

<<<<<<< HEAD
## 7. Instalador `instalbrain (versión).exe` y desinstalar

Si quieres un instalador con asistente (pantallas de «Siguiente», sin ventana negra), haz doble clic en **`CREAR_SETUP.bat`**. Tarda un par de minutos (necesita internet solo en ese PC) y deja un archivo **`instalbrain (1.0.6).exe`** en la misma carpeta. Cópialo a cualquier PC con Windows y haz doble clic: **lleva Python dentro**, así que no hay que instalar nada más. El asistente te deja elegir si quieres el icono del escritorio, que BRAIN se abra al encender el ordenador y si instala Ollama (la IA). BRAIN se instala en `%LOCALAPPDATA%\BRAIN`. Si lo ejecutas sobre una versión anterior, la actualiza **sin borrar tus datos**.

La primera vez que abras BRAIN te ofrece, con un botón, descargar el modelo de IA que mejor encaja con tu ordenador (es lo único que tarda). Un detalle: con el Python incluido no se puede instalar el reconocimiento de voz (necesita `pip`); si quieres voz, usa `INSTALAR.bat`.

Para desinstalar: *Configuración → Aplicaciones → BRAIN → Desinstalar*. Te pregunta si quieres borrar también tus datos (despensa, compra, conversaciones, copias). Python y Ollama no se tocan; quítalos desde Aplicaciones si ya no los quieres. (Si instalaste con `INSTALAR.bat`, basta con borrar la carpeta de BRAIN y los iconos.)

## 8. Desde el móvil u otro ordenador

Mira [`ACCESO_DESDE_EL_MOVIL.md`](ACCESO_DESDE_EL_MOVIL.md).
=======
## 7. Desinstalar

Borra la carpeta de BRAIN y el icono del escritorio. Python y Ollama se desinstalan desde *Configuración → Aplicaciones* si ya no los quieres.
>>>>>>> 84cb45a321c908149c3d3b8d4d77c1e0d48efb80
