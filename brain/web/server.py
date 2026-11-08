import json
import os
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from brain.ai.ollama import OllamaError, find_executable
from brain.ai.vision import MAX_BYTES as MAX_IMAGE
from brain.ai.vision import VisionError, save_reading, read_scale
from brain.core import logger
from brain.core.config import Config
from brain.core.hardware import LEVELS, alternatives, read_saved_model, recommend_model, save_model
from brain.i18n import language, t
from brain.integrations.home_assistant import HomeAssistantError
from brain.modules.system import BackupError
from brain.utils.lists import DESTINATIONS, apply_list, interpret_list
from brain.voice.recognition import Recognizer, VoiceError
from brain.web import home, config
from brain.web.access import SESSION_DURATION, COOKIE_NAME, Access

STATIC = Path(__file__).resolve().parent / "static"

MAX_MESSAGE = 4000
MAX_BODY = 64 * 1024
MAX_AUDIO = 4 * 1024 * 1024

# Local speech recognition (the web page's microphone).
recognizer = Recognizer()


def read_energy():
    """Live production, consumption and grid (the reading never breaks the web page)."""

    from brain.tools.builtin.energy import realtime

    try:
        return realtime.read()
    except Exception as error:
        logger.error(f"Live energy: {error!r}")

        return {"configured": True, "error": t("I could not read the inverter: {0}", error)}


def build_system(brain):
    """Backups, background tasks and Home Assistant alerts."""

    from brain.core.scheduler import scheduler, poll

    system = brain.modules.get("system")

    return {
        "backups": system.list_backups() if system else [],
        "tasks": scheduler.state(),
        "scheduler_active": scheduler.active,
        "alerts": poll.alerts,
    }


def build_notices(brain, after=0):
    """Recent notices and how to deliver them on the web (without duplicating Windows' own sound)."""

    from brain.core import notifier

    notices = brain.modules.get("notices")

    if notices is None:
        return {"notices": [], "unread": 0, "last_id": 0}

    config = notices.config()
    native_delivery = config["native"] and notifier.IS_WINDOWS
    disturb = not notices.in_do_not_disturb()

    items = notices.items(after=after, limit=30)

    for notice in items:
        notice["play_in_web"] = (not config["mute"]) and (not native_delivery) and (notice["level"] == "critical" or disturb)

    all_items = notices.items(unread_only=True, limit=500)

    return {
        "notices": items,
        "unread": len(all_items),
        "last_id": items[-1]["id"] if items else after,
        "mute": config["mute"],
    }


def build_summary(brain):
    """Data for the interface's side panel."""

    health = brain.modules.get("health")
    shopping = brain.modules.get("shopping")
    calendar = brain.modules.get("calendar")
    energy = brain.modules.get("energy")
    inventory = brain.modules.get("inventory")
    memory = brain.modules.get("memory")

    products = sum(len(v) for v in inventory.items().values()) if inventory else 0
    memories = sum(len(v) for v in memory.query().values()) if memory else 0

    return {
        "weight": health.weight_history(30) if health else [],
        "shopping": shopping.items() if shopping else [],
        "agenda": calendar.agenda(14) if calendar else {},
        "solar": energy.production(14) if energy else {},
        "pantry": inventory.everything() if inventory else [],
        "staples": inventory.staples() if inventory else [],
        "inventory_products": products,
        "memories": memories,
    }


_repairer = {"thread": None, "last": 0.0}
_repair_lock = threading.Lock()

# Seconds to wait between one attempt to start Ollama and the next.
WAIT_BETWEEN_ATTEMPTS = 20


def _start_ollama(ollama):
    """Tries to start Ollama (the first time it may take a minute)."""

    try:
        ollama.start_server(wait=90)
    except Exception as error:
        logger.error(f"Could not start Ollama: {error!r}")


def launch_repair(brain, force=False):
    """
    Starts Ollama in the background without blocking the interface.

    It is retried every few seconds while it stays off, because the first
    time it opens after installing it can take a while.
    Returns True if an attempt is underway.
    """

    with _repair_lock:
        thread = _repairer["thread"]

        if thread is not None and thread.is_alive():
            return True

        if not force and time.time() - _repairer["last"] < WAIT_BETWEEN_ATTEMPTS:
            return False

        _repairer["last"] = time.time()

        thread = threading.Thread(target=_start_ollama, args=(brain.ai.ollama,), daemon=True)
        _repairer["thread"] = thread
        thread.start()

        return True


_download_state = {"active": False, "model": "", "percent": 0, "state": "", "error": ""}
_recommended_cache = {}


def _recommended():
    """The ideal model for this computer (measured only once)."""

    if not _recommended_cache:
        try:
            r = recommend_model()
            _recommended_cache.update({"label": r["label"], "download_gb": r["download_gb"]})
        except Exception as error:
            logger.error(f"Could not measure the computer: {error!r}")
            _recommended_cache.update({"label": Config.DEFAULT_MODEL, "download_gb": 2.5})

    return _recommended_cache


def _download(brain, label):
    def progress(state, completed, total):
        _download_state["state"] = state

        if total:
            _download_state["percent"] = int(completed * 100 / total)

    try:
        candidates = [label] + alternatives(label)

        for candidate in candidates:
            _download_state.update({"model": candidate, "percent": 0, "state": t("Starting..."), "error": ""})

            try:
                if brain.ai.ollama.download_model(candidate, progress=progress):
                    save_model(candidate)
                    logger.system(f"Model {candidate} downloaded from the web interface")

                    return

            except OllamaError as error:
                _download_state["error"] = str(error)
                logger.error(f"Downloading {candidate}: {error}")

        if not _download_state["error"]:
            _download_state["error"] = t("Could not download the model.")
    finally:
        _download_state["active"] = False


def launch_download(brain):
    """Downloads the recommended model in the background. True if a download is underway."""

    with _repair_lock:
        if _download_state["active"]:
            return True

        _download_state.update({"active": True, "percent": 0, "state": t("Starting..."), "error": ""})

    threading.Thread(target=_download, args=(brain, _recommended()["label"]), daemon=True).start()

    return True


def _download_exact(brain, label):
    """Downloads exactly the requested model (no smaller fallbacks) and activates it."""

    def progress(state, completed, total):
        _download_state["state"] = state

        if total:
            _download_state["percent"] = int(completed * 100 / total)

    try:
        _download_state.update({"model": label, "percent": 0, "state": t("Starting..."), "error": ""})

        try:
            if brain.ai.ollama.download_model(label, progress=progress):
                select_model(brain, label)
                logger.system(f"Model {label} downloaded and activated from the web interface")

                return
        except OllamaError as error:
            _download_state["error"] = str(error)
            logger.error(f"Downloading {label}: {error}")

        if not _download_state["error"]:
            _download_state["error"] = t("Could not download the model.")
    finally:
        _download_state["active"] = False


def launch_model_download(brain, label):
    """Downloads one exact model (chosen by the user) in the background. True if underway."""

    with _repair_lock:
        if _download_state["active"]:
            return False

        _download_state.update({"active": True, "model": label, "percent": 0, "state": t("Starting..."), "error": ""})

    threading.Thread(target=_download_exact, args=(brain, label), daemon=True).start()

    return True


def select_model(brain, label):
    """Makes ``label`` the model BRAIN uses from now on (remembered between sessions)."""

    save_model(label)
    brain.ai.ollama.model = label
    brain.ai.ollama._models_cache.clear()


def model_catalog(brain):
    """Installed models plus the recommended catalog, marking what is installed and active."""

    try:
        installed = [m for m in brain.ai.ollama.models() if "embed" not in m.lower()]
    except OllamaError:
        installed = []

    try:
        current = brain.ai.ollama.resolve_model()
    except OllamaError:
        current = None

    installed_lower = {m.lower() for m in installed}
    catalog = [
        {
            "label": level["label"],
            "download_gb": level["download_state"],
            "installed": level["label"].lower() in installed_lower,
        }
        for level in LEVELS
    ]

    return {
        "current": current,
        "installed": installed,
        "catalog": catalog,
        "saved": read_saved_model(),
        "download_state": dict(_download_state),
    }


def build_state(brain):
    """AI status to show at the top of the interface."""

    ollama = brain.ai.ollama

    state = {
        "version": Config.VERSION,
        "language": language(),
        "ai_ready": False,
        "model": None,
        "message": "",
        "starting": False,
        "without_models": False,
        "recommended": None,
        "download_state": dict(_download_state),
    }

    try:
        models = [m for m in ollama.models() if "embed" not in m.lower()]

        if not models:
            recommended = _recommended()

            state["without_models"] = True
            state["recommended"] = recommended
            state["message"] = t(
                "Ollama is running (at {0}) but has no AI model. "
                "Click the button to download the one recommended for your PC ({1}, "
                "about {2:g} GB).",
                ollama.url,
                recommended["label"],
                recommended["download_gb"],
            )
        else:
            state["model"] = ollama.resolve_model()
            state["ai_ready"] = True

    except OllamaError as error:
        state["message"] = str(error)

        if find_executable():
            # Ollama is installed but off or starting: an attempt is made to
            # start it in the background and the page will ask again.
            state["starting"] = launch_repair(brain)

            if state["starting"]:
                state["message"] = t("Starting the AI (Ollama)... the first time it may take up to a minute.")
        elif os.name == "nt":
            state["message"] = t(
                "I cannot find Ollama on this computer. Run INSTALL.bat "
                "(or install it from https://ollama.com/download)."
            )
        else:
            state["message"] = t(
                "I cannot find Ollama on this computer. Install it from https://ollama.com/download."
            )

    return state


def read_devices(brain):
    """Smart-home devices for the panel (never breaks the web page)."""

    smart_home = brain.modules.get("smart_home")

    if smart_home is None or not smart_home.connected():
        return {"connected": False, "groups": [], "scenes": [], "total": 0}

    try:
        return {"connected": True, **smart_home.panel()}
    except HomeAssistantError as error:
        return {"connected": True, "error": str(error), "groups": [], "scenes": [], "total": 0}
    except Exception as error:
        logger.error(f"Smart-home panel: {error!r}")

        return {"connected": True, "error": t("I could not read the devices: {0}", error), "groups": [], "scenes": [], "total": 0}


def _import_value(brain, data):
    """Imports (or previews) a pasted list. Returns (code, response)."""

    text = str(data.get("text", ""))
    destination = str(data.get("destination", "auto")).strip().lower()

    if destination not in DESTINATIONS:
        destination = None  # "auto": worked out from the text

    parsed = interpret_list(text, destination)

    if not parsed or not parsed["products"]:
        return 400, {"error": t("I did not find any product in the text. Write one per line, for example: Milk, 2 units.")}

    response = {
        "destination": parsed["destination"],
        "total": len(parsed["products"]),
        "products": [{"name": n, "quantity": c} for n, c in parsed["products"]],
    }

    if data.get("preview_only"):
        return 200, response

    inventory = brain.modules.get("inventory")
    shopping = brain.modules.get("shopping")

    result = apply_list(parsed, inventory, shopping)

    return 200, {**response, "text": result["text"]}


def _action_data(brain, path, data):
    """Interface actions on shopping, inventory and smart home. Returns (code, response)."""

    shopping = brain.modules.get("shopping")
    inventory = brain.modules.get("inventory")
    smart_home = brain.modules.get("smart_home")

    try:
        if path == "/api/import":
            return _import_value(brain, data)

        if path == "/api/shopping/remove":
            return 200, {"removed": [i["product"] for i in shopping.remove(str(data.get("product", "")))]}

        if path == "/api/shopping/clear":
            return 200, {"deleted": shopping.empty()}

        if path == "/api/inventory/delete":
            deleted = inventory.delete(str(data.get("name", "")), data.get("location") or None)

            return 200, {"deleted": [p["name"] for p in deleted]}

        if path == "/api/inventory/clear":
            return 200, {"deleted": inventory.empty(data.get("location") or None)}

        if path == "/api/notices/read":
            return 200, {"marked": brain.modules.get("notices").mark_read(data.get("ids") or None)}

        if path == "/api/backup/create":
            return 200, {"backup": brain.modules.get("system").create_backup()}

        if path == "/api/backup/restore":
            if not data.get("name"):
                return 400, {"error": t("Choose which backup to restore.")}

            return 200, {"restored": brain.modules.get("system").restore_backup_file(str(data["name"]))}

        if path == "/api/device":
            if "on" not in data:
                return 400, {"error": t("Missing whether to turn_on or turn_off.")}

            return 200, smart_home.toggle(data.get("entity", ""), bool(data["on"]))

        if path == "/api/scene":
            return 200, smart_home.run_scene(data.get("entity", ""))

        if path == "/api/expenses/add":
            return 200, {"logged": brain.modules.get("expenses").add(data.get("amount"), data.get("description", ""), data.get("category", ""), data.get("date") or None)}

        if path == "/api/expenses/delete":
            return 200, {"deleted": brain.modules.get("expenses").delete(data.get("id", ""))}

    except HomeAssistantError as error:
        return 502, {"error": str(error)}

    except BackupError as error:
        return 400, {"error": str(error)}

    except ValueError as error:
        return 404, {"error": str(error)}

    return 404, {"error": t("Not found.")}


DATA_ROUTES = (
    "/api/notices/read",
    "/api/backup/create",
    "/api/backup/restore",
    "/api/import",
    "/api/shopping/remove",
    "/api/shopping/clear",
    "/api/inventory/delete",
    "/api/inventory/clear",
    "/api/device",
    "/api/scene",
    "/api/expenses/add",
    "/api/expenses/delete",
)


PUBLIC = {
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
    "/sw.js": ("sw.js", "text/javascript; charset=utf-8"),
    "/favicon.ico": ("iconos/brain.ico", "image/x-icon"),
    "/iconos/icono-192.png": ("iconos/icono-192.png", "image/png"),
    "/iconos/icono-512.png": ("iconos/icono-512.png", "image/png"),
    "/iconos/apple-touch-icon.png": ("iconos/apple-touch-icon.png", "image/png"),
}

MAX_SOUND = 3 * 1024 * 1024
MAX_DOCUMENT = 25 * 1024 * 1024


def login_page(message=""):
    """Entry screen for someone arriving from outside the computer."""

    from html import escape

    return (
        f"""<!doctype html><html lang="{language()}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>BRAIN</title>
<link rel="manifest" href="/manifest.webmanifest"><link rel="icon" href="/iconos/icono-192.png">
<style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#130B22;color:#EDE7FB;font-family:"Segoe UI",system-ui,sans-serif}}
main{{width:min(360px,90vw);text-align:center}}img{{width:96px;height:96px;border-radius:24px}}
h1{{font-size:1.4rem;margin:.6rem 0 1.2rem}}input,button{{width:100%;box-sizing:border-box;padding:.8rem 1rem;border-radius:12px;font-size:1rem;border:1px solid #3A2A5C}}
input{{background:#1C1231;color:inherit}}button{{margin-top:.7rem;background:#6D28D9;color:#fff;border:0;cursor:pointer}}
p{{color:#FF8FB1;min-height:1.4em}}</style></head><body><main>
<img src="/iconos/icono-192.png" alt=""><h1>BRAIN</h1>
<form id="f"><input id="c" type="password" placeholder="{escape(t('Password'))}" autocomplete="current-password" autofocus required>
<button>{escape(t('Enter'))}</button></form><p id="m">"""
        + escape(message)
        + f"""</p></main><script>
document.getElementById("f").onsubmit=async e=>{{e.preventDefault();
const r=await fetch("/api/access/login",{{method:"POST",headers:{{"Content-Type":"application/json"}},
body:JSON.stringify({{key:document.getElementById("c").value}})}});
if(r.ok){{location.href="/";}}else{{const d=await r.json().catch(()=>({{}}));document.getElementById("m").textContent=d.error||"{escape(t('Could not enter.'))}";}}}};
</script></body></html>"""
    ).encode("utf-8")


def create_handler(brain, access=None, on_show=None, actions=None, settings=None):
    chat_lock = threading.Lock()
    access = access or Access()
    # Desktop program actions (show, mute, autostart, quit).
    actions = dict(actions or {})
    if on_show is not None:
        actions.setdefault("show", on_show)

    class Handler(BaseHTTPRequestHandler):
        server_version = f"BRAIN/{Config.VERSION}"
        protocol_version = "HTTP/1.1"

        # ----------------------------------------------------------
        # Utilities
        # ----------------------------------------------------------

        def log_message(self, fmt, *args):
            # Logging every request to the console is silenced.
            pass

        def _host(self):
            return self.headers.get("Host", "")

        def _mode(self):
            """'local' (this same machine), 'remote' (Tailscale or another authorized host) or None."""

            host = self._host()

            if access.is_local(host, self.server.server_address[1]):
                return "local"

            if access.is_remote_allowed(host):
                return "remote"

            return None

        def _valid_origin(self):
            """
            Protects BRAIN from external web pages: only requests aimed at
            localhost or an authorized private address are accepted, and
            only if they come from BRAIN's own interface.
            """

            if self._mode() is None:
                return False

            origin = self.headers.get("Origin")

            if origin is not None:
                return urlparse(origin).netloc.lower() == self._host().lower()

            return True

        def _cookie(self):
            for chunk in self.headers.get("Cookie", "").split(";"):
                name, _, value = chunk.strip().partition("=")

                if name == COOKIE_NAME:
                    return value

            return None

        def _gate(self, path, method):
            """
            Access control. Returns True if the request has already been
            answered (because logging in is needed) and must not be
            processed further.
            """

            if self._mode() != "remote":
                return False

            if path == "/api/access/login" and method == "POST":
                return False

            if not access.configured():
                self._send(403, {"error": t("Access from outside is not enabled. Enable it on the home computer.")})

                return True

            if access.valid_session(self._cookie()):
                return False

            if method == "GET" and (path in PUBLIC):
                return False

            if method == "GET" and not path.startswith("/api/"):
                # 200 and not 401: some browsers replace a 401 page with their own generic error.
                self._send(200, login_page(), "text/html; charset=utf-8")
            else:
                self._send(401, {"error": t("Please log in."), "login": True})

            return True

        def _enter(self):
            data = self._read_json() or {}

            if access.lock_seconds():
                return self._send(429, {"error": t("Too many attempts. Wait {0} s.", access.lock_seconds())})

            if not access.verify_password(data.get("key", "")):
                return self._send(401, {"error": t("Wrong password.")})

            safe = "; Secure" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else ""
            cookie = f"{COOKIE_NAME}={access.create_session()}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_DURATION}{safe}"

            return self._send(200, {"ok": True}, headers={"Set-Cookie": cookie})

        def _send(self, code, body, kind="application/json; charset=utf-8", headers=None):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")

            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            # No persistent connections: this way an unread request body
            # (for example, a rejected request) is never confused with the
            # next request.
            self.send_header("Connection", "close")
            self.close_connection = True
            self.send_header("X-Content-Type-Options", "nosniff")

            for name, value in (headers or {}).items():
                self.send_header(name, value)

            self.end_headers()
            self.wfile.write(body)

        def _read_json(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0

            if length <= 0 or length > MAX_BODY:
                return None

            try:
                data = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None

            return data if isinstance(data, dict) else None

        def _image(self):
            """Receives a photo of the scale, reads it with a vision model and saves the weight."""

            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0

            if not self.headers.get("Content-Type", "").startswith("image/") or length <= 0 or length > MAX_IMAGE:
                return self._send(400, {"error": t("Invalid image (JPG, PNG or WebP, maximum 8 MB).")})

            content = self.rfile.read(length)
            conversation_id = parse_qs(urlparse(self.path).query).get("conversation", ["general"])[0]

            try:
                conversation = brain.conversations.get(conversation_id)
            except KeyError:
                return self._send(404, {"error": t("That conversation does not exist.")})

            health = brain.modules.get("health")

            with chat_lock:
                try:
                    reading = read_scale(brain.ai.ollama, content)
                    text = save_reading(health, reading)

                except VisionError as error:
                    return self._send(422, {"error": str(error)})

                except ValueError as error:
                    return self._send(422, {"error": str(error)})

                except Exception as error:
                    logger.error(f"Image: {error!r}")

                    return self._send(500, {"error": t("I could not analyze the image: {0}", error)})

                conversation.record_exchange(t("📷 Scale photo"), text)

            return self._send(200, {"response": text, "weight": reading["weight"], "date": reading["date"], "measurements": reading["measurements"]})

        def _upload_sound(self):
            """Receives a sound (.wav, .mp3 or .ogg) and saves it to data/sounds/."""

            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0

            if length <= 0 or length > MAX_SOUND:
                return self._send(400, {"error": t("The sound is empty or larger than 3 MB.")})

            name = unquote(self.headers.get("X-Name", ""))
            content = self.rfile.read(length)
            notices = brain.modules.get("notices")

            if notices is None:
                return self._send(404, {"error": t("Notices are not available.")})

            try:
                saved = notices.save_sound(name, content)
            except ValueError as error:
                return self._send(400, {"error": str(error)})

            return self._send(200, {"file": saved, **notices.list_sounds()})

        def _upload_document(self):
            """Receives a manual or note (PDF, .txt, .md, .json) and saves it so it can be searched."""

            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0

            if length <= 0 or length > MAX_DOCUMENT:
                return self._send(400, {"error": t("The file is empty or larger than 25 MB.")})

            name = unquote(self.headers.get("X-Name", ""))
            content = self.rfile.read(length)

            try:
                saved = brain.modules.get("documents").save_file(name, content)
            except ValueError as error:
                return self._send(400, {"error": str(error)})

            return self._send(200, {"saved": saved, "documents": brain.modules.get("documents").items()})

        def _voice(self):
            """Receives a WAV audio from the microphone and returns the text."""

            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0

            if "audio" not in self.headers.get("Content-Type", "") or length <= 0 or length > MAX_AUDIO:
                return self._send(400, {"error": t("Invalid audio.")})

            content = self.rfile.read(length)

            try:
                return self._send(200, {"text": recognizer.transcribe(content)})

            except VoiceError as error:
                return self._send(503 if not recognizer.available() else 400, {"error": str(error)})

            except Exception as error:
                logger.error(f"Voice: {error!r}")

                return self._send(500, {"error": t("I could not transcribe the audio: {0}", error)})

        # ----------------------------------------------------------
        # GET
        # ----------------------------------------------------------

        def _safe(self, action):
            """An unexpected failure answers with a clear error instead of dropping the connection."""

            try:
                action()
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as error:
                logger.error(f"Web server: {error!r}")

                try:
                    self._send(500, {"error": t("Internal error: {0}", error)})
                except Exception:
                    pass

        def do_GET(self):
            self._safe(self._get)

        def do_POST(self):
            self._safe(self._post)

        def _get(self):
            if not self._valid_origin():
                return self._send(403, {"error": t("Access not allowed."), "host": self._host()[:100], "version": Config.VERSION})

            path = urlparse(self.path).path

            if self._gate(path, "GET"):
                return

            if path in PUBLIC:
                file, kind = PUBLIC[path]

                try:
                    return self._send(200, (STATIC / file).read_bytes(), kind)
                except OSError:
                    return self._send(404, {"error": t("Not found.")})

            if path == "/api/access":
                if self._mode() != "local":
                    return self._send(403, {"error": t("Only from the home computer.")})

                return self._send(200, access.state())

            if path in ("/api/desktop", "/api/desktop/state"):
                local = "quit" in actions and self._mode() == "local"
                data = {"available": local}

                if local and settings is not None:
                    try:
                        data.update(settings())
                    except Exception as error:
                        logger.error(f"Desktop settings: {error!r}")

                return self._send(200, data)

            if path == "/api/sounds":
                notices = brain.modules.get("notices")

                return self._send(200, notices.list_sounds() if notices else {"files": [], "assigned": {}, "kinds": []})

            if path in ("/", "/index.html"):
                try:
                    content = (STATIC / "index.html").read_bytes()
                except OSError:
                    return self._send(404, {"error": t("The web interface is missing.")})

                return self._send(200, content, "text/html; charset=utf-8")

            if path == "/api/state":
                return self._send(200, build_state(brain))

            if path == "/api/models":
                return self._send(200, model_catalog(brain))

            if path == "/api/summary":
                return self._send(200, build_summary(brain))

            if path == "/api/energy":
                return self._send(200, read_energy())

            if path == "/api/expenses":
                month = parse_qs(urlparse(self.path).query).get("month", [None])[0]

                return self._send(200, brain.modules.get("expenses").summary(month))

            if path == "/api/system":
                return self._send(200, build_system(brain))

            if path == "/api/devices":
                return self._send(200, read_devices(brain))

            if path == "/api/voice":
                return self._send(200, recognizer.state())

            if path == "/api/notices":
                try:
                    after = int(parse_qs(urlparse(self.path).query).get("after", ["0"])[0])
                except ValueError:
                    after = 0

                return self._send(200, build_notices(brain, after))

            if path.startswith("/api/sound/"):
                notices = brain.modules.get("notices")
                file = notices.sound_path(unquote(path[len("/api/sound/") :])) if notices else None

                if file is None:
                    return self._send(404, {"error": t("Sound not found.")})

                kinds = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg"}

                return self._send(200, file.read_bytes(), kinds.get(file.suffix.lower(), "application/octet-stream"))

            if path == "/api/conversations":
                return self._send(200, {"conversations": brain.conversations.items()})

            if path == "/api/history":
                conversation_id = parse_qs(urlparse(self.path).query).get("conversation", ["general"])[0]

                try:
                    return self._send(200, {"messages": brain.conversations.get(conversation_id).messages()})
                except KeyError:
                    return self._send(404, {"error": t("That conversation does not exist.")})

            if path == "/api/tools":
                return self._send(
                    200,
                    {
                        "tools": [
                            {
                                "name": h["name"],
                                "description": h["description"],
                                "category": h["category"],
                            }
                            for h in brain.tools.items()
                        ]
                    },
                )

            response = config.handle(brain, "GET", path, {}, self._mode() == "local")

            if response is None:
                response = home.handle(brain, "GET", self.path, {}, self._mode() == "local")

            if response is not None:
                return self._send(*response)

            return self._send(404, {"error": t("Not found.")})

        # ----------------------------------------------------------
        # POST
        # ----------------------------------------------------------

        def _post(self):
            if not self._valid_origin():
                return self._send(403, {"error": t("Access not allowed."), "host": self._host()[:100], "version": Config.VERSION})

            path = urlparse(self.path).path

            if self._gate(path, "POST"):
                return

            if path == "/api/access/login":
                return self._enter()

            if path == "/api/sound/upload":
                return self._upload_sound()

            if path == "/api/voice":
                return self._voice()

            if path == "/api/documents/upload":
                return self._upload_document()

            if path == "/api/image":
                return self._image()

            if "application/json" not in self.headers.get("Content-Type", ""):
                return self._send(415, {"error": t("JSON was expected.")})

            if path == "/api/language":
                from brain.i18n import available, set_language

                code = (self._read_json() or {}).get("code", "")

                if code not in {a["code"] for a in available()}:
                    return self._send(400, {"error": t("Unknown language.")})

                set_language(code, persist=True)

                return self._send(200, {"language": language()})

            if path == "/api/access/password":
                if self._mode() != "local":
                    return self._send(403, {"error": t("The password can only be changed from the home computer.")})

                try:
                    access.set_password((self._read_json() or {}).get("key", ""))
                except ValueError as error:
                    return self._send(400, {"error": str(error)})

                return self._send(200, access.state())

            if path.startswith("/api/config/"):
                response = config.handle(brain, "POST", path, self._read_json() or {}, self._mode() == "local")

                if response is not None:
                    return self._send(*response)

            if path.startswith("/api/desktop/"):
                action = actions.get(path[len("/api/desktop/") :])

                if self._mode() != "local" or action is None:
                    return self._send(404, {"error": t("Not found.")})

                # It answers before running: "quit" shuts down this very server.
                self._send(200, {"ok": True})
                threading.Thread(target=action, daemon=True).start()

                return

            if path == "/api/access/logout":
                return self._send(200, {"ok": True}, headers={"Set-Cookie": f"{COOKIE_NAME}=; Path=/; Max-Age=0"})

            if path in ("/api/sounds/assign", "/api/sounds/delete"):
                notices = brain.modules.get("notices")
                data = self._read_json() or {}

                if notices is None:
                    return self._send(404, {"error": t("Notices are not available.")})

                try:
                    if path.endswith("/assign"):
                        notices.assign_sound(data.get("kind"), data.get("file"))
                    else:
                        notices.delete_sound(data.get("file"))
                except ValueError as error:
                    return self._send(400, {"error": str(error)})

                return self._send(200, notices.list_sounds())

            if path == "/api/repair":
                launch_repair(brain, force=True)

                return self._send(200, build_state(brain))

            if path == "/api/download":
                launch_download(brain)

                return self._send(200, build_state(brain))

            if path == "/api/models/select":
                label = (self._read_json() or {}).get("model", "").strip()

                try:
                    installed = {m.lower() for m in brain.ai.ollama.models()}
                except OllamaError as error:
                    return self._send(400, {"error": str(error)})

                if not label or label.lower() not in installed:
                    return self._send(400, {"error": t("That model is not installed.")})

                select_model(brain, label)

                return self._send(200, model_catalog(brain))

            if path == "/api/models/download":
                label = (self._read_json() or {}).get("model", "").strip()

                if not label:
                    return self._send(400, {"error": t("No model was given.")})

                if not launch_model_download(brain, label):
                    return self._send(409, {"error": t("A download is already underway.")})

                return self._send(200, model_catalog(brain))

            if path == "/api/voice/install":
                recognizer.install()

                return self._send(200, recognizer.state())

            if path in home.POST_ROUTES:
                response = home.handle(brain, "POST", self.path, self._read_json() or {}, self._mode() == "local")

                if response is not None:
                    return self._send(*response)

            if path in DATA_ROUTES:
                data = self._read_json()

                if data is None:
                    data = {}

                code, response = _action_data(brain, path, data)

                return self._send(code, response)

            if path in ("/api/conversations/create", "/api/conversations/rename", "/api/conversations/delete"):
                data = self._read_json() or {}

                try:
                    if path.endswith("/create"):
                        return self._send(200, {"conversation": brain.conversations.create(data.get("title"), data.get("instructions"))})

                    if path.endswith("/rename"):
                        return self._send(200, {"conversation": brain.conversations.rename(str(data.get("id", "")), data.get("title"))})

                    brain.conversations.delete(str(data.get("id", "")))

                    return self._send(200, {"ok": True})

                except KeyError as error:
                    return self._send(404, {"error": str(error.args[0])})

                except ValueError as error:
                    return self._send(400, {"error": str(error)})

            if path == "/api/clear":
                data = self._read_json() or {}

                try:
                    brain.conversations.get(data.get("conversation")).clear()
                except KeyError:
                    return self._send(404, {"error": t("That conversation does not exist.")})

                return self._send(200, {"ok": True})

            if path == "/api/chat":
                data = self._read_json()

                message = str((data or {}).get("message", "")).strip()

                if not message:
                    return self._send(400, {"error": t("The message is empty.")})

                if len(message) > MAX_MESSAGE:
                    return self._send(400, {"error": t("The message is too long.")})

                conversation_id = (data or {}).get("conversation") or "general"

                try:
                    brain.conversations.get(conversation_id)
                except KeyError:
                    return self._send(404, {"error": t("That conversation does not exist.")})

                with chat_lock:
                    try:
                        response = brain.conversations.ask(conversation_id, message)

                    except OllamaError as error:
                        return self._send(503, {"error": str(error)})

                    except Exception as error:
                        logger.error(f"Web chat: {error!r}")

                        return self._send(500, {"error": t("Unexpected error: {0}", error)})

                    used = [h["name"] for h in brain.ai.tools_used]

                return self._send(200, {"response": response, "tools": used})

            return self._send(404, {"error": t("Not found.")})

    return Handler


def create_server(brain, port=None, access=None, on_show=None, actions=None, settings=None):
    """Opens the web server on Config.WEB_HOST (if the port is busy, tries the next ones)."""

    port = port or Config.WEB_PORT

    handler = create_handler(brain, access, on_show, actions, settings)

    for attempt in range(port, port + 10):
        try:
            server = ThreadingHTTPServer((Config.WEB_HOST, attempt), handler)
            server.daemon_threads = True

            return server, attempt
        except OSError:
            continue

    raise OSError(t("I could not open any port between {0} and {1}.", port, port + 9))


def serve(brain, port=None, open_browser=True):
    """Starts BRAIN's web interface at http://127.0.0.1:<port>."""

    server, port = create_server(brain, port)

    url = f"http://127.0.0.1:{port}"

    print(t("\nBRAIN is running at {0}", url))
    print(t("Leave it open while you use it. To close it press Ctrl+C or close this window.\n"))

    logger.system(f"Web interface started at {url}")

    if open_browser:
        threading.Timer(0.8, webbrowser.open, args=(url,)).start()

    try:
        server.serve_forever()

    except KeyboardInterrupt:
        print(t("\nClosing BRAIN..."))

    finally:
        server.server_close()

        logger.system("Web interface closed")
