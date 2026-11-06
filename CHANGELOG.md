# Changelog

All relevant BRAIN changes are documented in this file.

---

## [2.0.0] - 2026-11-05

### Changed

* **Full English translation.** All code, comments, docstrings, identifiers, folders, scripts, CLI flags, environment variables, tool names and documentation are now in English. Old Spanish names (CLI flags like `--escritorio`, environment variables, tool names) are kept as deprecated aliases, and old Spanish data files migrate automatically on first load.
* **Bilingual interface.** The web UI now has a language switch (Settings → Idioma/Language) between Spanish and English, synced across devices through `/api/language`. The `--lang en|es` CLI flag sets it from the command line.
* `docs/es/` holds the Spanish translation of the documentation (`README.es.md`, `ROADMAP.md`, `CHANGELOG.md`, `REMOTE_ACCESS.md`, `SMART_HOME_GUIDE.md`, `WINDOWS_GUIDE.md`); the equivalent English docs live at the project root.
* `ACCESO_DESDE_EL_MOVIL.md` → `REMOTE_ACCESS.md`, `GUIA_DOMOTICA.md` → `SMART_HOME_GUIDE.md`, `INSTRUCCIONES_WINDOWS.md` → `WINDOWS_GUIDE.md`.
* `tests/language_scan.py`: a new test that scans the whole repository and fails if it finds Spanish text outside the allowed translation files.

### Fixed

* `scripts/create_icons.py` pointed `DESKTOP` at the no-longer-existing `brain/escritorio` folder instead of `brain/desktop`.
* `instalador/brain.iss` referenced `brain\escritorio\brain.ico` (desktop icon path) and excluded `datos\*` instead of the real `data\*` folder; both were silently broken.
* `scripts/instalar.ps1` had Unix line endings (LF) instead of the CRLF PowerShell on Windows expects.

### Verified

442 tests passing (up from 393) and a clean language scan across the whole repository outside test fixtures.

---

## [1.0.6] - 2026-10-19

### Added

* **Monthly budget with alerts.** Set a monthly total (and per-category limits) and BRAIN warns once when you hit 80% and 100%. Progress bar in "Expenses this month". Tools `set_budget` and `view_budget`.
* **Pantry expiry dates.** Any product can have an expiry date (tap "+ expiry" in the pantry or just tell BRAIN). Daily alert for what expires within 3 days, a yellow band on the panel, and tools `view_expirations` and `set_expiration` to ask for recipes that use it up.
* **Weekly menu.** BRAIN stores dishes with ingredients per day and adds to the shopping list *only what's missing*. "Menu of the week" panel with a "Buy what's missing" button. Tools `save_weekly_menu`, `view_weekly_menu`, `buy_from_menu`.
* **Habit panel with reminders.** Progress bar, streak, +1 button and an optional time: if it isn't done by then, BRAIN reminds you.
* **Household chores with turns.** "Take out the trash: Ana, Luis, Marta, every 3 days." Marking it done passes the turn to the next person; there is also a "Skip turn" option. Alert on the day it's someone's turn.
* **"Leaving home" and "Good night" buttons.** They first show what's on and what's pending (today's chores or tomorrow's agenda); only what you pick and confirm gets turned off.
* **Cost of electricity in euros** (tariff, cheap hours, savings from the solar panels and comparison with last month) with its own panel and "Tariff" button.
* **Global search** (magnifying glass at the top, or Ctrl+K): pantry, shopping, calendar, expenses, chores, devices, memories and manuals all at once.
* **Upload manuals and PDFs from the interface.** PDFs with text are converted so they can be searched (no installation needed). Scanned ones are rejected with a clear message.
* **Multiple people.** Habits and chores can belong to one person or to everyone; selector in the habits panel.
* **Backup to a second location** (USB, OneDrive, another folder): every daily backup is also copied there and can be restored with one click (it's validated before being restored).
* **Graphical installer `instalbrain (version).exe`** (Inno Setup, in Spanish): wizard with checkboxes for the desktop icon, starting with Windows and installing Ollama; **ships with Python included** (it doesn't download any Python), opens no black console window, updates without touching your data, and uninstalls from *Apps* (asks whether to delete the data). Built with `CREAR_SETUP.bat`.

### Changed

* **New logo and purple theme** across the whole interface (light and dark), the access page, the web manifest and the Windows icons.
* **Asking for a recipe now gives the recipe.** Before, the AI sometimes replied "I'm going to check the pantry" and stopped there. Now BRAIN checks the pantry itself before answering and, if the model only announces what it's about to do, it's forced to actually do it. This applies to any other request too.
* The name "Luis" is no longer written into BRAIN's personality.

### Verified

393 tests (up from 353) plus an end-to-end test in a real browser: all the new panels, dialogs, search, routines, habits, home and menu, with no JavaScript errors.

The `.exe` installer was written against the Inno Setup documentation, but could not be compiled or run on a real Windows machine while preparing this version.

---

## [1.0.5] - 2026-10-15

### Added

* **Choose which smart-home devices you want to see.** "Choose devices" button on the panel (and in *Settings*): a list by room with checkboxes, a search box and "All / None". Unchecked devices disappear from the panel and the AI neither controls nor mentions them; new devices you add to Home Assistant show up on their own.
* **First-use assistant** (Home Assistant and energy), inside the web app itself: finds Home Assistant on the network, tests the token and explains how to get one; suggests the energy sensors that fit best (production, consumption, grid, battery) and figures out the meter's sign by asking whether you currently buy or sell; and lets you pick the devices. It only appears the first time, can be skipped, and can be reopened from *Settings*. The Home Assistant key is never sent back to the web page and can only be configured from the PC itself.
* **Household expenses**: log expenses by talking ("I spent 23 € at the supermarket"), with a category inferred from the description, a monthly summary by category and an "Expenses this month" panel. Tools `add_expense`, `view_expenses`, `delete_expense`.
* **Daily habits with streaks**: "drink 8 glasses of water", "I took my pill". Daily goal, progress and days in a row (yesterday's streak doesn't break until today ends). Tools `create_habit`, `log_habit`, `view_habits`, `delete_habit`.

### Changed

* **Notices seen on opening**: if the notices panel stays open for more than 2 seconds, what's visible counts as seen (if it's closed before that, it doesn't; if the tab isn't visible, it doesn't either).

### Verified

Tested end to end in a real browser (Chromium) against a simulated Home Assistant: the full assistant (bad and good token), hiding and re-showing a device, making sure the assistant doesn't reappear, and the 2-second rule. Tests: 318 -> 353.

---

## [1.0.4] - 2026-10-14

### Fixed

* **Closing the window didn't close BRAIN.** BRAIN stayed alive with the icon next to the clock. Now, closing the window closes BRAIN entirely (program, icon and window). Anyone who prefers the old behavior (keep running in the background so alerts and reminders still sound) can turn it on in *Settings* or from the icon's menu: "Keep running in the background when the window closes".
* **The icon next to the clock became a "ghost".** On exit, the icon's process was killed forcibly and Windows wouldn't remove it until you moved the mouse over it. Now BRAIN asks it to hide and free itself (and if BRAIN disappears abruptly, the icon removes itself within 1 s instead of 3).
* **"Quit BRAIN" left the window open**, showing a dead page. Now the window is closed (along with any Edge/Chrome processes it had launched).
* **Black console screen.** `INICIAR.bat` kept a console window open the whole time. Now `main.py --desktop` relaunches itself with `pythonw.exe` (no console) and that window closes right away. Also, every helper program BRAIN launches (nvidia-smi, tailscale, netstat, ollama, pip) now runs with no window: without a console, Windows used to open a black window for each one.
* With no console there was nowhere to read startup errors: now they're logged to `data/logs/errors.log` and a Windows message box is shown.
* The icon next to the clock is launched with the script encoded (`-EncodedCommand`), with no dependency on quotes or accents.
* Clicking the icon while the window is already open (or minimized) now brings it to the front.
* `CERRAR_BRAIN.bat` now asks BRAIN to quit on its own (`main.py --close`) and only kills it if it doesn't respond; it no longer kills any `python main.py` on the machine.

* **Installer: failure installing Python (code 1603).** The cause, found in winget's log: Python's *tests* package (`test_JustForMe`) was failing, and BRAIN doesn't need it. Now Python is installed in a reduced form (`Include_test=0 Include_doc=0 Include_tcltk=0 Include_dev=0`) before trying winget. It now also looks for Python in the Windows registry and in any `Python3*` folder (even if it's not on the PATH), installs with winget for the current user only, logs the installation, and if it fails, explains what to do (restart, uninstall an older Python, install it by hand). And if the Windows Installer fails (1603), the installer falls back to a **portable copy of Python** (a zip from python.org, a `python` folder inside BRAIN) that needs no installer; BRAIN only uses the standard library. All the `.bat` files (home automation, energy, access, diagnostics, improve AI, start, close) now check for that portable copy first; before, they said "can't find Python". Limitation: with no `pip`, the optional voice install (Whisper) won't work with that copy.

### Added

* The icon's menu shows checked boxes (alerts muted, background mode, start with Windows) and *Settings* has the matching switches.
* `main.py --close`.
* Signing out of Windows or Ctrl+C also close the icon and window.

### Not verified on real Windows

The icon, window and `pythonw` changes were written against Windows' documented behavior and covered with simulated tests (318 pass), but could not be run on a real Windows machine.

---

## [1.0.3] - 2026-10-12

### Fixed

* `CONFIGURAR_ACCESO.bat` reported "BRAIN responded with code 403" with no explanation. Now the self-test shows the code, the BRAIN version that answered, the port and the response, and warns if what answered is an **old copy** of BRAIN still running (which doesn't understand Tailscale addresses and rejects them with 403). BRAIN announces its version in the `Server` header, and the 403 shows the `Host` it received.
* `CERRAR_BRAIN.bat` also closes old copies (`--web` mode), not just the desktop program's.

---

## [1.0.2] - 2026-10-12

### Fixed

* **"Quit BRAIN" from the icon next to the clock didn't close BRAIN.** The icon notified BRAIN through a pipe between processes and launched a thread with PowerShell code that can't run outside the main thread. Now the icon asks BRAIN for each action over its local address (`/api/desktop/show|mute|autostart|quit`, only from the PC itself), BRAIN responds before closing, and the icon only disappears once BRAIN has actually stopped existing. Verified that the process ends and cleans up its instance file.
* The icon uses BMP frames (the format most compatible with `System.Drawing.Icon`) instead of PNG.

### Added

* **Fully close BRAIN** in two more ways, in case the icon doesn't appear: a button in the window's own *Settings* and `CERRAR_BRAIN.bat`.

---

## [1.0.1] - 2026-10-12

### Fixed

* **Access from the phone: "This page isn't working".** (a) An unexpected failure inside the server cut the connection with no response (the browser shows it as "didn't send any data"); now it answers with a readable 500 error and logs it. (b) The password screen was sent with code 401, which some browsers replace with their own generic error; now it's sent with 200. (c) `tailscale serve` is now published pointing explicitly at `http://127.0.0.1:<port>`, and if BRAIN had to use a port other than 8765, it republishes on its own. (d) `CONFIGURAR_ACCESO.bat` no longer calls the job done without checking: it verifies that BRAIN answers under Tailscale's private name and shows what Tailscale has published.

---

## [1.0.0] - 2026-10-12

### Added

* **BRAIN as a desktop program** (`python main.py --desktop`, or the BRAIN icon): its own tab-less window (Microsoft Edge or Chrome in app mode, with a separate profile independent from Brave), an icon next to the clock with a menu (*Open*, *Mute alerts*, *Start with Windows*, *Quit*), single instance (opening it twice just shows the window) and background startup with Windows (`--background`), so alerts and reminders still sound even with the window closed. No tray icon; closing the window closes BRAIN.
* BRAIN's own original **logo and icons** (two hemispheres with a neural network and an amber spark): `brain.ico` for Windows, 192/512 PNGs and an Apple one for mobile.
* **`Setup.exe` installer**: `CREAR_SETUP.bat` builds it with IExpress (included in Windows). Installs to `%LOCALAPPDATA%\BRAIN`, keeps your data on update, prepares Python, Ollama and the model, creates shortcuts with the logo, and uninstalls from *Apps* (asks whether to also delete the data). `INSTALAR.bat` now also creates the desktop and Start-menu icons and turns on starting with Windows.
* **Custom sounds from the interface**: the gear icon in **Settings** → upload a `.wav`, `.mp3` or `.ogg` (max 3 MB; sanitized name, only those extensions), pick a sound per alert type with an instant preview, and remove uploaded sounds.
* **Access from the phone and other PCs** (Tailscale): `CONFIGURAR_ACCESO.bat` / `--configure-access` sets the password, detects the private `*.ts.net` name and publishes BRAIN with `tailscale serve` (HTTPS, no router ports opened). New security layer (`brain/web/access.py`): PBKDF2-SHA256 password hashing (200,000 rounds), HMAC-signed session cookie (`HttpOnly`, `SameSite=Strict`, `Secure` over HTTPS, 30 days, invalidated when the password changes), 60-second lockout after 5 failures, `Host` and `Origin` checks, and external access stays closed with no password set. No password is asked for from the PC itself; changing the password or showing the window is only possible from the PC.
* **Installable mobile app** (PWA): manifest, icons and a service worker; its own splash screen.
* Redesigned English README (real light/dark/mobile screenshots, requirements table), `README.es.md` with the previous one, `LICENSE` (MIT) and `REMOTE_ACCESS.md`.

### Fixed

* **Microphone: resampling with a low-pass filter.** Downsampling audio from 44.1/48 kHz to 16 kHz used linear interpolation (server) or block averaging (browser), neither of which filters: high frequencies folded back onto the voice (a 15 kHz tone reappeared at 72% of its strength). Both now use a sinc filter with a Blackman window before decimating (the same tone now measures 0.0000 and the voice 1.000). Thanks to the feedback received.

### Changed

* `INICIAR.bat` opens the desktop program; browser mode moves to `INICIAR_NAVEGADOR.bat`.
* The web icon moves from a hand-drawn favicon to the new logo.
* Tests: 253 -> 297.

### Not verified on real Windows

The tray icon (PowerShell `NotifyIcon`), the Edge window in app mode, `Setup.exe` (IExpress), the autostart registry entry and Whisper with real audio were written against documented behavior but could not be run on a real Windows machine while preparing this version.

---

## [0.10.0] - 2026-10-11

### Added

* **Proactive daily summary**: every morning (by default at 8:30, if BRAIN is open; if you open it later, it arrives then, up to 21:00) you get an alert with today's and tomorrow's agenda, chores, reminders, the shopping list, yesterday's solar production, sensor alerts, expiring warranties and your weight. Tools `view_daily_summary` and `configure_daily_summary` ("send me the summary at 7:45").
* **Alerts with sound**: a notice center (bell icon on the web, history in SQLite) with Windows notifications and its own sound. Each alert type (`alert`, `reminder`, `summary`, `automation`, `energy`, `info`) can have its own sound: copy `.wav`, `.mp3` or `.ogg` files into `data/sounds/` and tell BRAIN "set the bell.wav sound for reminders". "Do not disturb" window (by default 23:00-07:00; critical alerts always sound) and a mute mode. Reminders ("remind me in 20 minutes to take out the chicken") and an alert 30 minutes before timed calendar events. Tools: `create_reminder`, `view_reminders`, `cancel_reminder`, `view_notices`, `mark_notices_read`, `view_sounds`, `assign_sound`, `configure_notices`, `test_notice`.
* **Natural-language automations**: "tell me when the panels go over 3 kW", "turn off the lights every night at 23:30". Triggers by time (with days), by a device's state or by energy; actions to notify, turn on, turn off and run a scene (never locks, garages or alarms). Tools `create_automation`, `view_automations`, `delete_automation`, `toggle_automation`, `run_automation`.
* **Energy optimizer**: using the inverter's history, `view_energy_advice` says which hours have spare solar production (the best times for the washing machine, dishwasher or water heater), when the house consumes the most, and how the day's production is going.
* **Scale by photo**: the camera button in the chat sends a photo of your scale's app screen; a vision model in Ollama reads the weight (and fat, BMI, water, muscle mass, etc. if shown), BRAIN validates the numbers and saves them. Out-of-range data is rejected instead of being saved incorrectly. Needs a vision-capable model installed (BRAIN tells you if there isn't one). Tool `view_body_measurements`.
* **Appliances**: stores the brand, model, purchase date and warranty of each appliance; if one breaks, `check_appliance` combines its record with excerpts from its manuals in `data/documents/` to help diagnose it. The daily summary warns about expiring warranties. Tools `add_appliance`, `view_appliances`, `remove_appliance`, `check_appliance`.
* **Parallel conversations**: tabs in the chat to keep several independent conversations (for example, one just about recipes), each with its own history and, if you want, a topic that BRAIN only follows within it.

### Changed

* **The AI only gets the tools for the topic at hand**: with 70 tools, their descriptions took up about 11,000 of the 16,384 context tokens and would have brought back empty responses. Now each question only sends the tools for the topics being discussed (and from the latest part of the conversation); the rest stay available when needed.
* Total tools: 48 -> 70.

---

## [0.9.0] - 2026-10-11

### Added

* **SQLite database** (`brain/core/database.py`, file `data/brain.db`, standard library only): weight, sensor readings, daily solar production and a new real-time energy history move from JSON to tables indexed by date. Every operation uses `with sqlite3.connect(...)` (it either commits fully or rolls back) and old data migrates itself on first startup (a `.premigration` copy of each JSON file is kept). The 42 previous tools keep their signature. Pantry, shopping, calendar, memory and configuration stay in JSON.
* **Background scheduler** (`brain/core/scheduler.py`): its own thread that starts with `main.py` without blocking the web app or the console; an error in one task is logged and never stops it. Default tasks: a daily backup and polling Home Assistant every 120 s (`BRAIN_POLL_SECONDS`), which saves energy to the history and watches smoke, gas, CO, water-leak and similar sensors. `BRAIN_SCHEDULER=0` turns it off.
* **Backups** (`brain/modules/system.py`): `create_backup`, `view_backups` and `restore_backup`. A `backup_YYYYMMDD_HHMMSS.zip` in `data/backups/` with a SHA-256 checksum manifest (does not include the voice models, which can be downloaded again). Only the last 5 are kept. Restoring validates the zip, saves the current state first (`prerestore_*.zip`) and recovers it if anything fails. "Backups" panel on the web.
* **`add_missing_recipe_ingredients_to_shopping`**: compares a recipe's ingredients against the fridge, freezer, pantry and household basics, and adds to the shopping list in one go whatever is missing or out of stock, without duplicating what's already on the list. Understands "2 eggs", "200 g of flour" and plurals.
* **Local documents** (`brain/modules/documents.py`): `search_documents` and `read_document` over the `.txt`, `.md` and `.json` files in `data/documents/`, with excerpts and BM25 scoring in pure Python (no embeddings). The index updates itself whenever the files change.

### Changed

* Total tools: 42 -> 48 (6 new: `add_missing_recipe_ingredients_to_shopping`, `create_backup`, `view_backups`, `restore_backup`, `search_documents`, `read_document`).

---

## [0.8.0] - 2026-10-09

### Fixed

* **Empty responses ("I couldn't generate a response")**: the tool descriptions took up about 5,000 tokens and the AI's working memory was 8,192, so the model lost its instructions. It's now 16,384, long messages are saved trimmed in the history, and if the model answers empty, it's asked once more before giving up (with a helpful message if it still fails).
* **A pasted list ended up on the shopping list**: now a long list of products (like one from a supermarket order) is saved straight to the pantry, without going through the AI, and only goes to the shopping list if you say so ("...to the shopping list").
* The list parser now understands `Name: 2 units`, abbreviated units, "approx.", `Eggs (12)`, titles ending in ":" and an introductory sentence before the list.
* Mobile: the chat no longer overflows the screen.

### Added

* **Import list** (button in the pantry and in shopping): paste the text as is, choose the destination (pantry, fridge, freezer or shopping), BRAIN shows you what it understood and adds it once you confirm.
* **Delete**: an × button on each product, "Clear" (with confirmation) and tools `remove_from_shopping`, `clear_shopping_list`, `delete_from_inventory`, `clear_inventory` ("clear the shopping list" now works).
* **Recipes with your pantry**: `available_ingredients` gives the AI what's at home plus the **basics** (water, oil, salt, sugar, flour, spices...). Basics can be edited ("I'm out of cumin", `add_basic`, `remove_basic`, `view_basics`) and show up in the panel.
* **Home automation in the panel**: devices found appear by room, with a toggle to turn on or off (lights, plugs, fans, blinds, climate, TVs) and buttons for scenes. Still cannot touch locks, doors, garages or alarms.
* **Microphone that works in Brave** (and any browser): the web app records, BRAIN transcribes it on your PC with Whisper (`faster-whisper`), and the audio never leaves the computer. Installed once with the "Install voice" button (about 500 MB). Chrome and Edge keep using the browser's own recognition unless you install it.
* **New interface**: light and dark theme (with a toggle), real-time energy at the top right, chat with bold text and lists, a tabbed mobile version.

### Removed

* The "Solar production (history)" card: replaced by "Energy now".

---

## [0.7.0] - 2026-10-07

### Fixed

* **Products weren't being saved to the inventory** (and the AI said they were): any tool with a parameter named `name` (`add_inventory`, `remove_inventory`) always failed with "got multiple values for argument 'name'". Fixed at the root, with a regression test.
* Quantities written as text ("1 unit", "2 units", "1.5 kg", "two") no longer error out.
* Arguments the AI makes up are now ignored instead of failing; an unknown location ("kitchen cupboard") goes to the pantry; memory accepts any unknown type and "everything/memories" to see it all.
* The AI can chain up to 12 steps (up from 6) and, if it can't finish, says so clearly instead of claiming it did.
* **Diagnostics**: no longer breaks on Windows over `netstat`/`tasklist` encoding.
* **Installer**: no longer gives a false "Ollama still has no model" after downloading it successfully; BRAIN now checks for itself that the model shows up in Ollama and, if not, says so with instructions.

### Added

* **Bulk add**: `add_several_inventory` and `add_several_to_shopping` understand pasted lists as-is ("Whole milk, 2 units", "2 x eggs", "Bread x3"), in a single operation.
* **"Ran out"**: `ran_out` removes the product from the inventory and adds it to the shopping list. Using up the last unit with `remove_inventory` also adds it.
* **Pantry panel** in the web interface: the whole inventory grouped by location, with quantities.
* **Real-time energy**: an "Energy now" panel (production, consumption, buying/selling to the grid, battery) that updates every 5 seconds, and a `view_energy_now` tool ("how much am I using right now?"). Reads the inverter and meter through Home Assistant (Huawei, Fronius, SolarEdge, Growatt, Solax, GoodWe, Victron, Shelly...). Detects the sensors on its own; `CONFIGURAR_ENERGIA.bat` lets you pick them by hand.

---

## [0.6.0] - 2026-10-07

### Added

* **Home automation with Home Assistant**: BRAIN controls lights (on, off, brightness, color, white tone), plugs, blinds, thermostats and scenes, and reads sensors. Works with any brand that has Home Assistant. Understands names and rooms ("the living-room light", "all the kitchen lights") and asks when unsure.
  * 8 new tools: `turn_on`, `turn_off`, `set_light`, `move_blind`, `set_temperature`, `activate_scene`, `view_devices`, `device_state`.
  * `CONFIGURAR_DOMOTICA.bat`: a wizard that finds Home Assistant and tests the connection.
  * Safety: never opens locks, doors, garages or gates, and never touches alarms (read-only).
  * Guide: `SMART_HOME_GUIDE.md`.
* **Automatic choice of the best AI model for the PC** (`MEJORAR_IA.bat` / `main.py --improve-ai`): measures RAM, NVIDIA card (VRAM) and free disk space and picks between Qwen 3.8 27B, Gemma 4 (26B, 12B, E4B, E2B) or Qwen 3 4B. If one download fails, it tries the next smaller one. The installer uses this same system.
* Diagnostics now shows the machine's specs, the ideal model, what `ollama list` sees, and which program is listening on Ollama's port.

### Fixed

* **"AI unavailable" after installing**: BRAIN only tried to start Ollama once (8 s). Now it retries in the background only (up to 90 s per attempt), the page checks more often in the meantime, and there's a **Retry** button.
* **"Ollama works but has no model"**: BRAIN now downloads the model through the very same Ollama it will later use (before, `ollama pull` could install it somewhere else). The web interface offers a **Download AI** button with a progress bar.
* BRAIN respects the `OLLAMA_HOST` variable, same as the `ollama` command.
* The installer now checks at the end that the model really shows up in Ollama.

---

## [0.5.0] - 2026-10-07

### Added

* **Full support for Windows 10 and 11**:
  * `INSTALAR.bat`: installs Python and Ollama if missing, downloads an AI model, checks BRAIN and creates a desktop shortcut.
  * `INICIAR.bat` (web interface), `INICIAR_CONSOLA.bat` (chat in the black window) and `DIAGNOSTICO.bat`.
  * UTF-8 console: no more errors with accents, special characters and emoji in the Windows console.
  * Data writes now tolerate antivirus / OneDrive locks.
* **Local web interface** (`http://127.0.0.1:8765`): chat, panel with weight, calendar, shopping, solar energy, voice dictation and text-to-speech. Only reachable from the machine itself.
* **Console chat** (`python main.py --console`) with commands `/help`, `/tools`, `/models`, `/clear`, `/exit`.
* `python main.py --diagnose` to see what's installed and what's failing.
* **Persistent conversation memory**: BRAIN remembers what was said even after being closed and reopened.
* **Permanent memory**: tools `remember`, `check_memory` and `forget`; what's remembered is always included in the AI's context.
* **Historical queries**: `weight_on_date`, `weight_history` (with change between records).
* **Several tools in one response** (up to 6 chained steps).
* **22 new tools** for Inventory, Shopping, Calendar, Solar Energy, Memory and Sensors.
* Ollama's native tool calling, with an automatic fallback to JSON commands in text for models that don't support it.
* The AI is given its personality (`personality.md`), the current date and time, and permanent memory.
* Offline tests with a simulated Ollama (72 tests, no real AI needed, your data untouched) and `scripts/try_ai.py` to test against your real Ollama.
* Error and event logging in `data/logs/`.
* `.gitattributes` (the `.bat` files keep Windows line endings) and `pyproject.toml` (Black).

### Changed

* All data now lives under `data/` (merged the duplicate `brain/data/` folder).
* `save_weight` and solar production now update the day's record instead of duplicating it; the date is optional (today by default).
* The modules now share a base class (`BaseModule`) instead of repeating code.
* `brain.core` lazily imports `Brain` to avoid circular imports.
* `requirements.txt` no longer lists any packages (BRAIN only uses the standard library); development tools move to `requirements-dev.txt`.
* Ollama: now uses `127.0.0.1` instead of `localhost` (on Windows, `localhost` often resolves to IPv6), ignores the system proxy, and the context is widened to 8192 tokens.

### Fixed

* The conversation didn't remember earlier messages (the history never reached the AI).
* Encoding errors when printing from the Windows console.
* Tests that wrote to real data and depended on Ollama being on.
* Duplicate test data in weight, solar production and inventory.

---

## [0.4.0] - 2026-08-10

### Added

* Local AI system through Ollama.
* Python client for talking to the Ollama API.
* `BrainAI` layer to abstract the AI provider.
* Detection of available models.
* Support for Qwen 3 4B and Qwen 3 8B.
* Decorator-based registerable tool system.
* Central tool registry.
* Tool executor.
* First working tools for the Health module:

  * `save_weight`
  * `get_weight`
* Integration between the AI and the tools.
* Basic conversation layer.
* Conversation history.
* Tests for tools, AI and conversation.
* `.gitignore` to exclude caches, virtual environments and temporary files.

### Changed

* Restructured BRAIN's core.
* Centralized data access through `DataManager`.
* Improved dynamic module loader.
* Migrated the modules to the new architecture.
* Updated `main.py` to use the new architecture.
* Separated the AI layer from BRAIN's main logic.
* Separated the tool system from the modules.
* Storage organized per module through JSON files.

### Removed

* `brain/tools.py`, replaced by the new tool system.
* `.pyc` files and `__pycache__` directories that were under Git control.

### Status

BRAIN has, for the first time, a complete working flow:

```text
User
   ↓
BRAIN
   ↓
Local AI
   ↓
Decision
   ↓
Tool
   ↓
Module
   ↓
DataManager
   ↓
JSON data
```

The next stage will focus on persistent memory, historical queries, and deeper integration between conversation, memory and tools.

---

## [0.3.0] - 2026-08

### Added

* BRAIN's modular core.
* Module system.
* `DataManager`.
* Knowledge manager.
* Independent persistence per module.
* Migration of the Inventory module to `inventory.json`.
* Modular structure for Health, Energy, Inventory and other modules.

---

## [0.2.0]

### Added

* Initial BRAIN architecture.
* Initial knowledge system.
* Data persistence.
* First working program.
* Python virtual environment.
* Formatting with Black.
