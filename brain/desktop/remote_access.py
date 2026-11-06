"""
Wizard to reach BRAIN from a phone or another PC with Tailscale.

Tailscale creates a private network between your devices. BRAIN keeps
listening only on this computer; `tailscale serve` publishes that address
only inside your private network, with HTTPS, and BRAIN asks for a password
from whoever reaches it that way. No router port is opened.
"""

import getpass
import json
import shutil
import subprocess
from typing import Optional

from brain.i18n import t
from brain.utils.processes import execute
from brain.web.access import MIN_PASSWORD, Access


def _execute(arguments, time=25):
    try:
        r = execute(arguments, capture_output=True, timeout=time)
    except (OSError, subprocess.SubprocessError):
        return None, ""

    return r.returncode, (r.stdout + r.stderr).decode("utf-8", errors="replace")


def find_tailscale() -> Optional[str]:
    found = shutil.which("tailscale")

    if found:
        return found

    import os
    from pathlib import Path

    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)"):
        base = os.environ.get(variable)

        if base and (Path(base) / "Tailscale" / "tailscale.exe").exists():
            return str(Path(base) / "Tailscale" / "tailscale.exe")

    return None


def tailscale_name(executable: str) -> Optional[str]:
    """This computer's private name on Tailscale (for example, home.tail1234.ts.net)."""

    code, text = _execute([executable, "status", "--json"])

    if code != 0:
        return None

    try:
        name = json.loads(text).get("Self", {}).get("DNSName", "")
    except ValueError:
        return None

    return name.rstrip(".") or None


def publish(executable: str, port: int) -> bool:
    """Publishes BRAIN inside the private network with HTTPS (tries the new syntax and the old one)."""

    for arguments in (
        [executable, "serve", "--bg", f"http://127.0.0.1:{port}"],
        [executable, "serve", "--bg", str(port)],
        [executable, "serve", "https", "/", f"http://127.0.0.1:{port}"],
    ):
        code, _ = _execute(arguments)

        if code == 0:
            return True

    return False


def publish_state(executable: str) -> str:
    """What Tailscale currently has published (`tailscale serve status`)."""

    _, text = _execute([executable, "serve", "status"], time=15)

    return text.strip()


def try_local(port: int, name: str) -> str:
    """
    Asks BRAIN for its entry page with the private name as `Host`, the same way
    Tailscale does. Returns "" if everything is fine, or the reason for the failure.
    """

    import http.client

    from brain.core.config import Config

    try:
        # http.client does not go through any system proxy (urllib might).
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        connection.request("GET", "/", headers={"Host": name, "X-Forwarded-Proto": "https"})
        response = connection.getresponse()
        body = response.read()
        server = response.getheader("Server", "unknown")
        connection.close()
    except Exception as error:
        return t("BRAIN is not responding on port {0} ({1}). Open BRAIN and repeat this step.", port, error)

    if response.status == 200 and b"BRAIN" in body:
        return ""

    detail = t("code {0}, server '{1}', port {2}, response: {3}", response.status, server, port, body[:160].decode("utf-8", "replace"))

    if not server.startswith("BRAIN/") or server != f"BRAIN/{Config.VERSION}":
        return (
            f"{detail}\n    "
            + t("It looks like there is an OLD copy of BRAIN open (or something else on that port).")
            + "\n    "
            + t("Run CLOSE_BRAIN.bat, open BRAIN again and repeat this step.")
        )

    return detail


def configure_access(port: int) -> int:
    from brain.desktop import instance

    # If BRAIN is already open on another port (8765 was taken), that one is used.
    port = instance.port_running() or port
    access = Access()

    print("\n=== " + t("Access to BRAIN from your phone or another computer") + " ===\n")

    if access.configured():
        print(t("There is already a password. Press Enter to keep it, or type a new one."))

    while True:
        key = getpass.getpass(t("Password (minimum {0} characters): ", MIN_PASSWORD))

        if not key and access.configured():
            break

        try:
            access.set_password(key)
            break
        except ValueError as error:
            print(f"  {error}")

    executable = find_tailscale()

    if executable is None:
        print(
            "\n" + t("The password is saved, but Tailscale is missing.") + "\n"
            "  1. " + t("Install it on this computer and on your phone from https://tailscale.com/download") + "\n"
            "  2. " + t("Sign in with the same account on both.") + "\n"
            "  3. " + t("Run CONFIGURE_ACCESS.bat again.") + "\n"
        )

        return 1

    name = tailscale_name(executable)

    if not name:
        print("\n" + t("Tailscale is installed but you have not signed in. Open it, sign in with your account and repeat this step.") + "\n")

        return 1

    if not publish(executable, port):
        print(
            "\n" + t("I could not publish BRAIN with Tailscale. If this is the first time, go to your Tailscale panel")
            + "\n"
            + t("(https://login.tailscale.com/admin/dns) and turn on 'HTTPS Certificates'; then repeat this step.")
            + "\n"
        )

        return 1

    address = f"https://{name}"
    access.save_address(address)
    access.add_host(name)

    problem = try_local(port, name)

    if problem:
        print(f"\n[!] " + t("BRAIN is not ready to receive connections: {0}", problem))
        print("    " + t("(private name: {0})", name))
        print("    " + t("Open BRAIN (desktop icon), wait a few seconds and run CONFIGURE_ACCESS.bat again.") + "\n")

        return 1

    print("\n" + t("Tailscale currently has this published:") + "\n")
    print(publish_state(executable) or "  (" + t("I could not read it.") + ")")

    print("\n" + t("Done. From your phone (with Tailscale on) open:") + f"\n\n    {address}\n")
    print(t("It will ask for the password. On your phone you can use 'Add to home screen' to have BRAIN as an app.") + "\n")

    return 0
