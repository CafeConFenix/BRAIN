import os
import platform
import re
import subprocess
import time

from brain.ai.ollama import OllamaError, find_executable
from brain.core.config import Config
from brain.i18n import t
from brain.utils.processes import execute
from brain.core.hardware import alternatives, detect_hardware, save_model, recommend_model

HELP = """
Commands:
  /help     show this help
  /tools    list what BRAIN can do
  /models   list the installed AI models
  /clear    clear the conversation history
  /exit     close BRAIN
"""


def prepare_ai(brain, interactive=True):
    """
    Checks that Ollama and a model are ready, and gets them ready if it can.

    Returns (True, "") if everything is ready, or (False, message) with what
    needs to be done to fix it.
    """

    ollama = brain.ai.ollama

    if not ollama.active_server():
        if find_executable() is None:
            if os.name == "nt":
                return False, t(
                    "I can't find Ollama on this computer. Run INSTALL.bat "
                    "(or install it from https://ollama.com/download) and open BRAIN again."
                )

            return False, t(
                "I can't find Ollama on this computer. Install it from "
                "https://ollama.com/download and open BRAIN again."
            )

        if interactive:
            print(t("Starting Ollama..."))

        if not ollama.start_server():
            return False, t("I was not able to start Ollama. Open it from the Start menu and try again.")

    try:
        models = [m for m in ollama.models() if "embed" not in m.lower()]
    except OllamaError as error:
        return False, str(error)

    if models:
        return True, ""

    model = Config.MODEL or recommend_model()["label"]

    message = t("Ollama has no AI model installed. Download it with: ollama pull {0}", model)

    if not interactive:
        return False, message

    print(t("\nOllama has no AI model installed. BRAIN needs one ({0}, about 2.5 GB).", model))

    try:
        response = input(t("Do you want to download it now? (y/n): ")).strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False, message

    if response not in {"y", "yes", "s", "si"}:
        return False, message

    try:
        if ollama.download_model(model):
            return True, ""
    except OllamaError as error:
        return False, str(error)

    return False, message


def _output_of(command, wait=15):
    """
    Runs a command and returns its output as text.

    Windows programs (netstat, tasklist...) write in the console's code page,
    not UTF-8: this decodes without ever failing.
    """

    try:
        result = execute(command, capture_output=True, timeout=wait)
    except (OSError, subprocess.SubprocessError):
        return ""

    return (result.stdout or b"").decode("utf-8", errors="replace")


def who_listens(url):
    """
    Names of the programs listening on Ollama's port (Windows only). Used to
    detect a second Ollama (for example in Docker).
    """

    if os.name != "nt":
        return []

    port = url.rsplit(":", 1)[-1].strip("/")

    output = _output_of(["netstat", "-ano", "-p", "tcp"])

    pids = set()

    for line in output.splitlines():
        parts = line.split()

        if len(parts) >= 5 and parts[3].upper() == "LISTENING" and parts[1].endswith(f":{port}"):
            pids.add(parts[4])

    names = []

    for pid in sorted(pids):
        task = _output_of(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"])
        match = re.match(r'"([^"]+)"', task.strip())
        names.append(f"{match.group(1) if match else t('unknown')} (PID {pid})")

    return names


def diagnose(brain):
    """Shows the system's state (useful to see what's wrong)."""

    ollama = brain.ai.ollama

    print("\n=== " + t("BRAIN DIAGNOSTICS") + " ===")
    print(f"{t('BRAIN version')}    : {Config.VERSION}")
    print(f"Python           : {platform.python_version()} ({platform.system()} {platform.release()})")
    print(f"{t('Data')}             : {Config.DATA}")
    print(f"{t('Ollama (program)')} : {find_executable() or t('NOT FOUND')}")
    print(f"{t('Ollama (server)')}  : {'active' if ollama.active_server() else t('off')} {t('at')} {ollama.url}")

    try:
        models = ollama.models()
        print(f"{t('Models')}           : {', '.join(models) or t('none')}")

        if models:
            print(f"{t('Chosen model')}     : {ollama.resolve_model()}")
    except OllamaError as error:
        print(f"{t('Models')}           : {t('not available')} ({error})")

    if os.environ.get("OLLAMA_HOST"):
        print(f"OLLAMA_HOST      : {os.environ['OLLAMA_HOST']}")

    if os.environ.get("OLLAMA_MODELS"):
        print(f"OLLAMA_MODELS    : {os.environ['OLLAMA_MODELS']}")

    listing = ollama.list_by_command()

    if listing:
        print(t("What the 'ollama list' command sees:"))

        for line in listing.splitlines():
            print(f"    {line}")

    try:
        listen = who_listens(ollama.url)
    except Exception:
        listen = []

    if listen:
        print(t("Programs listening on that port: {0}", ', '.join(listen)))

    try:
        recommended = recommend_model()
        print(f"{t('Your computer')}    : {recommended['hardware'].summary()}")
        print(t("Ideal model     : {0} (install it with UPGRADE_AI.bat)", recommended["label"]))
    except Exception as error:
        print(t("Your computer    : I could not measure it ({0})", error))

    print(f"{t('Modules')}          : {', '.join(brain.modules.items())}")
    print(f"{t('Tools')}            : {len(brain.tools.items())}")


def configure_energy(brain):
    """Wizard to choose the inverter and meter sensors."""

    from brain.integrations.home_assistant import HomeAssistant, HomeAssistantError
    from brain.modules.energy import (
        ROLE_NAMES,
        ROLES,
        RealtimeEnergy,
        _to_watts,
        _is_power,
        describe,
        detect_sensors,
        save_energy_sensors,
    )

    print("\n=== " + t("VIEW THE INVERTER IN REAL TIME") + " ===")

    ha = HomeAssistant()

    if not ha.configured:
        print(t("You need to connect Home Assistant first: run CONFIGURE_SMART_HOME.bat."))
        return 1

    try:
        states = ha.states()
    except HomeAssistantError as error:
        print(f"[{t('Error')}] {error}")
        return 1

    candidates = detect_sensors(states)

    powers = [
        {"entity": e["entity_id"], "name": (e.get("attributes") or {}).get("friendly_name", e["entity_id"]), "value_w": round(_to_watts(e))}
        for e in states
        if _is_power(e) and _to_watts(e) is not None
    ]

    if not powers:
        print(t("Home Assistant has no power sensor (W or kW)."))
        print(t("First add your inverter in Home Assistant (Settings > Devices & Services) and run this again."))
        return 1

    print(t("I'll look in Home Assistant for your solar inverter's and meter's sensors."))
    print(t("For each question: Enter = pick the first one (the best match), 0 = none, a = see all.\n"))

    def show(items):
        for i, c in enumerate(items, 1):
            value = "" if c["value_w"] is None else t("  (now: {0} W)", c["value_w"])
            print(f"   {i}) {c['name']}{value}")

    chosen = {}

    for role in ROLES:
        if role == "battery_pct":
            items = candidates[role]

            if not items:
                continue
        else:
            items = candidates[role] or []

        print(f"\n» {ROLE_NAMES[role].capitalize()}:")

        if items:
            show(items)
        else:
            print(t("   (I found none that match)"))

        while True:
            try:
                response = input(t("   Your choice: ")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                return 1

            if response == "a" and role != "battery_pct":
                items = powers
                show(items)
                continue

            if response == "" and items:
                chosen[role] = items[0]["entity"]
                break

            if response in ("0", ""):
                break

            if response.isdigit() and 1 <= int(response) <= len(items):
                chosen[role] = items[int(response) - 1]["entity"]
                break

            print(t("   I did not understand; type a number, Enter, 0 or a."))

    if not chosen:
        print(t("\nYou chose no sensor; nothing is changed."))
        return 1

    # The sign of "grid" depends on the device: found out by asking.
    if chosen.get("grid"):
        current = next((p["value_w"] for p in powers if p["entity"] == chosen["grid"]), None)

        if current is not None and abs(current) > 50:
            print(t("\nThe grid sensor currently reads {0} W.", current))

            try:
                response = input(t("Are you currently BUYING electricity from the grid (b), SELLING it (s) or not sure (?): ")).strip().lower()
            except (EOFError, KeyboardInterrupt):
                return 1

            if response.startswith("b") and current < 0:
                chosen["grid_inverted"] = True
            elif response.startswith("s") and current > 0:
                chosen["grid_inverted"] = True

    save_energy_sensors(chosen)

    print("\n[OK] " + t("Saved. This is what I see right now:"))
    print("   " + describe(RealtimeEnergy().read()))
    print("\n" + t("BRAIN will show it live in the 'Energy now' panel."))

    return 0


def configure_smart_home(brain):
    """Wizard to connect BRAIN with Home Assistant."""

    from getpass import getpass

    from brain.integrations.home_assistant import (
        HomeAssistant,
        HomeAssistantError,
        find_home_assistant,
        save_config,
        read_config,
        normalize_url,
    )

    print("\n=== " + t("CONNECT BRAIN WITH SMART HOME (Home Assistant)") + " ===")
    print(t("You need Home Assistant running on your network. If you don't have it, see SMART_HOME_GUIDE.md.\n"))

    current_url, current_token = read_config()

    print(t("Looking for Home Assistant on your network..."))
    found = find_home_assistant()

    suggested = current_url or found

    if found:
        print(t("I found it at {0}", found))
    else:
        print(t("I could not find it automatically."))

    try:
        input_value = input(t("Home Assistant address [{0}]: ", suggested or t("for example 192.168.1.50:8123"))).strip()
    except (EOFError, KeyboardInterrupt):
        return 1

    url = normalize_url(input_value or suggested)

    if not url:
        print(f"[{t('Error')}] " + t("I need the Home Assistant address."))
        return 1

    print("\n" + t("Now I need the access key (token). To create it:"))
    print("  1. " + t("Open Home Assistant in your browser and go to your profile (your name at the bottom left)."))
    print("  2. " + t("'Security' tab > at the bottom 'Long-Lived Access Tokens' > 'Create Token'."))
    print("  3. " + t("Name it BRAIN, copy the long text that appears and paste it here (right-click)."))

    try:
        token = getpass("\n" + t("Token (it will not show as you paste it, then press Enter): ")).strip()
    except (EOFError, KeyboardInterrupt):
        return 1

    token = token or current_token

    if not token:
        print(f"[{t('Error')}] " + t("I need the token."))
        return 1

    client = HomeAssistant(url, token)

    print("\n" + t("Testing the connection..."))

    try:
        client.check()
        states = client.states()
    except HomeAssistantError as error:
        print(f"[{t('Error')}] {error}")
        print(t("I have not saved anything. Check the details and run it again."))
        return 1

    save_config(url, token)

    accounts = {}

    for state in states:
        domain = state.get("entity_id", "").split(".", 1)[0]
        accounts[domain] = accounts.get(domain, 0) + 1

    print("\n[OK] " + t("Connected to Home Assistant. Here is what BRAIN can control:"))

    for domain, name in (
        ("light", t("lights")),
        ("switch", t("plugs and switches")),
        ("cover", t("blinds and curtains")),
        ("climate", t("thermostats")),
        ("scene", t("scenes")),
        ("media_player", t("media players")),
    ):
        if accounts.get(domain):
            print(f"  - {accounts[domain]} {name}")

    if not accounts.get("light") and not accounts.get("switch"):
        print(t("  (There are no lights or plugs yet. Add your devices in Home Assistant and BRAIN will see them on its own.)"))

    print("\n" + t("You can now open BRAIN and say: «Turn on the living room light»."))

    try:
        from brain.modules.energy import detect_sensors

        if detect_sensors(states)["production"]:
            print("\n" + t("I found sensors that look like a solar inverter."))

            if input(t("Do you want to see production and consumption in real time now? (y/n): ")).strip().lower() in {"y", "yes", "s", "si"}:
                return configure_energy(brain)
    except (EOFError, KeyboardInterrupt):
        pass

    return 0


def _appears_in_ollama(ollama, label, attempts=10):
    """Checks (with some patience) that Ollama lists the just-downloaded model."""

    for _ in range(attempts):
        try:
            if ollama._find_model(label, ollama.models()):
                return True
        except OllamaError:
            pass

        time.sleep(1)

    return False


def upgrade_model(brain, auto=False):
    """
    Measures the computer, chooses the best AI model that fits it and downloads it.

    With auto=True it asks no questions (used by the installer). Returns 0 if
    BRAIN ends up with a model ready.
    """

    ollama = brain.ai.ollama

    print("\n=== " + t("UPGRADE BRAIN'S AI") + " ===")
    print(t("Measuring your computer..."))

    recommended = recommend_model(detect_hardware())
    label = recommended["label"]

    print(recommended["hardware"].summary())

    for note in recommended["hardware"].notes:
        print(f"[!] {note}")

    print(t("\nRecommended model: {0} (about {1:g} GB to download)", label, recommended["download_gb"]))
    print(recommended["explanation"])

    if not ollama.active_server():
        print("\n" + t("Starting Ollama..."))

        if not ollama.start_server(wait=90):
            print(f"[{t('Error')}] " + t("I can't start Ollama. Run INSTALL.bat or open it from the Start menu."))
            return 1

    installed_models = ollama.models()

    if ollama._find_model(label, installed_models):
        save_model(label)
        print(t("\nYou already have {0} installed. BRAIN will use it.", label))
        return 0

    if not auto:
        try:
            response = input(t("\nDownload it now? (y/n): ")).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return 1

        if response not in {"y", "yes", "s", "si"}:
            print(t("OK, nothing is changed."))
            return 0

    for candidate in [label] + alternatives(label):
        print(t("\nDownloading {0} (only the first time, it may take a while)...", candidate))

        try:
            correct = ollama.download_model(candidate)
        except OllamaError as error:
            print(f"[{t('Error')}] {error}")
            return 1

        if correct:
            if not _appears_in_ollama(ollama, candidate):
                print(t("[!] Ollama says it downloaded {0} but I don't see it in its list.", candidate))
                print("    " + t("There may be two different copies of Ollama on this PC. Run DIAGNOSTICS.bat and send me what it shows."))
                return 1

            save_model(candidate)
            print(t("\nDone: BRAIN will use {0}.", candidate))

            if installed_models:
                print(t("You can delete the old models to free up space (ollama rm name)."))

            return 0

        print(t("[!] Could not download {0}. Trying a smaller one.", candidate))

    # If nothing new could be downloaded, keep whatever was already there.
    if installed_models:
        print("\n" + t("Keeping the model you already had installed."))
        return 0

    print(f"[{t('Error')}] " + t("I was not able to download any model. Check your internet connection."))
    return 1


def console_chat(brain):
    """Text chat in the console."""

    print("\n" + t("Type your message and press Enter. /help for the commands, /exit to close.") + "\n")

    while True:
        try:
            text = input(t("You > ")).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not text:
            continue

        if text.startswith("/"):
            command = text.lower()

            if command in {"/exit", "/quit", "/salir"}:
                break

            if command in {"/help", "/ayuda"}:
                print(HELP)

            elif command in {"/tools", "/herramientas"}:
                for tool in brain.tools.items():
                    print(f"- {tool['name']}: {tool['description']}")

            elif command in {"/models", "/modelos"}:
                try:
                    for model in brain.ai.models():
                        print(f"- {model}")
                except OllamaError as error:
                    print(error)

            elif command in {"/clear", "/limpiar"}:
                brain.conversation.clear()
                print(t("Conversation cleared."))

            else:
                print(t("That command does not exist. Type /help."))

            continue

        try:
            print(t("BRAIN is thinking..."), end="\r", flush=True)

            response = brain.conversation.ask(text)

            print(" " * 30, end="\r")
            print(f"BRAIN > {response}\n")

        except OllamaError as error:
            print(" " * 30, end="\r")
            print(f"[{t('Error')}] {error}\n")

        except KeyboardInterrupt:
            print("\n" + t("Cancelled.") + "\n")

    print(t("Goodbye."))
