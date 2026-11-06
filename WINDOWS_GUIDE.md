# BRAIN on Windows: step-by-step guide

No programming knowledge needed. You need Windows 10 or 11, an internet connection (only to install) and about 6 GB of free disk space.

## 1. Install (only once)

1. Unzip the BRAIN folder wherever you like (for example `C:\BRAIN`). **Don't use it from inside the ZIP**: extract it first.
2. Double-click **`INSTALAR.bat`**.
   * If Windows shows *"Windows protected your PC"*: click **More info** and then **Run anyway**. This is normal with downloaded files.
   * If it asks for permission to install programs, accept.
3. Wait. The first time it takes **between 5 and 20 minutes** because it downloads Python, Ollama and the AI model (about 2.5 GB). Don't close the window.
4. When it finishes you'll see a green message and a **BRAIN** icon will have been created on the desktop.

The installer measures your PC (memory, NVIDIA graphics card and disk space) and downloads the best AI model that fits, from 2.5 to 18 GB depending on the machine. If you ever change your PC or graphics card, double-click **`MEJORAR_IA.bat`** and BRAIN will choose again.

## 2. Use BRAIN

Double-click the **BRAIN** icon on the desktop (or in the Start menu).

* BRAIN opens in **its own window**, tab-less and not depending on Brave or another browser (it uses Microsoft Edge, which already comes with Windows, or Chrome if you prefer).
* The **BRAIN icon** appears next to the Windows clock (if you don't see it, click the ^ arrow on the taskbar). If you close the window, BRAIN **keeps running** and notifications keep sounding. Click the icon to open it again.
* Right-click the icon: *Open BRAIN*, *Mute / unmute alerts*, *Start with Windows (yes / no)* and *Quit BRAIN* (this option does close it completely).
* There are three ways to close it completely: right-click the icon → *Quit BRAIN*; the gear icon in Settings → *Close BRAIN completely*; or double-click `CERRAR_BRAIN.bat`.
* Nothing happens if you open BRAIN twice: it just shows the window that was already open.
* If you prefer your regular browser, use `INICIAR_NAVEGADOR.bat` (at <http://127.0.0.1:8765>).

### Notification sounds

Press the gear icon at the top right → **Notification sounds** → *Add a sound* and pick a `.wav`, `.mp3` or `.ogg` file (3 MB max). Then pick which sound plays for each alert type (alerts, reminders, daily summary…). You'll hear a preview as you pick it.

The first reply takes longer (the model loads into memory). The next ones are faster. Without a graphics card, each reply can take 10 to 60 seconds: that's normal.

### What you can tell it

Write as you would talk to a person:

* "Today I weigh 88.4"
* "What did I weigh on August 5th?" · "How has my weight changed?"
* "Add milk and bread to the shopping list" · "What's on the shopping list?" · "I already bought the milk"
* "I have a dentist appointment Friday at 18:30" · "Note that I need to pay the electricity bill" · "What do I have this week?"
* "The panels produced 32.5 kWh today" · "How much did they produce this week?" · "How much am I using right now?"
* "I put 6 eggs in the fridge" · "How many eggs are left?" · "The oil ran out" (adds it to the shopping list only)
* Paste a whole list of products ("Milk: 6 units", "Rice, 2", "2 x eggs"...) and BRAIN saves it **to the pantry** in one go. You can also use the **Import list** button on the panel, which shows you what it understood before saving. For the shopping list, start the message with "shopping list".
* "What can I cook today?" · "Give me a recipe with what I have" (uses the pantry and household basics: oil, salt, water, flour, sugar and spices)
* "Clear the shopping list" · "Remove bread from the shopping list" · "I'm out of cumin" (removes it from the basics)
* "Turn on the living-room light" · "Lower the bedroom blind" · "Set the thermostat to 22" (needs [`SMART_HOME_GUIDE.md`](SMART_HOME_GUIDE.md))
* "Remember that my sister's name is Ana" · "What do you know about me?" · "Forget about my sister"

### The microphone

Press 🎤 and talk; BRAIN sends what you say when you pause.

* **Chrome and Edge**: works with nothing to install.
* **Brave** (and other browsers): the first time it offers **Install voice** (only once, about 500 MB). After that it recognizes your voice on your own PC, without sending anything to the internet. Transcribing takes a few seconds.
* If the browser asks for microphone permission, accept it. If you blocked it before, click the lock icon in the address bar and allow it.

The "Read replies out loud" checkbox makes BRAIN speak.

If you prefer the black window with no browser, use **`INICIAR_CONSOLA.bat`**.

## 3. Where your data is stored

In the `data` folder inside BRAIN, as text files. To make a **backup**, copy that folder. To move BRAIN to another PC, copy the whole BRAIN folder.

## 4. If something goes wrong

Double-click **`DIAGNOSTICO.bat`**: it tells you what's installed and what isn't.

| Symptom | Fix |
| --- | --- |
| "Can't find Python" | Run `INSTALAR.bat`. If you just installed it, close everything and try again. |
| "Can't find Ollama" / "Ollama is off" | Run `INSTALAR.bat`, or open **Ollama** from the Start menu and wait a few seconds. |
| "AI not available" when opening | Wait: the first time Ollama can take up to a minute to start. BRAIN retries on its own; you can also press **Retry**. |
| "Ollama works but has no model" | Press the **Download AI** button shown in the alert (or run `MEJORAR_IA.bat`). If it happens again, run `DIAGNOSTICO.bat`: it shows what `ollama list` sees and which program is using Ollama's port. |
| Replies take a very long time | Your PC is right at the edge for that model. Open a console (`cmd`) and type `ollama pull qwen3:4b`; BRAIN will use whichever one it has installed. |
| The browser shows "No connection with BRAIN" | The black window has closed. Open BRAIN again. |
| Antivirus blocks something | The `.bat` files are plain text and you can open them with Notepad to check them. Add the BRAIN folder to the exceptions if needed. |
| Port 8765 is busy | BRAIN automatically tries the next ports; check the address the black window shows. |

If none of this works, copy the text from the black window (or from `DIAGNOSTICO.bat`) and ask for help with it.

## 5. Controlling the lights and the home

See the guide [`SMART_HOME_GUIDE.md`](SMART_HOME_GUIDE.md): you need Home Assistant and to run `CONFIGURAR_DOMOTICA.bat` once.

## 6. Changing the model (optional)

The usual way is `MEJORAR_IA.bat`. If you prefer another one, open `cmd` and type `ollama pull model-name`. BRAIN automatically uses the best one it finds installed. To force one: `setx BRAIN_MODEL qwen3:8b` and open BRAIN again.

## 7. The `instalbrain (version).exe` installer and uninstalling

If you want a wizard-style installer ("Next" screens, no black window), double-click **`CREAR_SETUP.bat`**. It takes a couple of minutes (internet is only needed on that PC) and leaves an **`instalbrain (1.0.6).exe`** file in the same folder. Copy it to any Windows PC and double-click it: **it has Python built in**, so there's nothing else to install. The wizard lets you choose whether you want the desktop icon, whether BRAIN opens when the computer turns on, and whether it installs Ollama (the AI). BRAIN installs to `%LOCALAPPDATA%\BRAIN`. If you run it over an earlier version, it updates it **without deleting your data**.

The first time you open BRAIN it offers, with one button, to download the AI model that best fits your computer (that's the only part that takes a while). One detail: with the bundled Python, voice recognition cannot be installed (it needs `pip`); if you want voice, use `INSTALAR.bat`.

To uninstall: *Settings → Apps → BRAIN → Uninstall*. It asks whether you also want to delete your data (pantry, shopping, conversations, backups). Python and Ollama are left untouched; remove them from Apps if you no longer want them. (If you installed with `INSTALAR.bat`, just delete the BRAIN folder and the icons.)

## 8. From your phone or another computer

See [`REMOTE_ACCESS.md`](REMOTE_ACCESS.md).
