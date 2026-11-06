import json
import os
import re
import shutil
import socket
import subprocess
import time
from urllib import error, request

from brain.core.config import Config
from brain.utils.processes import execute
from brain.core.hardware import read_saved_model
from brain.i18n import t

# Order of preference when no specific model is requested.
PREFERRED_MODELS = (
    "qwen3.8:27b",
    "gemma4:26b",
    "gemma4:12b",
    "qwen3:8b",
    "gemma4:e4b",
    "gemma4:e2b",
    "qwen3:4b",
    "qwen3:latest",
    "llama3.1:8b",
    "llama3.2:3b",
    "gemma3:4b",
    "mistral:7b",
)


def _show_progress(state, completed, total):
    """Shows download progress in the console."""

    if total:
        percent = completed * 100 // total
        print(f"\r  {state[:30]:<30} {percent:3d}% ({completed / 1024**3:.1f}/{total / 1024**3:.1f} GB)", end="", flush=True)
    elif state:
        print(f"\r  {state[:60]:<60}", end="", flush=True)

    if state == "success":
        print()


class OllamaError(RuntimeError):
    """Error communicating with Ollama."""


class NoToolsError(OllamaError):
    """The chosen model does not support native tool calling."""


def strip_thinking(text):
    """
    Removes the internal reasoning (<think>...</think>) that some
    models, such as Qwen 3, include in the response.
    """

    if not text:
        return ""

    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

    if "</think>" in text:
        text = text.split("</think>")[-1]

    if "<think>" in text:
        text = text.split("<think>")[0]

    return text.strip()


def find_executable():
    """
    Locates the Ollama program.

    After installing it with winget, Windows does not refresh the PATH
    of the window already open, so the usual paths are also searched.
    """

    path = shutil.which("ollama")

    if path:
        return path

    candidates = []

    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA")
        files = os.environ.get("PROGRAMFILES")

        if local:
            candidates.append(os.path.join(local, "Programs", "Ollama", "ollama.exe"))

        if files:
            candidates.append(os.path.join(files, "Ollama", "ollama.exe"))
    else:
        candidates = ["/usr/local/bin/ollama", "/usr/bin/ollama"]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


class Ollama:
    """
    Client for talking to Ollama.

    Supports:
    - normal queries and conversations with history
    - automatic selection of the installed model
    - Ollama's native tool calling (optional)
    - starting the server and downloading models
    """

    def __init__(
        self,
        url=None,
        model=None,
        think=None,
    ):
        self.url = (url or Config.OLLAMA_URL).rstrip("/")

        # None = choose automatically among the installed models.
        self.model = model if model is not None else (Config.MODEL or None)

        self.think = Config.THINK if think is None else think

        # The system proxy is ignored: Ollama is local, and a corporate
        # or antivirus proxy can break the connection.
        self._opener = request.build_opener(request.ProxyHandler({}))

        self._models_cache = {}
        self._strip_think = set()

    # ------------------------------------------------------------------
    # Server and model status
    # ------------------------------------------------------------------

    def active_server(self):
        """Whether Ollama is responding."""

        try:
            self.models()
            return True
        except OllamaError:
            return False

    def start_server(self, wait=25):
        """
        Starts Ollama in the background if it is not running.

        Returns True if the server becomes available.
        """

        if self.active_server():
            return True

        executable = find_executable()

        if not executable:
            return False

        options = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }

        if os.name == "nt":
            options["creationflags"] = (
                subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
            )
        else:
            options["start_new_session"] = True

        try:
            subprocess.Popen([executable, "serve"], **options)
        except OSError:
            return False

        limit = time.time() + wait

        while time.time() < limit:
            if self.active_server():
                return True

            time.sleep(0.5)

        return False

    def download_model(self, name, progress=None):
        """
        Downloads a model through the same Ollama server BRAIN uses
        (so it is installed exactly where BRAIN will look for it).

        `progress(state, completed, total)` is called while downloading;
        by default the percentage is shown in the console.
        Returns True if the download finishes correctly.
        """

        if progress is None:
            progress = _show_progress

        req = request.Request(
            f"{self.url}/api/pull",
            data=json.dumps({"model": name, "stream": True}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        correct = False

        try:
            with self._opener.open(req, timeout=600) as response:
                for line in response:
                    try:
                        data = json.loads(line.decode("utf-8"))
                    except ValueError:
                        continue

                    if data.get("error"):
                        raise OllamaError(t("Ollama could not download '{0}': {1}", name, data["error"]))

                    state = data.get("status", "")

                    progress(state, data.get("completed", 0), data.get("total", 0))

                    if state == "success":
                        correct = True

        except error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")

            raise OllamaError(t("Ollama could not download '{0}' ({1}): {2}", name, e.code, detail)) from e

        except (error.URLError, TimeoutError, socket.timeout, ConnectionError) as e:
            raise OllamaError(t("The download of '{0}' was interrupted: {1}", name, e)) from e

        finally:
            self._models_cache.clear()

        return correct

    def list_by_command(self):
        """Output of `ollama list` (for diagnostics), or '' if it cannot be run."""

        executable = find_executable()

        if not executable:
            return ""

        try:
            output = execute([executable, "list"], capture_output=True, timeout=20)
        except (OSError, subprocess.SubprocessError):
            return ""

        return (output.stdout or b"").decode("utf-8", errors="replace").strip()

    def models(self):
        """
        Returns the models available in Ollama.
        """

        data = self._open_window(
            request.Request(f"{self.url}/api/tags"),
            timeout=10,
        )

        return [model["name"] for model in data.get("models", [])]

    @staticmethod
    def _find_model(name, installed_models):
        name = name.lower()

        for installed in installed_models:
            if installed.lower() == name:
                return installed

        if ":" not in name:
            for installed in installed_models:
                if installed.lower().startswith(name + ":"):
                    return installed

        return None

    def resolve_model(self, model=None):
        """
        Decides which model to use.

        If a specific one is requested it must be installed. Otherwise,
        the best one from the preferred list that is installed is
        chosen, and failing that any installed text model.
        """

        requested = model or self.model

        if requested in self._models_cache:
            return self._models_cache[requested]

        installed_models = self.models()

        chosen = None

        if requested:
            chosen = self._find_model(requested, installed_models)

            if chosen is None:
                items = ", ".join(installed_models) or t("none")

                raise OllamaError(
                    t(
                        "Model '{0}' is not installed in Ollama (installed: {1}). "
                        "Install it with: ollama pull {0}",
                        requested,
                        items,
                    )
                )
        else:
            # First the model "UPGRADE_AI.bat" chose (if still installed).
            saved = read_saved_model()

            if saved:
                chosen = self._find_model(saved, installed_models)

            for preferred in PREFERRED_MODELS:
                if chosen:
                    break

                chosen = self._find_model(preferred, installed_models)

            if chosen is None:
                for installed in installed_models:
                    if "embed" not in installed.lower():
                        chosen = installed
                        break

            if chosen is None:
                raise OllamaError(
                    t(
                        "Ollama has no model installed. "
                        "Run INSTALL.bat or type: ollama pull qwen3:4b"
                    )
                )

        self._models_cache[requested] = chosen

        return chosen

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------

    def _send(self, messages, model=None, tools=None):
        """Sends messages to /api/chat and returns the response message."""

        model_name = self.resolve_model(model)

        data = {
            "model": model_name,
            "messages": messages,
            "stream": False,
        }

        if tools:
            data["tools"] = tools

        if Config.CONTEXT:
            data["options"] = {"num_ctx": Config.CONTEXT}

        if self.think is not None and model_name not in self._strip_think:
            data["think"] = bool(self.think)

        try:
            result = self._post("/api/chat", data)

        except OllamaError as e:
            if "does not support tools" in str(e).lower():
                raise NoToolsError(str(e)) from e

            # Some models or Ollama versions do not support "think".
            if "think" in data and "think" in str(e).lower():
                self._strip_think.add(model_name)
                data.pop("think")
                result = self._post("/api/chat", data)
            else:
                raise

        message = dict(result.get("message") or {})
        message["content"] = strip_thinking(message.get("content", ""))

        return message

    def capabilities(self, model):
        """Capabilities Ollama reports for a model ("completion", "vision", "tools"...)."""

        cache = self.__dict__.setdefault("_capabilities", {})

        if model not in cache:
            try:
                cache[model] = list(self._post("/api/show", {"model": model}).get("capabilities") or [])
            except OllamaError:
                return []

        return cache[model]

    def vision_model(self, model=None):
        """The model (the current one or, if it cannot see images, another installed one) that reads images; or None."""

        try:
            current = self.resolve_model(model)
        except OllamaError:
            current = None

        candidates = ([current] if current else []) + [m for m in self.models() if m != current]

        for name in candidates:
            if "vision" in self.capabilities(name):
                return name

        return None

    def chat_with_image(self, question, image_base64, model=None):
        """Asks about an image (in base64) and returns the text of the response."""

        message = {"role": "user", "content": question, "images": [image_base64]}

        return self._send([message], model=model)["content"]

    def chat(self, messages, model=None):
        """
        Sends a list of messages ({"role": ..., "content": ...}) and
        returns the text of the response.
        """

        return self._send(messages, model=model)["content"]

    def full_chat(self, messages, model=None, tools=None):
        """
        Sends messages and returns the full response message
        (with "content" and, if the model asks for it, "tool_calls").
        """

        return self._send(messages, model=model, tools=tools)

    def ask(
        self,
        message,
        system=None,
        model=None,
        history=None,
    ):
        """
        Asks a question and returns the text of the response.

        `history` is the list of previous messages in the conversation.
        """

        messages = []

        if system:
            messages.append({"role": "system", "content": system})

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": message})

        return self.chat(messages, model=model)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _open_window(self, req, timeout):
        """Opens a request and translates the errors into OllamaError."""

        try:
            with self._opener.open(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))

        except error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")

            detail = body

            try:
                content = json.loads(body)

                if isinstance(content, dict):
                    detail = content.get("error", body)
            except ValueError:
                pass

            raise OllamaError(t("Ollama error ({0}): {1}", e.code, detail)) from e

        except error.URLError as e:
            raise OllamaError(
                t("Cannot connect to Ollama at {0}: {1}. Is Ollama running?", self.url, e.reason)
            ) from e

        except (TimeoutError, socket.timeout) as e:
            raise OllamaError(
                t(
                    "Ollama took too long to respond. The model may be "
                    "too large for this computer; try qwen3:4b."
                )
            ) from e

        except ConnectionError as e:
            raise OllamaError(t("Lost connection to Ollama: {0}", e)) from e

    def _post(self, endpoint, data):
        """
        Makes a POST request against Ollama.
        """

        req = request.Request(
            f"{self.url}{endpoint}",
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        return self._open_window(req, timeout=300)
