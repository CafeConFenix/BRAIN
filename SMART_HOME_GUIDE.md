# Controlling the home with BRAIN (lights, blinds, plugs, heating...)

BRAIN does not talk directly to each bulb or plug: it talks to **Home Assistant**, a free program that acts as the home's "hub" and understands almost every brand (Philips Hue, IKEA Trådfri, Tuya / Smart Life, Shelly, Xiaomi, Sonoff, Zigbee, Z-Wave, Google Home, Alexa, Tado, Netatmo...).

Once your devices show up in Home Assistant, BRAIN controls them on its own. Just tell it:

* "Turn on the living-room light" · "Turn off all the lights"
* "Set the kitchen light to 30% and warm white" · "Make it blue"
* "Lower the bedroom blind" · "Set the blind to 40%"
* "Set the living-room thermostat to 22 degrees"
* "Activate the night scene"
* "Which lights are on?" · "What's the temperature in the living room?"

If there are two matching devices ("the light" and you have several), BRAIN asks which one instead of guessing.

## The "Home" panel

Once Home Assistant is connected, the panel on the right shows your devices **grouped by room**, each with a **toggle** to turn it on or off (lights, plugs, fans, blinds, climate, TVs) and buttons to run your scenes. It updates on its own every few seconds. If a device is in the wrong room, change it in Home Assistant (*Settings → Areas*).

## Viewing the solar inverter and consumption in real time

If your inverter (Huawei, Fronius, SolarEdge, Growatt, Solax, GoodWe, Victron, SMA...) or your meter (a Shelly EM, for example) already shows up in Home Assistant, BRAIN reads them live:

* On the web, the **Energy now** panel shows, every 5 seconds, the panels' production, the home's consumption, whether you're buying or selling to the grid, and the battery.
* You can ask: "How much am I using right now?" · "How much are the panels producing now?"

BRAIN finds the sensors on its own. To pick them by hand or fix them, double-click **`CONFIGURAR_ENERGIA.bat`**. If your setup has no consumption sensor, BRAIN calculates it (production + what you buy from the grid).

If your inverter doesn't show up in Home Assistant yet, add it under *Settings → Devices & Services* (almost every brand has an official integration).

## Safety

BRAIN **never** opens locks, doors, garages or gates, and never touches alarms. It can only *read* their state ("is the door closed?"). This is a design decision: a conversation should not be able to open your house.

## Step 1: have Home Assistant

**If you already have it** (on a Raspberry Pi, Home Assistant Green, a NAS...): skip to step 2.

**If you don't have it**, here are the simplest ways, from easiest to most work:

1. **Home Assistant Green**: an official little box that plugs into your router. The easiest option for non-programmers.
2. **Raspberry Pi 4 or 5**: install it with the official *Raspberry Pi Imager* tool, choosing "Home Assistant OS".
3. **On this same Windows PC**: possible, but needs a virtual machine and is heavier. Not recommended if the PC turns off at night.

Official step-by-step guide: <https://www.home-assistant.io/installation/>

Then, in Home Assistant, add your devices from *Settings → Devices & Services → Add integration*. **Assign each device to its room** (*Settings → Areas*): that way BRAIN understands "the living-room light" even if the device is named something else.

## Step 2: connect BRAIN (only once)

1. In Home Assistant: click your name (bottom left) → **Security** tab → at the bottom, **Long-lived access tokens** → **Create token**. Name it `BRAIN`, **copy the long text** that appears (it's only shown once).
2. In BRAIN, double-click **`CONFIGURAR_DOMOTICA.bat`**.
3. Press Enter if BRAIN finds Home Assistant on its own, or type its address (for example `192.168.1.50:8123`). Paste the token (it won't be visible while pasting) and press Enter.
4. If everything goes well, you'll see how many lights, blinds, etc. it found.

The token is saved to `data\smart_home\home_assistant.json`, only on your PC. Don't share it or upload that folder to the internet.

## If something goes wrong

| Symptom | Fix |
| --- | --- |
| "Can't connect to Home Assistant" | Check that it's on and that this PC is on the same network/wifi. Try opening its address in the browser. |
| "The access key was rejected" | Create a new token and run `CONFIGURAR_DOMOTICA.bat` again. |
| "I can't find a matching device" | Check the name in Home Assistant. BRAIN will tell you which devices it sees. |
| BRAIN doesn't understand which room you mean | Assign the device to an Area in Home Assistant. |
| New devices don't show up | BRAIN refreshes the list every minute; wait a bit or repeat the command. |
| The AI says it did it but nothing happens | Can happen with very small models sometimes. Run `MEJORAR_IA.bat` to use a better one. |

## For those who know a bit more

* It can also be configured with the `BRAIN_HA_URL` and `BRAIN_HA_TOKEN` environment variables.
* Controllable device types: lights, plugs and switches, fans, blinds/curtains (not garages), climate, scenes, scripts, players, humidifiers, vacuums.
* Read-only: sensors, binary sensors, locks, alarms, weather, people.
