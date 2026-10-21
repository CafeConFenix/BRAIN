# Usar BRAIN desde el móvil u otro ordenador

BRAIN vive en tu ordenador de casa. Para entrar desde el móvil (en el sofá o haciendo la compra) o desde otro PC usamos **Tailscale**: una red privada y gratuita (para uso personal) que une tus dispositivos como si estuvieran en la misma casa.

* No se abre ningún puerto del router: nadie desde internet puede ver BRAIN.
* La conexión va cifrada (HTTPS).
* Además BRAIN te pide una **contraseña** que eliges tú.
* El ordenador de casa tiene que estar **encendido** y con BRAIN abierto (si arranca con Windows, basta con encender el PC).

## Pasos (solo una vez)

1. **Instala Tailscale** en el ordenador de casa y en el móvil: <https://tailscale.com/download>. Entra en los dos con la **misma cuenta**.
2. En el panel de Tailscale (<https://login.tailscale.com/admin/dns>) activa **HTTPS Certificates**. Es un interruptor; solo hace falta la primera vez.
3. En el ordenador de casa, haz doble clic en **`CONFIGURAR_ACCESO.bat`**:
   * Escribe una contraseña de **8 caracteres o más** (no se ve mientras la escribes).
   * BRAIN publica su dirección privada y te la muestra, por ejemplo `https://mi-pc.tail1234.ts.net`.
   * (También puedes poner o cambiar la contraseña en BRAIN → engranaje → *Acceso desde el móvil u otro PC*, pero ese botón no activa Tailscale: para eso usa el `.bat`.)
4. En el **móvil**, con Tailscale activado, abre esa dirección en el navegador y entra con la contraseña.
5. **Como una app:** en Chrome (Android) *menú → Instalar aplicación*; en Safari (iPhone) *Compartir → Añadir a pantalla de inicio*. Tendrá el logo de BRAIN y se abrirá a pantalla completa.

El micrófono funciona desde el móvil porque la conexión es HTTPS. (La voz se transcribe en tu PC de casa, no en el móvil.)

## ¿Qué es `pythonw.exe` en el Administrador de tareas?

Es BRAIN funcionando (sin ventana negra). Es normal y es lo que permite que los avisos suenen con la ventana cerrada. Para cerrarlo del todo: clic derecho en el icono de BRAIN junto al reloj → *Salir de BRAIN*, o el engranaje de Ajustes → *Cerrar BRAIN del todo*, o `CERRAR_BRAIN.bat`.

## Seguridad

* Desde el propio ordenador de casa no se pide contraseña; desde cualquier otro sitio, sí.
* Las sesiones duran 30 días en ese dispositivo. Si cambias la contraseña, **todas las sesiones se cierran**.
* Tras 5 contraseñas incorrectas seguidas hay un bloqueo de 60 segundos.
* La contraseña solo se puede cambiar desde el ordenador de casa.
* Si pierdes el móvil: cambia la contraseña en BRAIN (cierra la sesión del móvil) y quita el móvil de tu cuenta de Tailscale.
* BRAIN nunca controla cerraduras, garajes ni alarmas, tampoco desde fuera.

## Si algo falla

| Síntoma | Qué hacer |
| --- | --- |
| `CONFIGURAR_ACCESO.bat` dice que falta Tailscale | Instálalo (paso 1) y repite |
| Dice que no has iniciado sesión | Abre Tailscale en el PC, entra con tu cuenta y repite |
| No he podido publicar BRAIN | Activa *HTTPS Certificates* (paso 2) y repite |
| "Esta página no funciona" / error 502 | Abre BRAIN en el PC (icono del escritorio), espera 10 segundos y ejecuta de nuevo `CONFIGURAR_ACCESO.bat`: ahora comprueba que BRAIN responde y te muestra lo que Tailscale tiene publicado. Usa siempre la dirección `https://...ts.net` que te da, **no** la IP 100.x.x.x ni `http://` |
| El móvil no carga la dirección | Comprueba que Tailscale está **activado** en el móvil y que el PC de casa está encendido |
| "Acceso desde fuera no activado" | Falta la contraseña: ponla en el paso 3 |
| Cambié de PC o de nombre | Vuelve a ejecutar `CONFIGURAR_ACCESO.bat` |

Para dejar de publicar BRAIN: abre una ventana de comandos y escribe `tailscale serve reset`.
