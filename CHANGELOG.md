# Changelog

Todos los cambios relevantes de BRAIN se documentan en este archivo.

---

## [1.0.6] - 2026-10-19

### Añadido

* **Presupuesto mensual con avisos.** Fija un total al mes (y límites por categoría) y BRAIN avisa una sola vez al llegar al 80 % y al 100 %. Barra de progreso en «Gastos del mes». Herramientas `fijar_presupuesto` y `ver_presupuesto`.
* **Caducidades de la despensa.** Cada producto puede llevar fecha de caducidad (pulsa «＋ caducidad» en la despensa o díselo a BRAIN). Aviso diario de lo que caduca en 3 días, franja amarilla en el panel y herramientas `ver_caducidades` y `poner_caducidad` para pedir recetas que lo aprovechen.
* **Menú semanal.** BRAIN guarda platos con ingredientes por día y apunta en la lista de la compra *solo lo que falta*. Panel «Menú de la semana» con botón «Comprar lo que falta». Herramientas `guardar_menu_semanal`, `ver_menu_semanal`, `comprar_lo_del_menu`.
* **Panel de hábitos con recordatorios.** Barra de progreso, racha, botón +1 y una hora opcional: si a esa hora aún no está cumplido, BRAIN avisa.
* **Tareas del hogar con turnos.** «Sacar la basura: Ana, Luis, Marta, cada 3 días». Al marcarla como hecha el turno pasa a la siguiente persona; también «Pasar» el turno. Aviso el día que toca a quien le corresponde.
* **Botones «Salgo de casa» y «Buenas noches».** Primero muestran lo que está encendido y lo pendiente (tareas de hoy o agenda de mañana); solo se apaga lo que marques y confirmes.
* **Coste de la luz en euros** (tarifa, horas baratas, ahorro de las placas y comparación con el mes pasado) con panel propio y botón «Tarifa».
* **Búsqueda global** (lupa de arriba o Ctrl+K): despensa, compra, agenda, gastos, tareas, aparatos, recuerdos y manuales a la vez.
* **Subir manuales y PDF desde la interfaz.** Los PDF con texto se convierten para poder buscar dentro (sin instalar nada). Los escaneados se rechazan con un mensaje claro.
* **Varias personas.** Hábitos y tareas del hogar pueden ser de una persona o de todos; selector en el panel de hábitos.
* **Copia de seguridad en un segundo sitio** (USB, OneDrive, otra carpeta): cada copia diaria se duplica allí y se puede recuperar con un clic (se valida antes de traerla).
* **Instalador gráfico `instalbrain (versión).exe`** (Inno Setup, en español): asistente con casillas para el icono del escritorio, arranque con Windows e instalación de Ollama; **lleva Python incluido** (no descarga nada de Python), no abre ninguna ventana negra, actualiza sin tocar tus datos y se desinstala desde *Aplicaciones* (pregunta si borrar los datos). Se crea con `CREAR_SETUP.bat`.

### Cambiado

* **Nuevo logo y tema morado** en toda la interfaz (claro y oscuro), la página de acceso, el manifiesto de la web y los iconos de Windows.
* **Pedir una receta da la receta.** Antes la IA a veces contestaba «voy a revisar la despensa» y se quedaba ahí. Ahora BRAIN consulta la despensa por su cuenta antes de responder y, si el modelo solo anuncia lo que va a hacer, se le obliga a hacerlo. Vale para cualquier otra petición.
* El nombre «Luis» ya no está escrito en la personalidad de BRAIN.

### Verificado

393 tests (antes 353) y una prueba de punta a punta en un navegador real: todos los paneles nuevos, los diálogos, la búsqueda, rutinas, hábitos, hogar y menú, sin errores de JavaScript.

El instalador `.exe` se escribió según la documentación de Inno Setup, pero no se pudo compilar ni ejecutar en un Windows real al preparar esta versión.

---

## [1.0.5] - 2026-10-15

### Añadido

* **Elegir qué dispositivos de domótica quieres ver.** Botón «Elegir dispositivos» en el panel (y en *Ajustes*): lista por habitación con casillas, buscador y «Todos / Ninguno». Los desmarcados desaparecen del panel y la IA no los controla ni los menciona; los dispositivos nuevos que añadas a Home Assistant aparecen solos.
* **Asistente de primer uso** (Home Assistant y energía), en la propia web: busca Home Assistant en la red, prueba el token y explica cómo conseguirlo; propone los sensores de energía que mejor encajan (producción, consumo, red, batería) y averigua el signo del contador preguntando si ahora compras o vendes; y deja elegir los dispositivos. Aparece solo la primera vez, se puede saltar y se reabre desde *Ajustes*. La llave de Home Assistant nunca se devuelve a la web y solo se configura desde el propio PC.
* **Gastos del hogar**: apunta gastos hablando («he gastado 23 € en el súper»), con categoría deducida del concepto, resumen mensual por categoría y panel «Gastos del mes». Herramientas `anadir_gasto`, `ver_gastos`, `borrar_gasto`.
* **Hábitos diarios con racha**: «bebe 8 vasos de agua», «me he tomado la pastilla». Objetivo por día, progreso y días seguidos (la racha de ayer no se rompe hasta que acabe hoy). Herramientas `crear_habito`, `anotar_habito`, `ver_habitos`, `borrar_habito`.

### Cambiado

* **Avisos vistos al abrirlos**: si el panel de avisos se queda abierto más de 2 segundos, lo que se ve cuenta como visto (si se cierra antes, no; si la pestaña no está visible, tampoco).

### Verificado

Probado de punta a punta en un navegador real (Chromium) contra un Home Assistant simulado: asistente completo (token malo y bueno), ocultar y volver a mostrar un dispositivo, que el asistente no reaparezca, y la regla de los 2 segundos. Tests: 318 -> 353.

---

## [1.0.4] - 2026-10-14

### Corregido

* **Cerrar la ventana no cerraba BRAIN.** BRAIN seguía vivo con el icono junto al reloj. Ahora, al cerrar la ventana, BRAIN se cierra del todo (programa, icono y ventana). Quien prefiera el comportamiento anterior (seguir en segundo plano para que suenen los avisos) puede activarlo en *Ajustes* o en el menú del icono: "Seguir en segundo plano al cerrar la ventana".
* **El icono junto al reloj se quedaba "fantasma".** Al salir se mataba el proceso del icono a la fuerza y Windows no lo retiraba hasta pasar el ratón por encima. Ahora BRAIN le pide que se oculte y se libere él mismo (y si BRAIN desaparece de golpe, el icono se quita solo en 1 s en vez de 3).
* **"Salir de BRAIN" dejaba la ventana abierta**, mostrando una página muerta. Ahora se cierra la ventana (y todos los procesos de Edge/Chrome que hubiera lanzado).
* **Pantalla negra de consola.** `INICIAR.bat` mantenía una ventana de consola abierta todo el rato. Ahora `main.py --escritorio` se relanza solo con `pythonw.exe` (sin consola) y esa ventana se cierra enseguida. Además, todos los programas auxiliares que BRAIN lanza (nvidia-smi, tailscale, netstat, ollama, pip) se ejecutan sin ventana: sin consola, Windows abría una ventana negra por cada uno.
* Sin consola no había dónde leer los errores de arranque: ahora se anotan en `datos/logs/errores.log` y se muestra un cuadro de Windows.
* El icono junto al reloj se lanza con el script codificado (`-EncodedCommand`), sin depender de comillas ni acentos.
* Pulsar el icono con la ventana ya abierta (o minimizada) ahora la trae al frente.
* `CERRAR_BRAIN.bat` ahora pide a BRAIN que salga él mismo (`main.py --cerrar`) y solo lo mata si no responde; ya no mata cualquier `python main.py` del equipo.

* **Instalador: fallo al instalar Python (código 1603).** Causa hallada en el registro de winget: fallaba el paquete de *tests* de Python (`test_JustForMe`), no necesario para BRAIN. Ahora se instala Python reducido (`Include_test=0 Include_doc=0 Include_tcltk=0 Include_dev=0`) antes de probar winget. Ahora busca Python también en el registro de Windows y en cualquier carpeta `Python3*` (aunque no esté en el PATH), instala con winget solo para el usuario, guarda el registro de la instalación y, si falla, explica qué hacer (reiniciar, desinstalar Python anterior, instalarlo a mano). Y si Windows Installer falla (1603), el instalador usa una **copia portable de Python** (zip de python.org, carpeta `python` dentro de BRAIN) que no necesita instalador; BRAIN solo usa la biblioteca estándar. Todos los `.bat` (domótica, energía, acceso, diagnóstico, mejorar IA, iniciar, cerrar) buscan primero esa copia portable; antes decían «no encuentro Python». Limitación: sin `pip`, así que la instalación opcional de la voz (Whisper) no funcionará con esa copia.

### Añadido

* El menú del icono muestra casillas marcadas (avisos silenciados, segundo plano, arrancar con Windows) y *Ajustes* tiene los interruptores correspondientes.
* `main.py --cerrar`.
* Cerrar la sesión de Windows o Ctrl+C también cierran icono y ventana.

### Sin verificar en Windows real

Los cambios de icono, ventana y `pythonw` se programaron según el comportamiento documentado de Windows y se cubrieron con tests simulados (318 pasan), pero no se pudieron ejecutar en un Windows real.

---

## [1.0.3] - 2026-10-12

### Corregido

* `CONFIGURAR_ACCESO.bat` daba "BRAIN respondio con el codigo 403" sin explicar nada. Ahora la autoprueba muestra el código, la versión de BRAIN que contesta, el puerto y la respuesta, y avisa si lo que responde es una **copia antigua** de BRAIN que sigue abierta (que no entiende las direcciones de Tailscale y las rechaza con 403). BRAIN anuncia su versión en la cabecera `Server`, y el 403 indica el `Host` recibido.
* `CERRAR_BRAIN.bat` cierra también las copias antiguas (modo `--web`), no solo las del programa de escritorio.

---

## [1.0.2] - 2026-10-12

### Corregido

* **"Salir de BRAIN" del icono junto al reloj no cerraba BRAIN.** El icono avisaba a BRAIN por una tubería entre procesos y lanzaba un hilo con código de PowerShell que no puede ejecutarse fuera del hilo principal. Ahora el icono pide cada acción a BRAIN por su dirección local (`/api/escritorio/mostrar|silencio|autoarranque|salir`, solo desde el propio PC), BRAIN responde antes de cerrarse y el icono desaparece solo si BRAIN deja de existir. Verificado que el proceso termina y limpia su archivo de instancia.
* El icono usa fotogramas BMP (el formato más compatible con `System.Drawing.Icon`) en lugar de PNG.

### Añadido

* **Cerrar BRAIN del todo** de dos formas más, por si el icono no aparece: botón en *Ajustes* de la propia ventana y `CERRAR_BRAIN.bat`.

---

## [1.0.1] - 2026-10-12

### Corregido

* **Acceso desde el móvil: "Esta página no funciona".** (a) Un fallo inesperado dentro del servidor cortaba la conexión sin respuesta (el navegador lo muestra como "no ha enviado ningún dato"); ahora responde con un error 500 legible y lo anota en el registro. (b) La pantalla de contraseña se enviaba con código 401, que algunos navegadores sustituyen por su error genérico; ahora se envía con 200. (c) `tailscale serve` se publica ahora apuntando explícitamente a `http://127.0.0.1:<puerto>`, y si BRAIN tuvo que usar otro puerto distinto del 8765 se republica solo. (d) `CONFIGURAR_ACCESO.bat` ya no da el trabajo por bueno sin más: comprueba que BRAIN responde con el nombre privado de Tailscale y muestra lo que Tailscale tiene publicado.

---

## [1.0.0] - 2026-10-12

### Añadido

* **BRAIN como programa de escritorio** (`python main.py --escritorio`, o el icono BRAIN): ventana propia sin pestañas (Microsoft Edge o Chrome en modo aplicación, con perfil aparte e independiente de Brave), icono junto al reloj con menú (*Abrir*, *Silenciar avisos*, *Arrancar con Windows*, *Salir*), copia única (abrirlo dos veces solo enseña la ventana) y arranque con Windows en segundo plano (`--segundo-plano`), para que los avisos y recordatorios suenen aunque la ventana esté cerrada. Sin icono de bandeja, cerrar la ventana cierra BRAIN.
* **Logo e iconos** originales de BRAIN (dos hemisferios con red neuronal y una chispa ámbar): `brain.ico` para Windows, PNG 192/512 y de Apple para el móvil.
* **Instalador `Setup.exe`**: `CREAR_SETUP.bat` lo construye con IExpress (incluido en Windows). Instala en `%LOCALAPPDATA%\BRAIN`, conserva los datos al actualizar, prepara Python, Ollama y el modelo, crea los accesos directos con el logo y se desinstala desde *Aplicaciones* (pregunta si borrar también los datos). `INSTALAR.bat` también crea ahora los iconos del escritorio y del menú Inicio y activa el arranque con Windows.
* **Sonidos propios desde la interfaz**: engranaje de **Ajustes** → subir un `.wav`, `.mp3` u `.ogg` (máx. 3 MB; nombre saneado, solo esas extensiones), elegir sonido por tipo de aviso con prueba al instante y quitar sonidos subidos.
* **Acceso desde el móvil y otros PC** (Tailscale): `CONFIGURAR_ACCESO.bat` / `--configurar-acceso` pone la contraseña, detecta el nombre privado `*.ts.net` y publica BRAIN con `tailscale serve` (HTTPS, sin abrir puertos del router). Capa de seguridad nueva (`brain/web/acceso.py`): contraseña con PBKDF2-SHA256 (200.000 vueltas), sesión en cookie firmada con HMAC (`HttpOnly`, `SameSite=Strict`, `Secure` con HTTPS, 30 días, se invalida al cambiar la contraseña), bloqueo de 60 s tras 5 fallos, comprobación de `Host` y `Origin`, y sin contraseña configurada el acceso externo queda cerrado. Desde el propio PC no se pide contraseña; cambiar la contraseña o enseñar la ventana solo se puede desde el PC.
* **App instalable en el móvil** (PWA): manifiesto, iconos y *service worker*; pantalla de entrada propia.
* README en inglés rediseñado (capturas reales claro/oscuro/móvil, tabla de requisitos), `README.es.md` con el anterior, `LICENSE` (MIT) y `ACCESO_DESDE_EL_MOVIL.md`.

### Corregido

* **Micrófono: remuestreo con filtro paso bajo.** Al bajar el audio de 44,1/48 kHz a 16 kHz se usaba interpolación lineal (servidor) o medias de tramos (navegador), que no filtran: las frecuencias altas se plegaban sobre la voz (un tono de 15 kHz reaparecía con el 72 % de su fuerza). Ahora ambos usan un filtro sinc con ventana de Blackman antes de decimar (el mismo tono queda en 0,0000 y la voz en 1,000). Gracias al comentario recibido.

### Cambiado

* `INICIAR.bat` abre el programa de escritorio; el modo navegador pasa a `INICIAR_NAVEGADOR.bat`.
* El icono de la web pasa del favicon dibujado a mano al logo nuevo.
* Tests: 253 -> 297.

### Sin verificar en Windows real

La bandeja (PowerShell `NotifyIcon`), la ventana de Edge en modo aplicación, el `Setup.exe` (IExpress), el registro de autoarranque y Whisper con audio real se escribieron según el comportamiento documentado pero no se pudieron ejecutar en un Windows real al preparar esta versión.

---

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
