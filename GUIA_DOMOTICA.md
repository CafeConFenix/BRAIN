# Controlar la casa con BRAIN (luces, persianas, enchufes, calefacción...)

BRAIN no habla directamente con cada bombilla o enchufe: habla con **Home Assistant**, un programa gratuito que hace de "central" de la casa y que se entiende con casi todas las marcas (Philips Hue, IKEA Trådfri, Tuya / Smart Life, Shelly, Xiaomi, Sonoff, Zigbee, Z-Wave, Google Home, Alexa, Tado, Netatmo...).

Una vez que tus aparatos aparecen en Home Assistant, BRAIN los controla solo. Tú le dices:

* «Enciende la luz del salón» · «Apaga todas las luces»
* «Pon la luz de la cocina al 30 % y en blanco cálido» · «Ponla de color azul»
* «Baja la persiana del dormitorio» · «Pon la persiana al 40 %»
* «Pon el termostato del salón a 22 grados»
* «Activa la escena noche»
* «¿Qué luces hay encendidas?» · «¿Qué temperatura hay en el salón?»

Si hay dos aparatos que encajan («la luz» y tienes varias), BRAIN te pregunta cuál en lugar de adivinar.

## Ver el inversor solar y el consumo en tiempo real

Si tu inversor (Huawei, Fronius, SolarEdge, Growatt, Solax, GoodWe, Victron, SMA...) o tu contador (por ejemplo un Shelly EM) ya aparecen en Home Assistant, BRAIN los lee en directo:

* En la web, el panel **Energía ahora** muestra cada 5 segundos la producción de las placas, el consumo de la casa, si estás comprando o vendiendo a la red y la batería.
* Puedes preguntar: «¿Cuánto estoy consumiendo?» · «¿Cuánto producen las placas ahora?».

BRAIN busca los sensores él solo. Para elegirlos a mano o corregirlos, haz doble clic en **`CONFIGURAR_ENERGIA.bat`**. Si tu instalación no tiene sensor de consumo, BRAIN lo calcula (producción + lo que compras a la red).

Si tu inversor todavía no aparece en Home Assistant, añádelo en *Ajustes → Dispositivos y servicios* (casi todas las marcas tienen integración oficial).

## Seguridad

BRAIN **nunca** abre cerraduras, puertas, garajes ni portones, ni toca alarmas. Solo puede *leer* su estado («¿está cerrada la puerta?»). Es una decisión de diseño: una conversación no debe poder abrir tu casa.

## Paso 1: tener Home Assistant

**Si ya lo tienes** (en una Raspberry Pi, Home Assistant Green, un NAS...): pasa al paso 2.

**Si no lo tienes**, estas son las formas más sencillas, de más fácil a más trabajo:

1. **Home Assistant Green**: una cajita oficial que se enchufa al router. Es lo más fácil para no programadores.
2. **Raspberry Pi 4 o 5**: se instala con el programa oficial *Raspberry Pi Imager* eligiendo "Home Assistant OS".
3. **En este mismo PC con Windows**: se puede, pero con una máquina virtual y es más pesado. No lo recomiendo si el PC se apaga por las noches.

Guía oficial paso a paso: <https://www.home-assistant.io/installation/>

Después, en Home Assistant, añade tus aparatos desde *Ajustes → Dispositivos y servicios → Añadir integración*. **Asigna cada aparato a su habitación** (*Ajustes → Áreas*): así BRAIN entiende «la luz del salón» aunque el aparato se llame de otra forma.

## Paso 2: conectar BRAIN (una sola vez)

1. En Home Assistant: haz clic en tu nombre (abajo a la izquierda) → pestaña **Seguridad** → al final, **Tokens de acceso de larga duración** → **Crear token**. Llámalo `BRAIN`, **copia el texto largo** que aparece (solo se muestra una vez).
2. En BRAIN, haz doble clic en **`CONFIGURAR_DOMOTICA.bat`**.
3. Pulsa Enter si BRAIN encuentra solo Home Assistant, o escribe su dirección (por ejemplo `192.168.1.50:8123`). Pega el token (no se verá al pegarlo) y pulsa Enter.
4. Si todo va bien verás cuántas luces, persianas, etc. ha encontrado.

El token se guarda en `datos\domotica\home_assistant.json`, solo en tu PC. No lo compartas ni subas esa carpeta a internet.

## Si algo falla

| Síntoma | Solución |
| --- | --- |
| «No puedo conectar con Home Assistant» | Comprueba que está encendido y que este PC está en la misma red/wifi. Prueba a abrir su dirección en el navegador. |
| «Ha rechazado la llave de acceso» | Crea un token nuevo y vuelve a ejecutar `CONFIGURAR_DOMOTICA.bat`. |
| «No encuentro ningún aparato que encaje» | Revisa el nombre en Home Assistant. BRAIN te dirá qué aparatos ve. |
| BRAIN no entiende de qué habitación hablas | Asigna el aparato a un Área en Home Assistant. |
| Los aparatos nuevos no aparecen | BRAIN refresca la lista cada minuto; espera un poco o repite la orden. |
| La IA dice que lo ha hecho pero no pasa nada | Con modelos muy pequeños pasa a veces. Ejecuta `MEJORAR_IA.bat` para usar uno mejor. |

## Para quien sabe un poco más

* También se puede configurar con las variables de entorno `BRAIN_HA_URL` y `BRAIN_HA_TOKEN`.
* Tipos de aparato controlables: luces, enchufes e interruptores, ventiladores, persianas/cortinas (no garajes), climatización, escenas, scripts, reproductores, humidificadores, aspiradoras.
* Solo lectura: sensores, sensores binarios, cerraduras, alarmas, meteorología, personas.
