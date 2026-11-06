"""
Home Assistant client (the smart-home "hub" of the house).

Home Assistant connects to almost every brand (Philips Hue, IKEA, Tuya,
Shelly, Xiaomi, Zigbee, Z-Wave, Google, Alexa...). BRAIN only talks to
Home Assistant, and Home Assistant talks to the devices.

It uses only the Python standard library.
"""

import json
import os
from urllib import error, request

from brain.core.config import Config
from brain.i18n import t

# Usual addresses where Home Assistant lives on a home network.
USUAL_ADDRESSES = (
    "http://homeassistant.local:8123",
    "http://homeassistant:8123",
    "http://127.0.0.1:8123",
    "http://localhost:8123",
)


class HomeAssistantError(RuntimeError):
    """Error talking to Home Assistant (the message is meant for the user)."""


def _config_file():
    return Config.DATA / "smart_home" / "home_assistant.json"


def normalize_url(url):
    """Accepts '192.168.1.5', 'homeassistant.local:8123', 'http://...'."""

    url = (url or "").strip().rstrip("/")

    if not url:
        return ""

    if "://" not in url:
        url = "http://" + url

    schema, rest = url.split("://", 1)
    rest = rest.split("/", 1)[0]

    if ":" not in rest:
        rest += ":8123"

    return f"{schema}://{rest}"


def read_config():
    """Return (url, token). Environment variables take priority."""

    url = os.environ.get("BRAIN_HA_URL", "").strip()
    token = os.environ.get("BRAIN_HA_TOKEN", "").strip()

    if not (url and token):
        try:
            data = json.loads(_config_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}

        if isinstance(data, dict):
            url = url or str(data.get("url", "")).strip()
            token = token or str(data.get("token", "")).strip()

    return normalize_url(url), token


def save_config(url, token):
    """Save the address and the access token of Home Assistant."""

    file = _config_file()
    file.parent.mkdir(parents=True, exist_ok=True)

    file.write_text(
        json.dumps({"url": normalize_url(url), "token": token.strip()}, indent=4),
        encoding="utf-8",
    )

    try:
        # On Unix-like systems, so that only the user can read it.
        os.chmod(file, 0o600)
    except OSError:
        pass


class HomeAssistant:
    """Client of the Home Assistant REST API."""

    def __init__(self, url=None, token=None, timeout=15):
        if url is None and token is None:
            url, token = read_config()

        self.url = normalize_url(url)
        self.token = (token or "").strip()
        self.timeout = timeout

        # Home Assistant is on the home network: the system proxy is ignored.
        self._opener = request.build_opener(request.ProxyHandler({}))

    @property
    def configured(self):
        return bool(self.url and self.token)

    # ------------------------------------------------------------------
    # Communication
    # ------------------------------------------------------------------

    def _req(self, method, path, data=None, text=False):
        if not self.configured:
            raise HomeAssistantError(
                t("The smart home is not connected yet. Run CONFIGURE_SMART_HOME.bat to connect BRAIN to Home Assistant.")
            )

        body = None

        if data is not None:
            body = json.dumps(data).encode("utf-8")

        req = request.Request(
            f"{self.url}{path}",
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )

        try:
            with self._opener.open(req, timeout=self.timeout) as response:
                content = response.read().decode("utf-8")

        except error.HTTPError as e:
            if e.code == 401:
                raise HomeAssistantError(
                    t("Home Assistant rejected the access token. Create a new one and run CONFIGURE_SMART_HOME.bat.")
                ) from e

            if e.code == 404:
                raise HomeAssistantError(t("Home Assistant does not recognise the request {0}.", path)) from e

            detail = e.read().decode("utf-8", errors="replace")[:200]

            raise HomeAssistantError(t("Home Assistant answered with an error ({0}): {1}", e.code, detail)) from e

        except error.URLError as e:
            raise HomeAssistantError(
                t(
                    "I cannot connect to Home Assistant at {0} ({1}). Is it on and on the same network as this computer?",
                    self.url,
                    e.reason,
                )
            ) from e

        except (TimeoutError, OSError) as e:
            raise HomeAssistantError(t("Home Assistant does not answer at {0}: {1}", self.url, e)) from e

        if text:
            return content

        try:
            return json.loads(content) if content else None
        except ValueError as e:
            raise HomeAssistantError(t("Home Assistant returned an answer I do not understand.")) from e

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def check(self):
        """Raise HomeAssistantError if there is no valid connection."""

        self._req("GET", "/api/")

    def states(self):
        """List of all the entities with their current state."""

        return self._req("GET", "/api/states") or []

    def state(self, entity_id):
        return self._req("GET", f"/api/states/{entity_id}")

    def service(self, domain, service, data):
        """Run a service, for example light.turn_on with {'entity_id': ...}."""

        return self._req("POST", f"/api/services/{domain}/{service}", data or {})

    def areas(self):
        """
        Room of each entity, as {entity_id: room_name}.

        Home Assistant does not give the rooms in /api/states, so they are
        requested with a template. If they cannot be obtained, {} is returned.
        """

        template = "{% for s in states %}{{ s.entity_id }}|{{ area_name(s.entity_id) or '' }}\n{% endfor %}"

        try:
            text = self._req("POST", "/api/template", {"template": template}, text=True)
        except HomeAssistantError:
            return {}

        result = {}

        for line in (text or "").splitlines():
            entity, _, area = line.partition("|")

            if entity.strip() and area.strip() and area.strip().lower() != "none":
                result[entity.strip()] = area.strip()

        return result


def find_home_assistant():
    """
    Look for Home Assistant at the usual addresses (without needing the
    token). Return the first that answers, or '' if none is found.
    """

    for url in USUAL_ADDRESSES:
        req = request.Request(f"{url}/api/", method="GET")
        opener = request.build_opener(request.ProxyHandler({}))

        try:
            opener.open(req, timeout=3)
            return url
        except error.HTTPError as e:
            # 401 = "I need the token": it is there and working.
            if e.code in (401, 403):
                return url
        except (error.URLError, OSError):
            continue

    return ""
